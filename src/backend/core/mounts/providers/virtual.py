"""Permission-bound views of existing filesystem providers."""

import posixpath
from contextlib import ExitStack, contextmanager, nullcontext
from dataclasses import replace

from core.models import StorageSpace
from core.mounts.providers.base import get_browser_stream_capabilities as stream_capabilities
from core.mounts.registry import get_mount_provider
from core.services import storage_inventory as inventory
from core.services import storage_mount_write
from core.services import storage_quota as quota
from core.services import storage_spaces as spaces
from core.services.storage_namespace import namespace_guard
from wopi.utils import compute_mount_entry_version


@contextmanager
def _target(mount, path, *, write=False, traverse=False):
    if any(part.startswith(".drive-txn-") for part in path.split("/")):
        raise spaces.denied()
    space, user, native = spaces.context(mount)
    mount["_browse_context"] = (space, user)
    path = spaces.authorize(space, user, path, write=write, traverse=traverse)
    provider = get_mount_provider(native["provider"])
    if not getattr(provider, "supports_virtual_roots", lambda **_: False)(mount=native):
        raise spaces.denied()
    native = {**native, "_deny_reparse": True}
    translated = spaces.native_path(space, path)
    confine = getattr(provider, "confine", None)
    guard = confine(mount=native, normalized_path=translated) if confine else nullcontext()
    with namespace_guard(space.backend) if write else nullcontext(), guard:
        yield space, user, provider, native, translated


def _virtual_entry(space, entry):
    root = space.root_path.rstrip("/")
    path = entry.normalized_path[len(root) :] or "/"
    return replace(entry, normalized_path=path, name=entry.name if path != "/" else "/")


def stat(*, mount, normalized_path):
    """Resolve a virtual entry after rechecking its current permissions."""
    with _target(mount, normalized_path, traverse=True) as (space, _, provider, native, path):
        return _virtual_entry(space, provider.stat(mount=native, normalized_path=path))


def list_children(*, mount, normalized_path):
    """Filter inaccessible children, retaining parents needed to reach granted paths."""
    with _target(mount, normalized_path, traverse=True) as (space, user, provider, native, path):
        entries = []
        for child in provider.list_children(mount=native, normalized_path=path):
            if child.name.startswith(".drive-txn-"):
                continue
            entry = _virtual_entry(space, child)
            try:
                spaces.authorize(space, user, entry.normalized_path, traverse=True)
            except spaces.MountProviderError:
                continue
            entries.append(entry)
        return entries


@contextmanager
def open_read(*, mount, normalized_path):
    """Keep both provider confinement and the authorized read alive for the stream."""
    with _target(mount, normalized_path) as (_, _, provider, native, path):
        with provider.open_read(mount=native, normalized_path=path) as stream:
            yield stream


def get_browser_stream_capabilities(*, mount):
    """Preserve the underlying provider streaming contract."""
    _, _, native = spaces.context(mount)
    return stream_capabilities(provider=get_mount_provider(native["provider"]), mount=native)


def can_write(*, mount, normalized_path):
    """Read-only editor capability; actual writes repeat authorization in _target."""
    space, user, _ = spaces.context(mount)
    if space.backend.maintenance:
        return False
    try:
        spaces.authorize(space, user, normalized_path, write=True)
    except spaces.MountProviderError:
        return False
    return True


def entry_abilities(*, mount, entry, abilities):
    """Use the request's resolved grants for each row without repeating DB queries."""
    context = mount.get("_browse_context")
    space, user = context if context else spaces.context(mount)[:2]
    result = dict(abilities)
    if space.backend.maintenance:
        for action in ("create_folder", "move", "rename", "destroy", "upload", "duplicate", "wopi"):
            result[action] = False
    try:
        spaces.authorize(space, user, entry.normalized_path, write=True)
    except spaces.MountProviderError:
        for action in ("create_folder", "move", "rename", "destroy", "upload", "duplicate"):
            result[action] = False
    try:
        spaces.authorize(space, user, entry.normalized_path, share=True)
    except spaces.MountProviderError:
        result["share_link_create"] = False
    return result


def authorize_share(*, mount, normalized_path):
    """Sharing a sibling grant cannot authorize sharing this particular file."""
    space, user, _ = spaces.context(mount)
    spaces.authorize(space, user, normalized_path, share=True)


def write_stream(*, mount, final_path, chunks, limits=None, must_be_missing=False):
    """Authorize the target before delegating accounting and publication."""
    with _target(mount, final_path, write=True) as (space, user, provider, native, path):
        return storage_mount_write.write_stream(
            space=space,
            actor=user,
            provider=provider,
            mount=native,
            path=path,
            chunks=chunks,
            limits=limits,
            must_be_missing=must_be_missing,
        )


def _protect_roots(space, path):
    canonical = posixpath.join(space.backend.namespace_root, path.lstrip("/"))
    for root in StorageSpace.objects.select_related("backend").filter(
        backend__namespace=space.backend.namespace
    ):
        configured = posixpath.join(root.backend.namespace_root, root.root_path.lstrip("/"))
        if spaces.within(configured, canonical):
            raise quota.StorageWriteConflict(
                "Storage roots must be changed through storage administration."
            )


def mkdirs(*, mount, normalized_path):
    """Create a directory only within the caller's writable grant."""
    with _target(mount, normalized_path, write=True) as (space, user, provider, native, path):
        provider.mkdirs(mount=native, normalized_path=path)
        inventory.observe_entry(
            space.backend, provider.stat(mount=native, normalized_path=path), actor=user
        )


def remove(*, mount, normalized_path):
    """Account a deletion only after the provider confirms it."""
    with _target(mount, normalized_path, write=True) as (space, user, provider, native, path):
        _protect_roots(space, path)
        entry = provider.stat(mount=native, normalized_path=path)
        if entry.entry_type == "folder":
            _remove_empty_folder(space, user, provider, native, path, entry)
            return
        usage = inventory.observe_entry(space.backend, entry)
        operation = quota.admit(
            key=usage.key,
            actor=user,
            size=0,
            publication_key=quota.resource_key(f"path:{space.backend.namespace}:{usage.path}"),
        )
        quota.begin_publication(
            operation.pk,
            observed_version=compute_mount_entry_version(entry),
            size=0,
            publication={"kind": "delete", "backend_id": str(space.backend_id), "path": path},
        )
        provider.remove(mount=native, normalized_path=path)
        quota.commit(operation.pk, size=0, version="missing")


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _remove_empty_folder(space, user, provider, native, path, entry):  # noqa: PLR0913
    """Retained private copies must not prevent deleting an otherwise empty folder."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_tree_transfer import (  # noqa: PLC0415
        ensure_subtree_idle,
        relocate_recovery_paths,
    )

    with namespace_guard(space.backend, exclusive=True):
        ensure_subtree_idle(space.backend, path)
        children = provider.list_children(mount=native, normalized_path=path)
        if any(not child.name.startswith(".drive-txn-") for child in children):
            raise quota.StorageWriteConflict("The folder is not empty.")
        usage = inventory.observe_entry(space.backend, entry)
        operation = quota.admit(key=usage.key, actor=user, size=0)
        retained = (
            posixpath.join(posixpath.dirname(path), f".drive-txn-{operation.pk.hex}.deleted")
            if children
            else None
        )
        quota.begin_publication(
            operation.pk,
            observed_version=compute_mount_entry_version(entry),
            size=0,
            publication={
                "kind": "delete",
                "backend_id": str(space.backend_id),
                "path": path,
                "backup_path": retained,
                "backup_identity": entry.object_identity,
                "cleanup_pending": bool(retained),
                "source_path": path,
            },
        )
        if retained:
            provider.rename_no_replace(
                mount=native, src_normalized_path=path, dst_normalized_path=retained
            )
            operation.refresh_from_db()
            relocate_recovery_paths(operation)
        else:
            provider.remove(mount=native, normalized_path=path)
        quota.commit(operation.pk, size=0, version="missing")


# pylint: disable-next=too-many-locals
def rename(*, mount, src_normalized_path, dst_normalized_path, job_id=None):
    """Move a file after reserving any newly charged scope; never replace a target."""
    with ExitStack() as guards:
        source = guards.enter_context(_target(mount, src_normalized_path, write=True))
        target = guards.enter_context(_target(mount, dst_normalized_path, write=True))
        space, user, provider, native, src = source
        _, _, _, _, dst = target
        guards.enter_context(namespace_guard(space.backend, exclusive=True))
        _protect_roots(space, src)
        original = provider.stat(mount=native, normalized_path=src)
        if original.entry_type == "folder":
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_tree_transfer import move_tree  # noqa: PLC0415

            move_tree(
                space=space,
                actor=user,
                provider=provider,
                mount=native,
                source=original,
                destination_path=dst,
                job_id=job_id,
            )
            return
        usage = inventory.observe_entry(space.backend, original)
        parent = provider.stat(mount=native, normalized_path=posixpath.dirname(dst))
        parent_usage = inventory.observe_entry(space.backend, parent)
        destination = inventory.mount_record(
            space.backend,
            replace(original, normalized_path=dst, object_identity=None),
            actor=usage.owner or user,
            lookup_existing=False,
            canonical_path=posixpath.join(parent_usage.path, posixpath.basename(dst)),
        )
        inventory.refresh_policy(destination["owner"] or user)
        operation = quota.admit(
            key=usage.key,
            actor=user,
            size=usage.size,
            target_scopes=destination["scope_keys"],
            publication_key=quota.resource_key(
                f"path:{space.backend.namespace}:{destination['path']}"
            ),
        )
        quota.begin_publication(
            operation.pk,
            observed_version=compute_mount_entry_version(original),
            size=usage.size,
            publication={
                "kind": "move",
                "backend_id": str(space.backend_id),
                "source_path": src,
                "path": dst,
                "source_identity": original.object_identity,
                "target_attribution": {
                    "path": destination["path"],
                    "organization": destination["organization"],
                    "owner_id": str(destination["owner"].pk) if destination["owner"] else None,
                    "space_id": str(destination["space"].pk) if destination["space"] else None,
                },
            },
        )
        provider.rename_no_replace(mount=native, src_normalized_path=src, dst_normalized_path=dst)
        final = provider.stat(mount=native, normalized_path=dst)
        if final.object_identity != original.object_identity:
            raise quota.StorageWriteConflict("Move outcome requires reconciliation.")
        quota.commit(operation.pk, size=usage.size, version=compute_mount_entry_version(final))
