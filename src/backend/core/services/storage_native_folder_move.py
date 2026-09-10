"""Finalize native folder manifests through existing retained-deletion journals."""

import uuid
from contextlib import ExitStack

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.db.models.expressions import RawSQL

from core.models import DocsBinding, Item, StorageMoveJob, StorageReservation, StorageResource
from core.mounts.providers import virtual
from core.services.docs_lifecycle import queue_tree_changes
from core.services.storage_item_tree_move import _finish_native_folder
from core.services.storage_namespace import namespace_guard
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_recovery import reconcile_operation
from core.services.storage_resources import (
    bind_legacy_shares,
    transfer_native_links,
    transfer_staged_item_links,
)
from core.services.storage_spaces import authorize, context, native_path, resolve_space_mount
from core.services.storage_transfer_location import TransferLocation, resolve_location


def validate_native_tree(source, actor):
    """The writable directory must not contain any allocated storage root."""
    if source.kind != "folder" or source.backend.family != "mount":
        raise StorageWriteConflict("Choose a mounted source folder.")
    # Use the same root protection as ordinary native moves and deletion.
    # pylint: disable-next=protected-access
    with virtual._target(source.mount, source.path, write=True) as target:  # noqa: SLF001
        # pylint: disable-next=protected-access
        virtual._protect_roots(target[0], target[4])  # noqa: SLF001
        authorize(target[0], actor, source.path, write=True)
    if settings.DOCS_DRIVE_ENABLED:
        roots = DocsBinding.objects.filter(
            Q(mounted_parent=source.reference)
            | Q(
                mounted_parent__namespace=source.backend.namespace,
                mounted_parent__path__startswith=source.reference.path.rstrip("/") + "/",
            ),
            item__path__ancestors=OuterRef("path"),
        )
        if (
            Item.objects.alias(anchored=Exists(roots))
            .filter(anchored=True)
            .exclude(docs_binding__state="active", ancestors_deleted_at__isnull=True)
            .exists()
        ):
            raise StorageWriteConflict(
                "Resolve pending or deleted documents before moving this folder."
            )


def _source(entry, job):
    """A retained source keeps its original authorization even after its public path disappears."""
    snapshot = entry.source
    mount = resolve_space_mount(snapshot["space"], job.actor)
    if not mount:
        raise StorageWriteConflict("The source folder is no longer writable.")
    space, actor, _ = context(mount)
    authorize(space, actor, snapshot["path"], write=True)
    if (str(space.backend_id), space.backend.configuration_generation) != (
        snapshot["backend"],
        snapshot["generation"],
    ):
        raise StorageWriteConflict("The source folder connection changed.")
    resource = StorageResource.objects.get(pk=entry.source_id, namespace=space.backend.namespace)
    return TransferLocation(resource, space, snapshot["path"], mount)


def _retain(entry, source, job):
    """Each empty directory gets its own resumable quarantine, never recursive deletion."""
    if (
        settings.DOCS_DRIVE_ENABLED
        and DocsBinding.objects.filter(mounted_parent=source.reference).exists()
    ):
        raise StorageWriteConflict(
            "The source folder has unfinished documents. Completed transfers are retained."
        )
    operation_id = entry.publication.get("source_operation")
    if operation_id:
        outcome = reconcile_operation(operation_id, move_job_id=job.pk)
        if outcome == "committed":
            return
        if outcome != "cancelled":
            raise StorageWriteConflict("The source folder retention needs verification.")
    current = resolve_location(entry.source_id, job.actor, space_id=source.space.pk)
    if current.descriptor() != entry.source:
        raise StorageWriteConflict("The source folder moved during transfer.")
    bind_legacy_shares(source.backend, native_path(source.space, source.path))
    virtual.remove(mount=source.mount, normalized_path=source.path, folder_entry_id=entry.pk)
    entry.refresh_from_db()


@transaction.atomic
def _publish(entry, job):
    """The original folder UUID switches location with its manifest checkpoint."""
    source = _source(entry, job)
    target = resolve_location(
        entry.target_id,
        job.actor,
        space_id=entry.publication["target"]["space"],
        destination=True,
    )
    if target.descriptor() != entry.publication["target"]:
        raise StorageWriteConflict("The destination folder changed during transfer.")
    operation = StorageReservation.objects.get(pk=entry.publication["source_operation"])
    if operation.state != "committed":
        raise StorageWriteConflict("The source directory has not been safely retained.")
    if target.backend.family == "mount":
        _finish_native_folder(source.reference, target.reference, target)
    else:
        temporary = target.reference
        item = Item.objects.create_child(
            parent=temporary.parent(),
            id=source.reference.pk,
            share_link_nonce=uuid.uuid4(),
            type="folder",
            title=temporary.title,
            creator=source.space.owner or job.actor,
        )
        # The placeholder owns its name until both rows are switched at this commit.
        Item.objects.filter(pk=item.pk).update(title=temporary.title)
        Item.objects.filter(path__descendants=temporary.path).exclude(pk=temporary.pk).update(
            path=RawSQL("%s || subpath(path, nlevel(%s))", (str(item.path), str(temporary.path))),
        )
        transfer_native_links(source.reference, item)
        transfer_staged_item_links(temporary, item)
        Item.objects.filter(pk=temporary.pk).delete()
        queue_tree_changes(item)
    entry.target_id = source.reference.pk
    entry.publication = {**entry.publication, "moved": True}
    entry.save(update_fields=["target_id", "publication", "updated_at"])


@transaction.atomic
def _finish(job):
    """Child cleanup resolves the final parent UUIDs after all folder identities are rebound."""
    for entry in (
        job.copy_entries.filter(kind="file")
        .select_related("parent", "child_job")
        .iterator(chunk_size=100)
    ):
        parent = resolve_location(
            entry.parent.target_id,
            job.actor,
            space_id=job.payload["destination"]["space"],
            destination=True,
        )
        StorageMoveJob.objects.filter(pk=entry.child_job_id).update(
            destination_path=str(parent.reference.pk),
            payload={**entry.child_job.payload, "destination": parent.descriptor()},
        )
    job.state, job.reason = "done", ""
    job.payload = {**job.payload, "result": job.source_path, "source_retained": True}
    job.save(update_fields=["state", "reason", "payload", "updated_at"])


def finish_native_tree(job):
    """Bound directory finalization independently of the already completed file transfers."""
    destination = resolve_location(
        job.destination_path,
        job.actor,
        space_id=job.payload["destination"]["space"],
        destination=True,
    )
    if destination.descriptor() != job.payload["destination"]:
        raise StorageWriteConflict("The destination root changed during transfer.")
    with ExitStack() as guards:
        for backend in sorted(
            {job.space.backend, destination.backend}, key=lambda value: str(value.namespace)
        ):
            guards.enter_context(namespace_guard(backend, exclusive=True))
        pending = job.copy_entries.filter(kind="folder").filter(
            Q(publication__moved__isnull=True) | Q(publication__moved=False)
        )
        for entry in pending.order_by("-created_at", "-pk")[:20]:
            source = _source(entry, job)
            _retain(entry, source, job)
            _publish(entry, job)
        if pending.exists():
            return "more"
        _finish(job)
        return "done"
