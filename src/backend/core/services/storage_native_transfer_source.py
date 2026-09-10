"""Retain a native transfer source under its original permissions and identity."""

import posixpath
from contextlib import contextmanager, nullcontext

from core.models import StorageBackend
from core.mounts.providers import virtual
from core.mounts.registry import get_mount_provider
from core.services import storage_inventory as inventory
from core.services.storage_integrity import verify_mount_digest
from core.services.storage_mount_write import _stat_or_none
from core.services.storage_namespace import namespace_guard
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_resources import bind_legacy_shares
from core.services.storage_spaces import (
    authorize,
    context,
    namespace_path,
    native_connection,
    resolve_space_mount,
)
from wopi.services.lock import guard_mount_editors
from wopi.utils import compute_mount_entry_version


@contextmanager
def retained_source_context(job):
    """Authorize the original grant, then pin the journaled private copy after parent moves."""
    descriptor = job.payload["source"]
    mount = resolve_space_mount(descriptor["space"], job.actor)
    if not mount:
        raise StorageWriteConflict("Source write permission was removed.")
    space, actor, _ = context(mount)
    authorize(space, actor, descriptor["path"], write=True)
    if (
        str(space.backend_id) != descriptor["backend"]
        or space.backend.configuration_generation != descriptor["generation"]
    ):
        raise StorageWriteConflict("The original source connection changed.")
    publication = job.operation.publication
    info = publication.get("native_source") or publication
    backend = StorageBackend.objects.get(pk=info["backend_id"], enabled=True)
    if backend.namespace != space.backend.namespace or backend.configuration_generation != info.get(
        "retained_generation", descriptor["generation"]
    ):
        raise StorageWriteConflict("The retained source connection changed.")
    native = {**native_connection(backend), "_deny_reparse": True}
    provider = get_mount_provider(native["provider"])
    confine = getattr(provider, "confine", None)
    if not getattr(provider, "supports_virtual_roots", lambda **_: False)(mount=native):
        raise StorageWriteConflict("Protected retained-file access is unavailable.")
    guard = (
        # Registry modules are checked for callability above; localfs confines each operation.
        # pylint: disable-next=not-callable
        confine(mount=native, normalized_path=info["backup_path"])
        if callable(confine)
        else nullcontext()
    )
    with namespace_guard(backend, exclusive=True), guard:
        yield provider, native, info


def verify_retained_source(job, provider, mount, info):
    """Only the exact captured inode/version may be collected, even under a renamed parent."""
    entry = _stat_or_none(provider, mount, info["backup_path"])
    if entry:
        if (
            entry.object_identity != info["backup_identity"]
            or compute_mount_entry_version(entry)
            != info.get("source_version", info.get("source_observed_version"))
            or entry.size != info["backup_size"]
        ):
            raise StorageWriteConflict("The retained source changed.")
        verify_mount_digest(
            provider, mount, info["backup_path"], entry, job.operation.publication["sha256"]
        )
    return entry


@contextmanager
def source_context(job):
    """Confinement and current source write access remain required after relocation."""
    descriptor = job.payload["source"]
    mount = resolve_space_mount(descriptor["space"], job.actor)
    if not mount:
        raise StorageWriteConflict("Source write permission was removed.")
    # Reuse the virtual provider's pinned parent and authorization boundary.
    # pylint: disable-next=protected-access
    with virtual._target(mount, descriptor["path"], write=True) as target:  # noqa: SLF001
        space, _, _, _, path = target
        if (
            str(space.backend_id) != descriptor["backend"]
            or space.backend.configuration_generation != descriptor["generation"]
        ):
            raise StorageWriteConflict("The source connection changed.")
        info = job.payload.get("native_source")
        if info and (
            str(space.backend.namespace) != info["namespace"]
            or namespace_path(space.backend, path) != info["canonical_path"]
        ):
            raise StorageWriteConflict("The source namespace changed.")
        guard_mount_editors(space.backend, path)
        yield target


def prepare_source(job):
    """Observe the source charge and persist its private sibling before publication."""
    with source_context(job) as (space, _, provider, mount, path):
        if not callable(getattr(provider, "rename_no_replace", None)):
            raise StorageWriteConflict("This storage cannot safely retain the source.")
        entry = provider.stat(mount=mount, normalized_path=path)
        expected = job.payload["observation"]
        if (
            entry.entry_type != "file"
            or entry.object_identity != expected["identity"]
            or compute_mount_entry_version(entry) != expected["version"]
        ):
            raise StorageWriteConflict("The source changed before admission.")
        usage = inventory.observe_entry(space.backend, entry)
        bind_legacy_shares(space.backend, path)
        job.payload = {
            **job.payload,
            "native_source": {
                "backend_id": str(space.backend_id),
                "namespace": str(space.backend.namespace),
                "canonical_path": namespace_path(space.backend, path),
                "path": path,
                "source_kind": "file",
                "backup_size": int(entry.size or 0),
                "backup_path": posixpath.join(
                    posixpath.dirname(path), f".drive-txn-{job.pk.hex}.moved"
                ),
                "backup_identity": entry.object_identity,
                "source_version": compute_mount_entry_version(entry),
                "usage_key": usage.key,
            },
        }
        job.save(update_fields=["payload", "updated_at"])
        return usage


def check_source(job, *, retain=False):
    """Verify the original or retained object; never adopt a replacement at its old path."""
    info = job.payload["native_source"]
    with source_context(job) as (_, _, provider, mount, path):
        retained = _stat_or_none(provider, mount, info["backup_path"])
        entry = retained or provider.stat(mount=mount, normalized_path=path)
        if (
            entry.object_identity != info["backup_identity"]
            or compute_mount_entry_version(entry) != info["source_version"]
            or entry.size != info["backup_size"]
        ):
            raise StorageWriteConflict("The source changed; both locations were retained.")
        if retain:
            if retained is None:
                provider.rename_no_replace(
                    mount=mount,
                    src_normalized_path=path,
                    dst_normalized_path=info["backup_path"],
                )
                entry = provider.stat(mount=mount, normalized_path=info["backup_path"])
                if (
                    entry.object_identity != info["backup_identity"]
                    or compute_mount_entry_version(entry) != info["source_version"]
                ):
                    raise StorageWriteConflict("The retained source changed.")
            verify_mount_digest(
                provider,
                mount,
                info["backup_path"],
                entry,
                job.operation.publication["sha256"],
            )
        return entry
