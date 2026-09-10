"""Bounded connectivity probes with sanitized results and generation fencing."""

from django.utils import timezone

from celery import shared_task

from core.models import StorageBackend, StorageSpace, User
from core.mounts.registry import get_mount_provider
from core.services.storage_connections import storage_for_backend
from core.services.storage_namespace import namespace_guard
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_resources import observe_resources
from core.services.storage_spaces import native_connection


@shared_task(soft_time_limit=30, time_limit=40)
def check_storage_connection(backend_id, generation):
    """An old probe cannot mark newly changed credentials as verified."""
    backend = StorageBackend.objects.filter(
        pk=backend_id, configuration_generation=generation
    ).first()
    if backend is None:
        return
    try:
        if backend.family == "s3":
            storage = storage_for_backend(backend)
            storage.connection.meta.client.head_bucket(Bucket=storage.bucket_name)
        else:
            mount = native_connection(backend)
            get_mount_provider(mount["provider"]).stat(mount=mount, normalized_path="/")
        status = "ready"
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        status = "unavailable"
    StorageBackend.objects.filter(pk=backend_id, configuration_generation=generation).update(
        connection_status=status,
        connection_checked_at=timezone.now(),
    )


@shared_task(soft_time_limit=30, time_limit=40)
def create_storage_root(space_id, actor_id):
    """Create only the configured root; repetition preserves an existing directory."""
    if not User.objects.filter(pk=actor_id, is_active=True, is_superuser=True).exists():
        raise StorageWriteConflict("Root creation is not authorized or supported.")
    space = StorageSpace.objects.select_related("backend").get(
        pk=space_id, backend__enabled=True, backend__family="mount"
    )
    backend = space.backend
    with namespace_guard(backend, exclusive=True, allow_maintenance=True):
        mount = {**native_connection(backend), "_deny_reparse": True}
        provider = get_mount_provider(mount["provider"])
        if not getattr(provider, "supports_virtual_roots", lambda **_: False)(mount=mount):
            raise StorageWriteConflict("Root creation is not authorized or supported.")
        provider.mkdirs(mount=mount, normalized_path=space.root_path)
        observe_resources(backend, [provider.stat(mount=mount, normalized_path=space.root_path)])
