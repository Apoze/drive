"""Services for the WOPI lock operations."""

import posixpath
from contextlib import nullcontext
from uuid import UUID

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q

from core.models import Item, StorageMoveJob, StorageResource, StorageSpace
from core.services.storage_namespace import advisory_guard, namespace_guard
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_resources import space_root
from core.services.storage_spaces import within
from core.utils.no_leak import sha256_16


class LockService:
    """Service for the WOPI lock operations."""

    lock_timeout = settings.WOPI_LOCK_TIMEOUT
    lock_prefix = "wopi_lock"

    def __init__(self, item: Item):
        self.item = item

    @property
    def _lock_key(self):
        """Get the lock key for the item."""
        return f"{self.lock_prefix}:{self.item.id}"

    def lock(self, lock_value: str):
        """Lock the item."""
        if not self.item.storage_backend_id:
            cache.set(self._lock_key, lock_value, timeout=self.lock_timeout)
            return
        with advisory_guard(f"storage-editor:{self.item.pk}", shared=True):
            if StorageMoveJob.objects.filter(
                kind="s3_transfer", source_path=str(self.item.pk), state__in=["queued", "running"]
            ).exists():
                raise StorageWriteConflict("A storage transfer is in progress.")
            cache.set(self._lock_key, lock_value, timeout=self.lock_timeout)

    def get_lock(self, default: str = None):
        """Get the lock."""
        return cache.get(self._lock_key, default)

    def refresh_lock(self):
        """Refresh the lock."""
        cache.touch(self._lock_key, timeout=self.lock_timeout)

    def is_locked(self):
        """Check if the item is locked."""
        return self.get_lock() is not None

    def is_lock_valid(self, lock_value: str):
        """Check if the lock is valid."""
        return cache.get(self._lock_key) == lock_value

    def unlock(self):
        """Unlock the item."""
        cache.delete(self._lock_key)


def _legacy_mount_keys(path, spaces):
    for space in spaces:
        root = space_root(space).rstrip("/")
        if within(path, root or "/"):
            relative = path[len(root) :] or "/"
            yield f"wopi_mount_lock:{space.pk}:{sha256_16(relative)}"


def guard_mount_editors(backend, path):
    """Caller holds the namespace exclusively; check indexed files in bounded cache batches."""
    canonical = posixpath.normpath(posixpath.join(backend.namespace_root, path.lstrip("/")))
    spaces = list(
        StorageSpace.objects.select_related("backend").filter(backend__namespace=backend.namespace)
    )
    keys = []
    for resource in (
        StorageResource.objects.filter(
            Q(path=canonical) | Q(path__startswith=canonical.rstrip("/") + "/"),
            namespace=backend.namespace,
            kind="file",
            missing=False,
        )
        .only("pk", "path")
        .iterator(chunk_size=100)
    ):
        keys.extend(
            [f"wopi_mount_resource:{resource.pk}", *_legacy_mount_keys(resource.path, spaces)]
        )
        if len(keys) >= 100:
            if cache.get_many(keys):
                raise StorageWriteConflict(
                    "Close active editing sessions before moving this entry."
                )
            keys.clear()
    if keys and cache.get_many(keys):
        raise StorageWriteConflict("Close active editing sessions before moving this entry.")


class MountLockService:
    """Share one editor lock across authorized views of the same mounted resource."""

    lock_timeout = settings.WOPI_LOCK_TIMEOUT
    lock_prefix = "wopi_mount_lock"

    def __init__(self, *, mount_id: str, normalized_path: str):
        self.mount_id = str(mount_id or "").strip()
        self._path_hash = sha256_16(str(normalized_path or ""))
        self.backend = None
        self.resource = None
        self.legacy_keys = [f"{self.lock_prefix}:{self.mount_id}:{self._path_hash}"]
        if not settings.STORAGE_GOVERNANCE_ENABLED:
            return
        try:
            identity = UUID(self.mount_id)
        except ValueError:
            return
        space = StorageSpace.objects.select_related("backend").filter(pk=identity).first()
        if not space:
            return
        path = posixpath.normpath(posixpath.join(space_root(space), normalized_path.lstrip("/")))
        self.resource = StorageResource.objects.filter(
            namespace=space.backend.namespace, path=path, missing=False
        ).first()
        if not self.resource:
            raise StorageWriteConflict("Refresh the storage inventory before editing this file.")
        self.backend = space.backend
        spaces = StorageSpace.objects.select_related("backend").filter(
            backend__namespace=space.backend.namespace
        )
        self.legacy_keys = list(_legacy_mount_keys(path, spaces))

    @property
    def _lock_key(self):
        if self.resource:
            return f"wopi_mount_resource:{self.resource.pk}"
        return self.legacy_keys[0]

    def lock(self, lock_value: str):
        """Fence moves and other lock acquisitions; never replace another editor's lock."""
        with (
            namespace_guard(self.backend) if self.backend else nullcontext(),
            advisory_guard(f"editor-lock:{self._lock_key}"),
        ):
            existing = self.get_lock()
            if existing is not None and existing != lock_value:
                raise StorageWriteConflict("Another editing session holds this file's lock.")
            cache.set(self._lock_key, lock_value, timeout=self.lock_timeout)

    def get_lock(self, default=None):
        """Legacy alias locks remain effective until refreshed, released or expired."""
        values = cache.get_many([self._lock_key, *self.legacy_keys])
        return values.get(self._lock_key, next(iter(values.values()), default))

    def refresh_lock(self):
        """A legacy refresh also adopts the shared identity without clearing its old lease."""
        if (value := self.get_lock()) is not None:
            self.lock(value)
            for key in self.legacy_keys:
                cache.touch(key, timeout=self.lock_timeout)

    def is_locked(self):
        """Check all currently applicable aliases."""
        return self.get_lock() is not None

    def is_lock_valid(self, lock_value):
        """Validate the shared lease without exposing native paths."""
        return self.get_lock() == lock_value

    def unlock(self):
        """Release the matching lease across its old aliases too."""
        with advisory_guard(f"editor-lock:{self._lock_key}"):
            value = self.get_lock()
            keys = [self._lock_key, *self.legacy_keys]
            cache.delete_many(
                [key for key, current in cache.get_many(keys).items() if current == value]
            )
