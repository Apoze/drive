"""Queue large folder moves; the publication journal remains the recovery authority."""

import logging

from django.db import transaction

from core.models import StorageMoveJob
from core.mounts.providers import virtual
from core.mounts.providers.base import MountProviderError
from core.services import storage_quota as quota
from core.services.storage_namespace import StorageOperationBusy, advisory_guard
from core.services.storage_recovery import reconcile_operation
from core.services.storage_spaces import resolve_space_mount

from drive.celery_app import app

logger = logging.getLogger(__name__)


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


def dispatch_move(job_id):
    """A broker outage leaves a visible queued job, repaired by the scheduler."""
    try:
        app.send_task("core.tasks.storage.move_folder", args=[str(job_id)], retry=False)
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.warning("Storage move delivery deferred (job=%s).", job_id)


def execute_move(job_id):
    """Only one worker may process or recover a job, including after redelivery."""
    try:
        with advisory_guard(f"storage-move:{job_id}"):
            return _execute_move(job_id)
    except StorageOperationBusy:
        return "busy"


def _execute_move(job_id):
    job = StorageMoveJob.objects.select_related("actor", "operation").get(pk=job_id)
    if job.state in {"done", "failed"}:
        return job.state
    if job.operation_id:
        outcome = reconcile_operation(job.operation_id)
        if outcome in {"committed", "cancelled"}:
            job.state = "done" if outcome == "committed" else "failed"
            job.reason = (
                "" if outcome == "committed" else "The move was cancelled. Retry the request."
            )
        job.save(update_fields=["state", "reason", "updated_at"])
        return job.state
    job.state = "running"
    job.save(update_fields=["state", "updated_at"])
    try:
        mount = resolve_space_mount(job.space_id, job.actor)
        if not mount:
            raise quota.StorageWriteConflict("Access to this storage space was removed.")
        source = virtual.stat(mount=mount, normalized_path=job.source_path)
        if source.object_identity != job.source_identity:
            raise quota.StorageWriteConflict("The source folder changed. Retry the request.")
        virtual.rename(
            mount=mount,
            src_normalized_path=job.source_path,
            dst_normalized_path=job.destination_path,
            job_id=job.pk,
        )
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        job.refresh_from_db()
        if job.operation_id:
            # Publication may have completed even when its reply was lost.
            job.state = "running"
            job.reason = "The move is being reconciled."
        elif isinstance(exc, StorageOperationBusy):
            job.state = "queued"
            job.reason = str(exc.detail)
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
        return "busy" if job.state == "queued" else job.state
    job.state = "done"
    job.reason = ""
    job.save(update_fields=["state", "reason", "updated_at"])
    return job.state
