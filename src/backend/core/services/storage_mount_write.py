"""Stage governed mount writes and retain originals until publication is confirmed."""

import posixpath
import time
import uuid

from django.conf import settings
from django.utils import timezone

from core.mounts.providers.base import MountEntry, MountProviderError
from core.services import storage_inventory as inventory
from core.services import storage_quota as quota
from core.services.mount_write_transaction import (
    MountWriteLimits,
    MountWriteResult,
    MountWriteTimeout,
    MountWriteTooLarge,
    cleanup_mount_temp,
    write_all,
)
from wopi.utils import compute_mount_entry_version


def _stat_or_none(provider, mount, path):
    try:
        return provider.stat(mount=mount, normalized_path=path)
    except MountProviderError as exc:
        if exc.public_code != "mount.path.not_found":
            raise
    return None


def _physical_window(provider, mount, required):
    """Check native free space, including staging; this is not an external lock."""
    reader = getattr(provider, "capacity", None)
    if not callable(reader):
        return max(required, 8 * 1024**2)
    capacity = reader(mount=mount)
    available = capacity.get("caller_available_bytes")
    if not isinstance(available, int) or isinstance(available, bool) or available < 0:
        raise quota.StorageWriteConflict("Storage free space could not be verified.")
    if available < required:
        raise quota.StorageWriteConflict("Storage has insufficient space for a safe save.")
    # Already written staging bytes are in the native measurement, not deducted twice.
    return min(available, max(required, 8 * 1024**2))


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _write_reserved_chunks(  # noqa: PLR0913
    *, stream, chunks, operation, owner, limits, provider, mount
):
    started = time.monotonic()
    size = 0
    refreshed = False
    physical_remaining = 0
    for chunk in chunks:
        if not chunk:
            continue
        size += len(chunk)
        if limits.max_bytes is not None and size > limits.max_bytes:
            raise MountWriteTooLarge()
        if limits.max_seconds is not None and time.monotonic() - started > limits.max_seconds:
            raise MountWriteTimeout()
        if size > operation.previous_size + operation.reserved_bytes:
            if not refreshed:
                inventory.refresh_policy(owner)
                refreshed = True
            operation = quota.extend(operation.pk, size=size, window_bytes=8 * 1024**2)
        if len(chunk) > physical_remaining:
            physical_remaining = _physical_window(provider, mount, len(chunk))
        write_all(stream, chunk)
        physical_remaining -= len(chunk)
    return size


def _staging_paths(path):
    stem = posixpath.join(posixpath.dirname(path), f".drive-txn-{uuid.uuid4().hex}")
    return f"{stem}.tmp", f"{stem}.backup"


# One ordered publication protocol retains its original and staging identities.
# pylint: disable-next=too-many-arguments,too-many-positional-arguments,too-many-statements,too-many-locals
def write_stream(  # noqa: PLR0913, PLR0915
    *, space, actor, provider, mount, path, chunks, limits=None, must_be_missing=False
):
    """Reserve growth in bounded windows; preserve the old file on every rejection."""
    backend = space.backend
    if (
        not backend.inventory_completed_at
        or (timezone.now() - backend.inventory_completed_at).total_seconds()
        > settings.STORAGE_INVENTORY_MAX_AGE_SECONDS
    ):
        raise quota.StorageWriteConflict("Refresh this storage inventory before writing.")
    if not callable(getattr(provider, "rename_no_replace", None)):
        raise quota.StorageWriteConflict("This provider does not support protected publication.")
    current = _stat_or_none(provider, mount, path)
    if must_be_missing and current:
        raise quota.StorageWriteConflict("The restoration destination already exists.")
    if current and current.entry_type != "file":
        raise quota.StorageWriteConflict()
    parent = provider.stat(mount=mount, normalized_path=posixpath.dirname(path))
    if not parent.object_identity or (current and not current.object_identity):
        raise quota.StorageWriteConflict("Protected writes require stable filesystem identities.")
    parent_usage = inventory.observe_entry(backend, parent)
    # Inventory records the canonical parent spelling and ownership. A path alias
    # cannot avoid a nested space's quota when addressed through a wider view.
    canonical_path = posixpath.join(parent_usage.path, posixpath.basename(path))
    entry = (
        current
        if current
        else MountEntry(
            entry_type="file",
            normalized_path=path,
            name=posixpath.basename(path),
            size=0,
        )
    )
    usage = inventory.observe_entry(backend, entry, actor=actor, canonical_path=canonical_path)
    if usage.attribution_conflict:
        raise quota.StorageWriteConflict("Resolve this file's storage attribution before writing.")
    operation = quota.admit(
        key=usage.key,
        actor=actor,
        size=usage.size,
        publication_key=quota.resource_key(f"path:{backend.namespace}:{usage.path}"),
    )
    temp, backup = _staging_paths(path)
    publication = {
        "kind": "mount",
        "backend_id": str(backend.pk),
        "path": path,
        "temp_path": temp,
        "backup_path": backup if current else None,
        "backup_identity": current.object_identity if current else None,
        "backup_size": int(current.size or 0) if current else 0,
        "cleanup_pending": True,
    }
    publishing = False
    try:
        operation = quota.record_staging(operation.pk, publication)
        with provider.open_write(mount=mount, normalized_path=temp) as stream:
            staged = provider.stat(mount=mount, normalized_path=temp)
            publication["staging_identity"] = staged.object_identity
            operation = quota.record_staging(operation.pk, publication)
            size = _write_reserved_chunks(
                stream=stream,
                chunks=chunks,
                operation=operation,
                owner=usage.owner or actor,
                limits=limits or MountWriteLimits(),
                provider=provider,
                mount=mount,
            )
        staged = provider.stat(mount=mount, normalized_path=temp)
        if staged.size != size or not staged.object_identity:
            raise quota.StorageWriteConflict("The stored size does not match the transfer.")
        latest = _stat_or_none(provider, mount, path)
        version = (
            compute_mount_entry_version(latest)
            if latest
            else ("missing" if current else compute_mount_entry_version(entry))
        )
        publication["staging_identity"] = staged.object_identity
        quota.begin_publication(
            operation.pk, observed_version=version, size=size, publication=publication
        )
        publishing = True
        if current:
            provider.rename_no_replace(
                mount=mount, src_normalized_path=path, dst_normalized_path=backup
            )
            saved = provider.stat(mount=mount, normalized_path=backup)
            if (
                compute_mount_entry_version(saved) != operation.expected_version
                or saved.object_identity != current.object_identity
            ):
                # Do not replace a file changed by a direct NAS writer. Restoration
                # is also no-clobber, so another newly created target is preserved.
                provider.rename_no_replace(
                    mount=mount, src_normalized_path=backup, dst_normalized_path=path
                )
                raise quota.StorageWriteConflict()
        provider.rename_no_replace(mount=mount, src_normalized_path=temp, dst_normalized_path=path)
        final = provider.stat(mount=mount, normalized_path=path)
        if final.size != size or final.object_identity != staged.object_identity:
            raise quota.StorageWriteConflict("Publication requires reconciliation.")
        identity = final.object_identity or f"path:{canonical_path}"
        quota.bind_native_identity(
            usage.key,
            provider_identity=identity,
            native_key=quota.resource_key(f"mount:{backend.namespace}:{identity}"),
        )
        quota.commit(operation.pk, size=size, version=compute_mount_entry_version(final))
        # Keep the backup recorded in the operation for recovery and physical-space
        # reporting. An external writer may still hold its old filesystem handle.
        return MountWriteResult(temp_path=temp, final_path=path, bytes_written=size)
    except Exception:
        if not publishing:
            cleanup_mount_temp(provider=provider, mount=mount, temp_path=temp)
            quota.cancel(operation.pk)
        # A failed RPC is not proof that a publication failed. Keep its reservation
        # and recovery paths until an observer establishes the actual outcome.
        raise
