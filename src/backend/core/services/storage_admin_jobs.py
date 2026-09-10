"""Persist administrative intent and recover idempotent work after missed delivery."""

import logging

from django.db import transaction

from core.models import StorageAdminJob, StorageBackend, StorageSpace
from core.services.storage_namespace import StorageOperationBusy, advisory_guard, namespace_guard
from core.services.storage_quota import StorageQuotaExceeded, StorageWriteConflict, resource_key

from drive.celery_app import app

logger = logging.getLogger(__name__)


# Root provisioning and restoration both keep their explicit destination snapshot.
# pylint: disable-next=too-many-arguments
def enqueue_admin_job(  # noqa: PLR0913
    *, backend, actor, kind, space=None, source_operation=None, destination=None
):
    """Record a bounded target snapshot before asking the broker to run it."""
    if not actor.is_active or not actor.is_superuser:
        raise StorageWriteConflict("Storage administration requires an active administrator.")
    if kind not in {"inventory", "reclassify", "root", "restore"} or (
        kind in {"root", "restore"} and not space
    ):
        raise StorageWriteConflict("Unknown storage administration operation.")
    if space and space.backend_id != backend.pk:
        raise StorageWriteConflict("The space belongs to another connection.")
    if kind == "restore":
        if (
            not source_operation
            or source_operation.state != "committed"
            or not (
                source_operation.publication.get("native_source") or source_operation.publication
            ).get("backup_path")
            or not destination
            or backend.family != "mount"
        ):
            raise StorageWriteConflict("Choose a retained version and a filesystem destination.")
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.mounts.paths import normalize_mount_path  # noqa: PLC0415

        destination = normalize_mount_path(destination)
    request_key = resource_key(
        f"admin:{backend.pk}:{kind}:{space.pk if space else ''}:"
        f"{source_operation.pk if source_operation else ''}:{destination or ''}"
    )
    unresolved = StorageAdminJob.objects.filter(
        request_key=request_key,
        operation__state__in=["reserved", "writing", "publishing"],
    ).first()
    if unresolved:
        return unresolved
    job, _ = StorageAdminJob.objects.get_or_create(
        request_key=request_key,
        state__in=["queued", "running"],
        defaults={
            "backend": backend,
            "source_operation": source_operation,
            "actor": actor,
            "space": space,
            "kind": kind,
            "payload": {
                "generation": backend.configuration_generation,
                "requested_by": str(actor.pk),
                "root_path": space.root_path if space else None,
                "destination": destination,
            },
        },
    )
    transaction.on_commit(lambda: dispatch_admin_job(job.pk))
    return job


def dispatch_admin_job(job_id):
    """A broker failure leaves a visible request for the periodic repair pass."""
    try:
        app.send_task("core.tasks.storage.admin_operation", args=[str(job_id)], retry=False)
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.warning("Storage administration delivery deferred (job=%s).", job_id)


def execute_admin_job(job_id):
    """Every operation here can resume by observing its existing durable metadata."""
    try:
        with advisory_guard(f"storage-admin:{job_id}"):
            return _execute(job_id)
    except StorageOperationBusy:
        return "busy"


def _execute(job_id):
    job = StorageAdminJob.objects.select_related("backend", "space", "actor", "operation").get(
        pk=job_id
    )
    if job.state in {"done", "failed"}:
        return job.state
    try:
        with transaction.atomic():
            job.backend = StorageBackend.objects.select_for_update().get(pk=job.backend_id)
            if job.space_id:
                job.space = StorageSpace.objects.select_for_update().get(pk=job.space_id)
            space_changed = job.space_id and (job.space.backend_id, job.space.root_path) != (
                job.backend_id,
                job.payload["root_path"],
            )
            if (
                not job.actor.is_active
                or not job.actor.is_superuser
                or job.backend.configuration_generation != job.payload["generation"]
                or space_changed
            ):
                raise StorageWriteConflict("The administrator or storage configuration changed.")
            job.state, job.reason = "running", ""
            job.save(update_fields=["state", "reason", "updated_at"])
        _perform(job)
        job.state = "done"
    except StorageOperationBusy:
        job.state = "queued"
    except (StorageWriteConflict, StorageQuotaExceeded) as error:
        job.state, job.reason = "failed", str(error.detail)
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        # Native errors can contain paths or credentials. Keep them out of history.
        job.state, job.reason = (
            "failed",
            "Operation interrupted. Check storage availability and retry.",
        )
    job.save(update_fields=["state", "reason", "updated_at"])
    return "busy" if job.state == "queued" else job.state


def _perform(job):
    """Run existing storage services; each owns its native publication protocol."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_inventory import scan_backend  # noqa: PLC0415

    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_tree_transfer import (  # noqa: PLC0415
        finish_transfer,
        reclassify_backend,
    )

    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.tasks.storage_connections import create_storage_root  # noqa: PLC0415

    if job.kind == "inventory":
        scan_backend(job.backend_id)
    elif job.kind == "reclassify":
        # A crash after the final metadata commit has already left maintenance.
        if job.operation_id:
            with namespace_guard(
                job.backend, exclusive=True, recovery=True, allow_maintenance=True
            ):
                finish_transfer(job.operation_id, version=job.operation.expected_version)
        elif job.backend.maintenance:
            reclassify_backend(job.backend_id, job.actor_id, job_id=job.pk)
    elif job.kind == "root":
        create_storage_root(job.space_id, job.actor_id)
    else:
        _restore(job)


def _restore(job):
    """Recover a confirmed restoration without rereading or duplicating its source."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services import storage_quota as quota  # noqa: PLC0415

    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_recovery import (  # noqa: PLC0415
        _reconcile_mount,
        cleanup_operation,
        restore_backup,
    )

    if not job.operation_id:
        restore_backup(
            job.source_operation_id,
            space_id=job.space_id,
            actor_id=job.actor_id,
            destination=job.payload["destination"],
            job_id=job.pk,
        )
        return
    if job.operation.state == "committed":
        return
    if job.operation.state == "publishing":
        if _reconcile_mount(job.operation) != "committed":
            raise StorageWriteConflict("Restoration publication requires reconciliation.")
        return
    quota.cancel(job.operation_id)
    cleanup_operation(job.operation_id)
    raise StorageWriteConflict("Restoration interrupted before publication. Retry it.")
