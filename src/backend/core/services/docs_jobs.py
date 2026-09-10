"""Document moves and copies use the existing resumable transfer queue."""

import hashlib
import json
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from rest_framework.exceptions import APIException, PermissionDenied
from suite_identity.document_transport import actor_context, resolve_actor, send

from core.models import Item, ItemAccess, StorageCopyEntry, StorageMoveJob
from core.services.docs_lifecycle import change_document
from core.services.storage_namespace import advisory_guard
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_transfer_location import resolve_location


def enqueue(actor, source, destination, *, mode, request_key=None, with_accesses=False):  # noqa: PLR0913
    """Persist real delegation and stable copy identities; no synthetic owner session."""
    from core.services.storage_move_job import dispatch_move  # noqa: PLC0415

    ability = "move" if mode == "move" else "duplicate"
    if mode not in {"move", "copy"} or not source.reference.get_abilities(actor).get(ability):
        raise PermissionDenied()
    if with_accesses and not source.reference.get_abilities(actor).get("accesses_manage"):
        raise PermissionDenied()
    intent = {
        "source": str(source.reference.pk),
        "destination": destination.descriptor(),
        "mode": mode,
        "with_accesses": with_accesses,
    }
    digest = hashlib.sha256(json.dumps(intent, sort_keys=True).encode()).hexdigest()
    key = request_key or uuid4()
    proof = actor_context(actor)
    with advisory_guard(f"storage-move:{key}"), transaction.atomic():
        job, created = StorageMoveJob.objects.get_or_create(
            pk=key,
            defaults={
                "actor": actor,
                "space": destination.space,
                "kind": f"docs_{mode}",
                "source_path": str(source.reference.pk),
                "destination_path": str(destination.reference.pk),
                "source_identity": str(source.reference.docs_binding.document_id),
                "payload": {
                    **intent,
                    "request_hash": digest,
                    "title": source.name,
                    "destination_title": destination.name,
                    "actor": proof,
                },
            },
        )
        if not created and (job.actor_id != actor.pk or job.payload.get("request_hash") != digest):
            raise PermissionDenied("This operation key belongs to another request.")
        if job.state not in {"done", "failed"}:
            job.payload["actor"] = proof
            job.state, job.reason = "queued", ""
            job.save(update_fields=["payload", "state", "reason", "updated_at"])
            transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


def _index(job, source):
    """Freeze a metadata manifest in bounded batches, before copying any content."""
    if job.payload.get("indexed"):
        return
    if not source.get_abilities(job.actor).get("duplicate"):
        raise PermissionDenied()
    with advisory_guard("docs-tree-placement", shared=True), transaction.atomic():
        root = Item.objects.select_for_update().get(pk=source.pk)
        entries = (
            Item.objects.filter(path__descendants=root.path, ancestors_deleted_at__isnull=True)
            .select_related("docs_binding", "storageusage")
            .order_by("path")
        )
        # The whole index commits atomically; an interrupted pass owns no
        # completed entries. Keep only the ancestor stack and one insert batch.
        if job.copy_entries.exists():
            raise StorageWriteConflict("An incomplete document manifest needs reconciliation.")
        ancestors, batch = [], []
        for item in entries.iterator(chunk_size=100):
            if item.type != "docs":
                raise PermissionDenied()
            path = str(item.path)
            while ancestors and not path.startswith(ancestors[-1][0] + "."):
                ancestors.pop()
            if item.pk != root.pk and not ancestors:
                raise StorageWriteConflict("The document tree changed during preparation.")
            entry = StorageCopyEntry(
                job=job,
                source_id=item.pk,
                kind="docs",
                name=item.title,
                parent_id=ancestors[-1][1] if ancestors else None,
                source={
                    "document_id": str(item.docs_binding.document_id),
                    "revision": item.docs_binding.revision,
                    "version": item.storageusage.version,
                },
                publication={"document_id": str(uuid4()), "request_key": str(uuid4())},
            )
            ancestors.append((path, entry.pk))
            batch.append(entry)
            if len(batch) == 100:
                StorageCopyEntry.objects.bulk_create(batch)
                batch.clear()
        StorageCopyEntry.objects.bulk_create(batch)
        job.payload["indexed"] = True
        job.save(update_fields=["payload", "updated_at"])


def execute(job):
    """Each pass copies at most ten documents; a new request renews expired proof."""
    if job.state in {"done", "failed", "conflict"}:
        return job.state
    try:
        actor = resolve_actor(job.payload.get("actor"))
        if actor.pk != job.actor_id:
            raise PermissionDenied()
        job.actor = actor
        target = job.payload["destination"]
        destination = resolve_location(
            target["id"],
            actor,
            space_id=target["space"],
            destination=True,
            allow_document=job.kind == "docs_copy",
        )
        if destination.descriptor() != target:
            raise StorageWriteConflict("The destination changed. Choose it again.")
        source = Item.objects.get(pk=job.source_path, type="docs")
        if job.kind == "docs_move":
            result = change_document(
                actor,
                {
                    "action": "move",
                    "document_id": source.docs_binding.document_id,
                    "destination": destination.reference.pk,
                    "space_id": destination.space.pk,
                    "request_key": job.pk,
                },
            )
            job.state = "done" if result["revision"] == result["applied_revision"] else "running"
            job.payload["result"] = str(source.pk)
        else:
            _index(job, source)
            for entry in (
                job.copy_entries.filter(done=False)
                .select_related("parent")
                .order_by("created_at", "pk")[:10]
            ):
                if entry.parent_id and not entry.parent.done:
                    continue
                _copy_entry(job, entry, destination)
            job.state = "running" if job.copy_entries.filter(done=False).exists() else "done"
            root = job.copy_entries.get(source_id=source.pk)
            job.payload["result"] = str(root.target_id) if root.target_id else None
        job.reason = ""
    except (APIException, Item.DoesNotExist):
        job.state = "conflict"
        job.reason = "Document operation paused. Check access and quotas, then retry."
    # A concurrent cancellation may have purged an unpublished copy while
    # this worker was waiting for Docs. Never resurrect that operation.
    if (
        not StorageMoveJob.objects.filter(pk=job.pk)
        .exclude(state="failed")
        .update(state=job.state, payload=job.payload, reason=job.reason, updated_at=timezone.now())
    ):
        return "failed"
    return "more" if job.state == "running" else job.state


def _copy_entry(job, entry, destination):
    source = Item.objects.select_related("docs_binding").get(pk=entry.source_id)
    if not source.get_abilities(job.actor).get("duplicate"):
        raise PermissionDenied()
    result = send(
        "/api/v1.0/internal/drive/copy/",
        {
            **entry.source,
            **entry.publication,
            "source_document_id": entry.source["document_id"],
            "destination": str(
                entry.parent.target_id if entry.parent_id else destination.reference.pk
            ),
            "space_id": str(destination.space.pk),
            "title": entry.name if entry.parent_id else f"Copy of {entry.name}"[:255],
        },
        purpose="mutation",
        actor=job.payload["actor"],
    )
    if result.get("state") != "active":
        return
    if result.get("document_id") != entry.publication["document_id"]:
        raise StorageWriteConflict("The copy response has an unexpected identity.")
    target = Item.objects.get(docs_binding__document_id=result["document_id"])
    if not target.get_abilities(job.actor).get("accesses_manage"):
        raise PermissionDenied()
    if job.payload["with_accesses"]:
        if not source.get_abilities(job.actor).get("accesses_manage") or not target.get_abilities(
            job.actor
        ).get("accesses_manage"):
            raise PermissionDenied()
        with transaction.atomic():
            Item.objects.select_for_update().get(pk=target.pk)
            for access in source.accesses.all().iterator(chunk_size=100):
                ItemAccess.objects.get_or_create(
                    item=target,
                    user_id=access.user_id,
                    team=access.team,
                    defaults={"role": access.role},
                )
    entry.target_id, entry.done = target.pk, True
    entry.save(update_fields=["target_id", "done", "updated_at"])
