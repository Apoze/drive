"""Queue large folder moves; the publication journal remains the recovery authority."""

import logging
import posixpath

from django.core.exceptions import ValidationError
from django.db import transaction

from rest_framework.exceptions import APIException
from suite_identity.access import request_proofs
from suite_identity.document_transport import document_links

from core.models import Item, ItemActivityActionChoices, StorageMoveJob
from core.mounts.providers import virtual
from core.mounts.providers.base import MountProviderError
from core.services import storage_quota as quota
from core.services.item_activity import record_item_activity
from core.services.storage_namespace import StorageOperationBusy, advisory_guard, namespace_guard
from core.services.storage_recovery import reconcile_operation
from core.services.storage_spaces import authorize, context, resolve_space_mount
from core.services.storage_transfer_location import resolve_location
from wopi.utils import compute_mount_entry_version

from drive.celery_app import app

logger = logging.getLogger(__name__)


# Each supported native transfer has an explicit recovery owner.
# pylint: disable-next=too-many-return-statements
def enqueue_transfer(*, actor, source, destination, mode="move", name=None, request_key=None):  # noqa: PLR0911, PLR0913
    """All entry points select the same native mechanism from resolved logical locations."""
    if source.kind == "docs":
        from core.services.docs_jobs import enqueue  # noqa: PLC0415

        return enqueue(actor, source, destination, mode=mode, request_key=request_key)
    if mode == "copy":
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_copy_job import enqueue_copy  # noqa: PLC0415

        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_folder_copy import enqueue_folder_copy  # noqa: PLC0415

        enqueue = enqueue_folder_copy if source.kind == "folder" else enqueue_copy
        return enqueue(actor=actor, source=source, destination=destination, name=name)
    if mode != "move":
        raise quota.StorageWriteConflict("Choose a copy or a move.")
    if source.kind == "folder" and (
        source.backend.family != destination.backend.family
        or (source.backend.family == "s3" and source.backend.pk != destination.backend.pk)
        or source.backend.namespace != destination.backend.namespace
    ):
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_folder_copy import enqueue_folder_copy  # noqa: PLC0415

        return enqueue_folder_copy(actor=actor, source=source, destination=destination, mode="move")
    if source.backend.family == "mount" and destination.backend.family == "s3":
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_mount_s3_transfer import enqueue_mount_s3_move  # noqa: PLC0415

        return enqueue_mount_s3_move(actor=actor, source=source, destination=destination)
    if (
        source.backend.family == "mount"
        and source.backend.namespace == destination.backend.namespace
    ):
        return enqueue_resource_move(actor=actor, source=source, destination=destination)
    if source.space.pk == destination.space.pk:
        return enqueue_item_move(actor=actor, source=source, destination=destination)
    if destination.backend.family != "s3":
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_native_transfer import enqueue_native_transfer  # noqa: PLC0415

        enqueue = enqueue_native_transfer
    elif source.kind == "folder" and source.backend.pk == destination.backend.pk:
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_item_tree_move import enqueue_item_tree_move  # noqa: PLC0415

        enqueue = enqueue_item_tree_move
    else:
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_file_transfer import enqueue_s3_transfer  # noqa: PLC0415

        return enqueue_s3_transfer(
            actor=actor, source=source.reference, destination=destination.reference
        )
    return enqueue(actor=actor, source=source, destination=destination)


def enqueue_move(*, actor, space_id, source, destination_path):
    """Persist intent before publishing to Celery; periodic retries repair delivery."""
    if not source.object_identity or source.entry_type != "folder":
        raise quota.StorageWriteConflict("The folder identity must be known before moving it.")
    job, _ = StorageMoveJob.objects.get_or_create(
        actor=actor,
        space_id=space_id,
        source_path=source.normalized_path,
        destination_path=destination_path,
        state__in=["queued", "running"],
        defaults={"source_identity": source.object_identity},
    )
    transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


def enqueue_resource_move(*, actor, source, destination):
    """Move stable mounted references between permitted views of one namespace."""
    if (
        source.backend.family != "mount"
        or destination.backend.family != "mount"
        or source.backend.namespace != destination.backend.namespace
    ):
        raise quota.StorageWriteConflict("These locations require a cross-storage transfer.")
    space, user, _ = context(source.mount)
    authorize(space, user, source.path, write=True)
    observed = virtual.stat(mount=source.mount, normalized_path=source.path)
    if not observed.object_identity:
        raise quota.StorageWriteConflict("The source needs a stable identity before moving.")
    path = posixpath.join(destination.path, source.name)
    job, created = StorageMoveJob.objects.get_or_create(
        actor=actor,
        kind="native_resource_move",
        space=source.space,
        source_path=source.path,
        destination_path=path,
        state__in=["queued", "running", "conflict"],
        defaults={
            "source_identity": observed.object_identity,
            "payload": {
                "title": source.name,
                "destination_title": destination.name,
                "source": source.descriptor(),
                "destination": destination.descriptor(),
                "source_version": compute_mount_entry_version(observed),
            },
        },
    )
    if not created and job.payload.get("destination") != destination.descriptor():
        raise quota.StorageWriteConflict("Recover the existing move before changing its target.")
    transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


def _move_mounts(job):
    """Recheck both views even when publication moved the source out of its old view."""
    source_mount = resolve_space_mount(job.space_id, job.actor)
    if not source_mount:
        raise quota.StorageWriteConflict("Access to this storage space was removed.")
    if job.kind != "native_resource_move":
        return source_mount, source_mount
    for descriptor, path in (
        (job.payload["source"], job.source_path),
        (job.payload["destination"], job.destination_path),
    ):
        mount = resolve_space_mount(descriptor["space"], job.actor)
        if not mount:
            raise quota.StorageWriteConflict("Access to a transfer space was removed.")
        space, actor, _ = context(mount)
        if (
            str(space.backend_id) != descriptor["backend"]
            or space.backend.configuration_generation != descriptor["generation"]
        ):
            raise quota.StorageWriteConflict("The transfer connection configuration changed.")
        authorize(space, actor, path, write=True)
    target = resolve_location(
        job.payload["destination"]["id"],
        job.actor,
        space_id=job.payload["destination"]["space"],
        destination=True,
    )
    if target.descriptor() != job.payload["destination"]:
        raise quota.StorageWriteConflict("The destination folder changed.")
    return source_mount, target.mount


def enqueue_item_move(*, actor, source, destination):
    """Queue an ordinary same-space tree move without copying unchanged S3 objects."""
    if source.space.pk != destination.space.pk or not source.reference.get_abilities(actor).get(
        "move"
    ):
        raise quota.StorageWriteConflict("This item cannot be moved into the selected folder.")
    job, _ = StorageMoveJob.objects.get_or_create(
        actor=actor,
        kind="item_move",
        space=source.space,
        source_path=str(source.reference.pk),
        destination_path=str(destination.reference.pk),
        state__in=["queued", "running", "conflict"],
        defaults={
            "source_identity": str(source.reference.pk),
            "payload": {
                "source": source.descriptor(),
                "destination": destination.descriptor(),
                "title": source.name,
                "destination_title": destination.name,
            },
        },
    )
    transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


def _execute_item_move(job):
    """The tree change and final job state share one transaction, making retries idempotent."""
    if job.state in {"done", "failed", "conflict"}:
        return job.state
    try:
        job.actor.refresh_from_db()
        source = resolve_location(job.source_path, job.actor)
        with namespace_guard(source.backend, exclusive=True), transaction.atomic():
            for identity in sorted({job.source_path, job.destination_path}):
                Item.objects.select_for_update().get(pk=identity)
            source = resolve_location(job.source_path, job.actor)
            destination = resolve_location(job.destination_path, job.actor, destination=True)
            if (source.descriptor(), destination.descriptor()) != (
                job.payload["source"],
                job.payload["destination"],
            ):
                raise quota.StorageWriteConflict("An ordinary move location changed.")
            item, target = source.reference, destination.reference
            if not item.get_abilities(job.actor).get("move"):
                raise quota.StorageWriteConflict("The move permission was removed.")
            previous = item.parent() if item.depth > 1 else None
            item.move(target)
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_resources import revoke_item_tree_links  # noqa: PLC0415

            revoke_item_tree_links(item.path)
            record_item_activity(
                item=item,
                actor=job.actor,
                action=ItemActivityActionChoices.MOVED,
                payload={
                    "old_parent_id": str(previous.pk) if previous else None,
                    "old_parent_name": previous.title if previous else None,
                    "new_parent_id": str(target.pk),
                    "new_parent_name": target.title,
                },
            )
            job.state, job.reason = "done", ""
            job.save(update_fields=["state", "reason", "updated_at"])
        return "done"
    except StorageOperationBusy:
        return "busy"
    except (APIException, ValidationError):
        job.state, job.reason = (
            "failed",
            "The item could not be moved. Check its current permissions and destination.",
        )
        job.save(update_fields=["state", "reason", "updated_at"])
        return "failed"


def dispatch_move(job_id):
    """A broker outage leaves a visible queued job, repaired by the scheduler."""
    try:
        app.send_task("core.tasks.storage.move_folder", args=[str(job_id)], retry=False)
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.warning("Storage move delivery deferred (job=%s).", job_id)


def execute_move(job_id):
    """Only one worker may process or recover a job, including after redelivery."""
    # Celery has no HTTP middleware. Retain verified delegation within this
    # execution only, including nested transfers, and never across worker jobs.
    proof_token = request_proofs.set(dict(request_proofs.get() or {}))
    link_token = document_links.set(document_links.get())
    try:
        try:
            with advisory_guard(f"storage-move:{job_id}"):
                return _execute_move(job_id)
        except StorageOperationBusy:
            return "busy"
    finally:
        document_links.reset(link_token)
        request_proofs.reset(proof_token)


# Each durable family has its own recovery owner.
# pylint: disable-next=too-many-return-statements
def _execute_move(job_id):  # noqa: PLR0911
    job = StorageMoveJob.objects.select_related("actor", "operation").get(pk=job_id)
    if job.kind in {"docs_move", "docs_copy"}:
        from core.services.docs_jobs import execute  # noqa: PLC0415

        return execute(job)
    if job.payload.get("extraction_parent"):
        if job.state in {"done", "failed", "conflict"}:
            return job.state
        dispatch_move(job.payload["extraction_parent"])
        return "more"
    if job.payload.get("extract"):
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_extract import execute_extraction  # noqa: PLC0415

        return execute_extraction(job)
    if job.kind in {"s3_mount_transfer", "mount_mount_transfer"}:
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_native_transfer import execute_native_transfer  # noqa: PLC0415

        return execute_native_transfer(job)
    if job.kind == "mount_s3_transfer":
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_mount_s3_transfer import execute_mount_s3_move  # noqa: PLC0415

        return execute_mount_s3_move(job)
    if job.kind == "item_tree_move":
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_item_tree_move import execute_item_tree_move  # noqa: PLC0415

        return execute_item_tree_move(job)
    if job.kind == "item_move":
        return _execute_item_move(job)
    if job.kind in {"folder_copy", "folder_move"}:
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_folder_copy import execute_folder_copy  # noqa: PLC0415

        return execute_folder_copy(job)
    if job.kind == "file_copy":
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_copy_job import execute_copy  # noqa: PLC0415

        return execute_copy(job)
    if job.kind in {"s3_transfer", "s3_copy"}:
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_file_transfer import execute_s3_transfer  # noqa: PLC0415

        return execute_s3_transfer(job)
    return _execute_native_move(job)


def _execute_native_move(job):
    """Native moves own path publication and its accounting recovery."""
    if job.state in {"done", "failed", "conflict"}:
        return job.state
    job.state = "running"
    job.save(update_fields=["state", "updated_at"])
    try:
        job.actor.refresh_from_db()
        mount, destination_mount = _move_mounts(job)
        if job.operation_id:
            outcome = reconcile_operation(job.operation_id, move_job_id=job.pk)
            if outcome in {"committed", "cancelled", "uncertain"}:
                job.state = {"committed": "done", "cancelled": "failed", "uncertain": "conflict"}[
                    outcome
                ]
                job.reason = "" if outcome == "committed" else "The move needs verification."
            job.save(update_fields=["state", "reason", "updated_at"])
            return job.state
        source = virtual.stat(mount=mount, normalized_path=job.source_path)
        if source.object_identity != job.source_identity or (
            job.payload.get("source_version")
            and compute_mount_entry_version(source) != job.payload["source_version"]
        ):
            raise quota.StorageWriteConflict("The source folder changed. Retry the request.")
        virtual.rename(
            mount=mount,
            src_normalized_path=job.source_path,
            dst_normalized_path=job.destination_path,
            job_id=job.pk,
            destination_mount=destination_mount,
        )
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        job.refresh_from_db()
        if isinstance(exc, StorageOperationBusy):
            return "busy"
        if job.operation_id:
            # Publication may have completed even when its reply was lost.
            job.state = (
                "failed"
                if job.operation.state == "cancelled"
                else "conflict"
                if isinstance(exc, (APIException, MountProviderError))
                else "running"
            )
            job.reason = "The move is being reconciled."
        else:
            job.state = "failed"
            job.reason = (
                str(exc.detail)
                if isinstance(exc, (quota.StorageQuotaExceeded, quota.StorageWriteConflict))
                else exc.public_message
                if isinstance(exc, MountProviderError)
                else "The move could not be completed. Retry the request."
            )
        job.save(update_fields=["state", "reason", "updated_at"])
        return job.state
    job.state = "done"
    job.reason = ""
    job.save(update_fields=["state", "reason", "updated_at"])
    return job.state
