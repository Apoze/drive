"""Copy folder manifests in bounded passes, reusing file publication journals."""

import posixpath
import uuid
from contextlib import ExitStack
from itertools import batched

from django.conf import settings
from django.db import transaction

from rest_framework.exceptions import APIException, PermissionDenied
from suite_identity.document_transport import actor_context, resolve_actor

from core.models import Item, StorageCopyEntry, StorageMoveJob, StorageResource
from core.mounts.providers.virtual import _target, _virtual_entry
from core.services import storage_inventory as inventory
from core.services import storage_quota as quota
from core.services.storage_access import cache_item_grants
from core.services.storage_copy_job import enqueue_copy, validate_copy_name
from core.services.storage_mount_write import _stat_or_none
from core.services.storage_move_job import dispatch_move, execute_move
from core.services.storage_namespace import StorageOperationBusy, namespace_guard
from core.services.storage_resources import observe_resources
from core.services.storage_spaces import authorize
from core.services.storage_transfer_location import (
    TransferLocation,
    item_location,
    resolve_location,
)


def enqueue_folder_copy(*, actor, source, destination, name=None, mode="copy"):
    """Persist the folder's identity before walking or creating anything native."""
    if source.kind != "folder":
        raise quota.StorageWriteConflict("Choose a source folder.")
    if mode == "move":
        if source.backend.family == "mount":
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_native_folder_move import (  # noqa: PLC0415
                validate_native_tree,
            )

            validate_native_tree(source, actor)
        else:
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_item_tree_move import validate_tree_transfer  # noqa: PLC0415

            validate_tree_transfer(source, destination, actor)
    if source.backend.namespace == destination.backend.namespace:
        separator = "." if source.backend.family == "s3" else "/"
        start = str(source.reference.path).rstrip(separator)
        target = str(destination.reference.path).rstrip(separator)
        if target == start or target.startswith(start + separator):
            raise quota.StorageWriteConflict("A folder cannot be copied into itself.")
    name = validate_copy_name(name or source.name)
    proof = actor_context(actor) if settings.DOCS_DRIVE_ENABLED else None
    with transaction.atomic():
        job, created = StorageMoveJob.objects.get_or_create(
            actor=actor,
            kind="folder_move" if mode == "move" else "folder_copy",
            space=source.space,
            source_path=str(source.reference.pk),
            destination_path=str(destination.reference.pk),
            state__in=["queued", "running", "conflict"],
            defaults={
                "source_identity": str(source.reference.pk),
                "payload": {
                    "title": name,
                    "destination_title": destination.name,
                    "source": source.descriptor(),
                    "destination": destination.descriptor(),
                },
            },
        )
        if not created and (
            job.payload["title"] != name or job.payload["destination"] != destination.descriptor()
        ):
            raise quota.StorageWriteConflict(
                "Recover the existing folder copy before changing its target."
            )
        if settings.DOCS_DRIVE_ENABLED:
            job.payload["actor"] = proof
            job.save(update_fields=["payload", "updated_at"])
        StorageCopyEntry.objects.get_or_create(
            job=job,
            source_id=source.reference.pk,
            defaults={
                "source": source.descriptor(),
                "kind": "folder",
                "name": name,
            },
        )
        transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


def _resolve(snapshot, actor, *, destination=False):
    location = resolve_location(
        snapshot["id"], actor, space_id=snapshot["space"], destination=destination
    )
    if location.descriptor() != snapshot:
        raise quota.StorageWriteConflict("A transfer location changed.")
    return location


def _folder(entry, destination, actor):
    """Publish a new directory without ever merging into an existing native folder."""
    if entry.target_id:
        return resolve_location(
            entry.target_id, actor, space_id=destination.space.pk, destination=True
        )
    if destination.backend.family == "s3":
        with transaction.atomic():
            item = Item.objects.create_child(
                parent=destination.reference, type="folder", title=entry.name, creator=actor
            )
            entry.target_id = item.pk
            entry.save(update_fields=["target_id", "updated_at"])
        return resolve_location(item.pk, actor, destination=True)
    path = posixpath.join(destination.path, entry.name)
    with _target(destination.mount, path, write=True) as (space, _, provider, native, native_path):
        if not callable(getattr(provider, "rename_no_replace", None)):
            raise quota.StorageWriteConflict("Protected directory publication is unavailable.")
        publication = entry.publication
        if not publication.get("phase"):
            publication = {
                **publication,
                "temp": posixpath.join(
                    posixpath.dirname(native_path), f".drive-txn-copy-{uuid.uuid4()}"
                ),
                "path": native_path,
                "phase": "creating",
            }
            entry.publication = publication
            entry.save(update_fields=["publication", "updated_at"])
            if _stat_or_none(provider, native, publication["temp"]):
                raise quota.StorageWriteConflict("The staging directory already exists.")
            provider.mkdirs(mount=native, normalized_path=publication["temp"])
            staged = provider.stat(mount=native, normalized_path=publication["temp"])
            if not staged.object_identity:
                raise quota.StorageWriteConflict(
                    "Directory publication requires a stable identity."
                )
            publication.update(identity=staged.object_identity, phase="publishing")
            entry.save(update_fields=["publication", "updated_at"])
        if publication.get("phase") != "publishing":
            raise quota.StorageWriteConflict(
                "Directory creation was interrupted; its staging folder is retained."
            )
        final = _stat_or_none(provider, native, native_path)
        if not final:
            staged = provider.stat(mount=native, normalized_path=publication["temp"])
            if staged.object_identity != publication["identity"]:
                raise quota.StorageWriteConflict("The staged directory was replaced.")
            provider.rename_no_replace(
                mount=native,
                src_normalized_path=publication["temp"],
                dst_normalized_path=native_path,
            )
            final = provider.stat(mount=native, normalized_path=native_path)
        if final.object_identity != publication["identity"]:
            raise quota.StorageWriteConflict(
                "The destination folder already exists; nothing was overwritten."
            )
        observe_resources(space.backend, [final])
        entry.target_id = StorageResource.objects.get(
            namespace=space.backend.namespace,
            provider_identity=final.object_identity,
        ).pk
        entry.save(update_fields=["target_id", "updated_at"])
    return resolve_location(entry.target_id, actor, space_id=destination.space.pk, destination=True)


def _children(source, actor):
    """Yield current permitted references; never materialize a whole directory in RAM."""
    if source.backend.family == "s3":
        children = (
            source.reference.children()
            .filter(
                deleted_at__isnull=True,
                hard_deleted_at__isnull=True,
            )
            .select_related("storage_backend", "storage_space__backend")
            .annotate_user_roles(actor)
            .order_by("pk")
            .iterator(chunk_size=100)
        )
        for batch in batched(children, 100, strict=False):
            cache_item_grants(batch, actor)
            for child in batch:
                yield item_location(child, actor)
        return
    with _target(source.mount, source.path, traverse=True) as (space, _, provider, native, path):
        children = getattr(provider, "iter_children", None)
        if not callable(children):
            raise quota.StorageWriteConflict("Bounded folder enumeration is unavailable.")
        # Provider callability is checked above; Pylint cannot infer registry modules.
        # pylint: disable-next=not-callable
        for child in children(mount=native, normalized_path=path):
            if child.name.startswith(".drive-txn-"):
                continue
            virtual_path = _virtual_entry(space, child).normalized_path
            authorize(space, actor, virtual_path, traverse=True)
            usage = inventory.observe_entry(space.backend, child)
            key = (
                quota.resource_key(f"reference:{usage.key}")
                if child.entry_type == "file"
                else quota.resource_key(f"mount:{space.backend.namespace}:{child.object_identity}")
            )
            reference = StorageResource.objects.get(identity_key=key)
            yield TransferLocation(reference, space, virtual_path, source.mount)
    if not settings.DOCS_DRIVE_ENABLED:
        return
    documents = (
        Item.objects.filter(
            type="docs",
            docs_binding__mounted_parent=source.reference,
            docs_binding__anchor_space=source.space,
            deleted_at__isnull=True,
            hard_deleted_at__isnull=True,
        )
        .select_related("docs_binding")
        .order_by("pk")
    )
    for document in documents.iterator(chunk_size=100):
        yield item_location(document, actor)


def _enumerate(entry, source, actor):
    # ponytail: a restarted directory re-enumerates metadata; add native cursors
    # if retry cost becomes significant.
    for children in batched(_children(source, actor), 100, strict=False):
        StorageCopyEntry.objects.bulk_create(
            [
                StorageCopyEntry(
                    job_id=entry.job_id,
                    source_id=child.reference.pk,
                    parent=entry,
                    source=child.descriptor(),
                    kind=child.kind,
                    name=child.name if child.kind == "docs" else validate_copy_name(child.name),
                )
                for child in children
            ],
            ignore_conflicts=True,
        )
    entry.enumerated = True
    entry.save(update_fields=["enumerated", "updated_at"])


def _file(entry, source, destination, job):
    if source.kind == "docs" and (
        not entry.child_job_id
        or (entry.child_job.state in {"failed", "conflict"} and job.payload.get("retry_failed"))
    ):
        from core.services.docs_jobs import enqueue  # noqa: PLC0415

        child = enqueue(
            job.actor,
            source,
            destination,
            mode="move" if job.kind == "folder_move" else "copy",
            request_key=entry.pk,
        )
        child.payload["parent_job"] = str(job.pk)
        child.save(update_fields=["payload", "updated_at"])
        entry.child_job = child
        entry.save(update_fields=["child_job", "updated_at"])
    if not entry.child_job_id or (
        entry.child_job.state == "failed" and job.payload.get("retry_failed")
    ):
        with transaction.atomic():
            if job.kind == "folder_move":
                # pylint: disable-next=import-outside-toplevel,cyclic-import
                from core.services.storage_move_job import enqueue_transfer  # noqa: PLC0415

                child = enqueue_transfer(
                    actor=job.actor,
                    source=source,
                    destination=destination,
                    mode="move" if job.kind == "folder_move" else "copy",
                )
            else:
                child = enqueue_copy(
                    actor=job.actor, source=source, destination=destination, name=entry.name
                )
            child.payload = {**child.payload, "parent_job": str(job.pk)}
            child.save(update_fields=["payload", "updated_at"])
            entry.child_job = child
            entry.save(update_fields=["child_job", "updated_at"])
    outcome = execute_move(entry.child_job_id)
    if outcome in {"conflict", "failed"}:
        raise quota.StorageWriteConflict(
            "A child transfer needs attention; completed entries are retained."
        )
    if outcome not in ({"done", "cleanup"} if job.kind == "folder_move" else {"done"}):
        return False
    entry.child_job.refresh_from_db()
    entry.target_id = entry.child_job.payload["result"]
    entry.done = True
    entry.save(update_fields=["target_id", "done", "updated_at"])
    return True


# Manifest entries and file journals resume independently.
# pylint: disable-next=too-many-return-statements,too-many-branches
def execute_folder_copy(job):  # noqa: PLR0911, PLR0912
    """The parent advisory lock owns its manifest; each file keeps its own journal."""
    if job.state in {"done", "failed", "conflict"}:
        return job.state
    try:
        job.actor.refresh_from_db()
        _restore_actor(job)
        if job.payload.get("finalizing"):
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_native_folder_move import finish_native_tree  # noqa: PLC0415

            return finish_native_tree(job)
        source, destination = (
            _resolve(job.payload["source"], job.actor),
            _resolve(job.payload["destination"], job.actor, destination=True),
        )
        with ExitStack() as guards:
            for backend in sorted(
                {source.backend, destination.backend}, key=lambda value: str(value.namespace)
            ):
                guards.enter_context(namespace_guard(backend, exclusive=True))
            job.state, job.reason = "running", ""
            job.save(update_fields=["state", "reason", "updated_at"])
            for entry in (
                job.copy_entries.filter(done=False)
                .select_related("parent", "child_job")
                .order_by("created_at", "pk")[:20]
            ):
                if entry.child_job_id and entry.child_job.state in (
                    {"done", "cleanup"} if job.kind == "folder_move" else {"done"}
                ):
                    entry.target_id, entry.done = entry.child_job.payload["result"], True
                    entry.save(update_fields=["target_id", "done", "updated_at"])
                    continue
                current = _resolve(entry.source, job.actor)
                target = (
                    _resolve(entry.parent.publication["target"], job.actor, destination=True)
                    if entry.parent_id
                    else destination
                )
                if entry.kind == "folder":
                    created = _folder(entry, target, job.actor)
                    if "target" not in entry.publication:
                        entry.publication = {**entry.publication, "target": created.descriptor()}
                        entry.save(update_fields=["publication", "updated_at"])
                    if not entry.enumerated:
                        _enumerate(entry, current, job.actor)
                    entry.done = True
                    entry.save(update_fields=["done", "updated_at"])
                elif entry.kind == "docs":
                    # Native Docs calls Drive back to admit placement and quotas.
                    # Never hold namespace locks across that private round trip.
                    guards.close()
                    completed = _file(entry, current, target, job)
                    for backend in sorted(
                        {source.backend, destination.backend},
                        key=lambda value: str(value.namespace),
                    ):
                        guards.enter_context(namespace_guard(backend, exclusive=True))
                    if not completed:
                        return "busy"
                elif not _file(entry, current, target, job):
                    return "busy"
            if job.copy_entries.filter(done=False).exists():
                return "more"
            if job.kind == "folder_move":
                if source.backend.family == "mount":
                    job.payload = {**job.payload, "finalizing": True}
                    job.save(update_fields=["payload", "updated_at"])
                    return "more"
                # pylint: disable-next=import-outside-toplevel,cyclic-import
                from core.services.storage_item_tree_move import (  # noqa: PLC0415
                    finish_tree_manifest,
                )

                finish_tree_manifest(job)
                return "done"
            job.state = "done"
            job.payload = {
                **job.payload,
                "result": str(job.copy_entries.get(parent__isnull=True).target_id),
            }
            job.save(update_fields=["state", "payload", "updated_at"])
            return "done"
    except StorageOperationBusy:
        return "busy"
    except APIException as exc:
        job.state, job.reason = "conflict", str(exc.detail)[:255]
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        job.state, job.reason = "running", "Storage unavailable; this transfer will be retried."
    job.save(update_fields=["state", "reason", "updated_at"])
    return job.state


def retain_interrupted_staging(job):
    """Explicit recovery starts a new attempt; unproven directories are never adopted."""
    for entry in job.copy_entries.filter(
        target_id__isnull=True,
        publication__phase="creating",
    ).iterator(chunk_size=100):
        publication = entry.publication
        entry.publication = {
            "retained_staging": [
                *publication.get("retained_staging", []),
                {key: publication[key] for key in ("temp", "path")},
            ],
        }
        entry.save(update_fields=["publication", "updated_at"])


def _restore_actor(job):
    """Resume only with the original, still-valid suite delegation."""
    if job.payload.get("actor"):
        actor = resolve_actor(job.payload["actor"])
        if actor.pk != job.actor_id:
            raise PermissionDenied()
        job.actor = actor
