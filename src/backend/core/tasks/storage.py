"""Periodic metadata reconciliation for configured storage connections."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from core.entitlements import get_entitlements_backend
from core.models import StorageAdminJob, StorageBackend, StorageMoveJob, StorageQuota, User
from core.services.storage_inventory import (
    refresh_organization_policy,
    refresh_policy,
    scan_backend,
)
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_recovery import (
    cleanup_candidates,
    cleanup_operation,
    reconcile_expired_operations,
    reconcile_operation,
)

from drive.celery_app import app


@app.on_after_finalize.connect
def _setup_periodic_tasks(sender, **kwargs):
    if getattr(settings, "STORAGE_GOVERNANCE_ENABLED", False):
        sender.add_periodic_task(
            settings.STORAGE_RECONCILIATION_INTERVAL_SECONDS,
            reconcile_storage.s(),
            name="storage_inventory",
            serializer="json",
        )


@app.task
def reconcile_storage():
    """Schedule each connection separately so an unavailable NAS cannot block another."""
    StorageBackend.objects.filter(
        connection_status="checking",
        connection_checked_at__lt=timezone.now() - timedelta(minutes=2),
    ).update(connection_status="unavailable")
    for job_id in (
        StorageAdminJob.objects.filter(state__in=["queued", "running"])
        .order_by("updated_at")
        .values_list("pk", flat=True)[:200]
    ):
        admin_operation.delay(str(job_id))
    for job_id in (
        StorageMoveJob.objects.filter(state__in=["queued", "running", "cleanup"])
        .order_by("updated_at")
        .values_list("pk", flat=True)[:200]
    ):
        move_folder.delay(str(job_id))
    for backend_id in StorageBackend.objects.filter(enabled=True, family="mount").values_list(
        "pk", flat=True
    ):
        reconcile_backend.delay(str(backend_id))
    for operation_id in reconcile_expired_operations():
        recover_operation.delay(str(operation_id))
    for operation_id in cleanup_candidates():
        clean_storage_operation.delay(str(operation_id))
    if callable(getattr(get_entitlements_backend(), "get_storage_policy", None)):
        for user_id in (
            User.objects.filter(is_active=True)
            .values_list("pk", flat=True)
            .iterator(chunk_size=200)
        ):
            synchronize_policy.delay(str(user_id))
    if callable(getattr(get_entitlements_backend(), "get_organization_storage_policy", None)):
        for organization in (
            StorageBackend.objects.filter(enabled=True)
            .order_by()
            .values_list("organization", flat=True)
            .distinct()
        ):
            synchronize_organization_policy.delay(organization)


@app.task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def acknowledge_policy(user_id, revision):
    """Only acknowledge the revision still present in Drive's committed ledger."""
    if StorageQuota.objects.filter(key=f"user:{user_id}", policy_revision=revision).exists():
        get_entitlements_backend().acknowledge_policy(User.objects.get(pk=user_id), revision)


@app.task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def acknowledge_organization_policy(organization, revision):
    """A shared space can be acknowledged without inventing a member account."""
    if StorageQuota.objects.filter(
        key=f"organization:{organization}", policy_revision=revision
    ).exists():
        get_entitlements_backend().get_organization_storage_policy(
            organization,
            policy_applied={"revision": revision, "applied_at": timezone.now().isoformat()},
        )


@app.task
def synchronize_policy(user_id):
    """Update idle users too, so a policy change need not wait for a new upload."""
    refresh_policy(User.objects.get(pk=user_id))


@app.task
def synchronize_organization_policy(organization):
    """Keep configured shared spaces synchronized independently of user activity."""
    refresh_organization_policy(organization)


@app.task
def recover_operation(operation_id):
    """Keep unavailable backends from blocking recovery on another connection."""
    return reconcile_operation(operation_id)


@app.task
def clean_storage_operation(operation_id):
    """Retry private multipart/staging cleanup without releasing uncertain writes."""
    return cleanup_operation(operation_id)


@app.task
def reconcile_backend(backend_id):
    """Never overlap a still-running inventory on the same connection."""
    try:
        scan_backend(backend_id)
    except StorageWriteConflict:
        pass


@app.task
def reclassify_storage(backend_id, actor_id):
    """Apply administrative root changes without blocking an HTTP request."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_tree_transfer import reclassify_backend  # noqa: PLC0415

    reclassify_backend(backend_id, actor_id)


@app.task(bind=True, max_retries=12)
def move_folder(self, job_id):
    """Retry live lock contention; durable jobs also survive missed broker delivery."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_move_job import execute_move  # noqa: PLC0415

    result = execute_move(job_id)
    if result == "more":
        # Yield a bounded manifest batch without consuming contention retries.
        self.apply_async(args=[job_id], countdown=1)
    if result == "busy":
        raise self.retry(countdown=5)
    return result


@app.task(bind=True, max_retries=12)
def admin_operation(self, job_id):
    """Retry live contention and retain a durable, user-visible completion state."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_admin_jobs import execute_admin_job  # noqa: PLC0415

    result = execute_admin_job(job_id)
    if result == "busy":
        raise self.retry(countdown=5)
    return result
