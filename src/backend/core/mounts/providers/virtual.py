"""Permission-bound views of existing filesystem providers."""

import posixpath
from contextlib import ExitStack, contextmanager, nullcontext
from dataclasses import replace

from django.db import transaction
from django.db.models.functions import Lower

from core.models import StorageCopyEntry, StorageMoveJob, StorageSpace
from core.mounts.providers.base import MountEntry, MountProviderError
from core.mounts.providers.base import get_browser_stream_capabilities as stream_capabilities
from core.mounts.registry import get_mount_provider
from core.services import storage_inventory as inventory
from core.services import storage_mount_write
from core.services import storage_quota as quota
from core.services import storage_spaces as spaces
from core.services.mount_write_transaction import same_mount_entry
from core.services.storage_namespace import namespace_guard
from wopi.services.lock import guard_mount_editors
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


def list_children_page(*, mount, normalized_path, offset, limit):
    """Page the reconciled namespace index without scanning a whole native folder."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_resources import mounted_queryset, space_root  # noqa: PLC0415

    space, user, _ = spaces.context(mount)
    if not space.backend.inventory_completed_at:
        raise MountProviderError(
            failure_class="mount.inventory.not_ready",
            next_action_hint="Ask an administrator to initialize this storage inventory.",
            public_message="This storage needs its initial inventory before browsing.",
            public_code="mount.inventory.not_ready",
        )
    spaces.authorize(space, user, normalized_path, traverse=True)
    mount["_browse_context"] = (space, user)
    root = space_root(space)
    path = posixpath.normpath(posixpath.join(root, normalized_path.lstrip("/")))
    rows = (
        mounted_queryset(space, user, traverse=True)
        .filter(parent_path=path)
        .exclude(path=path)
        .annotate(order_name=Lower("name"))
        .order_by("-kind", "order_name", "path")
    )
    return rows.count(), [
        MountEntry(
            entry_type=row.kind,
            normalized_path=row.path[len(root.rstrip("/")) :] or "/",
            name=row.name,
            size=row.size,
            modified_at=row.modified_at,
            object_identity=row.provider_identity,
        )
        for row in rows[offset : offset + limit]
    ]


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


def supports_virtual_roots(*, mount):
    """Expose the same confinement guarantee as the underlying native connection."""
    _, _, native = spaces.context(mount)
    provider = get_mount_provider(native["provider"])
    return getattr(provider, "supports_virtual_roots", lambda **_: False)(mount=native)


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
        for action in (
            "create_folder",
            "move",
            "rename",
            "destroy",
            "upload",
            "duplicate",
            "convert",
            "wopi",
        ):
            result[action] = False
    try:
        spaces.authorize(space, user, entry.normalized_path, write=True)
    except spaces.MountProviderError:
        for action in (
            "create_folder",
            "move",
            "rename",
            "destroy",
            "upload",
            "duplicate",
            "convert",
        ):
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


# The virtual adapter forwards the protected writer's optional observation.
# pylint: disable-next=too-many-arguments
def write_stream(  # noqa: PLR0913
    *,
    mount,
    final_path,
    chunks,
    limits=None,
    must_be_missing=False,
    expected_entry=None,
    job_id=None,
    copy_job_id=None,
    move_job_id=None,
    source_check=None,
):
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
            expected_entry=expected_entry,
            job_id=job_id,
            copy_job_id=copy_job_id,
            move_job_id=move_job_id,
            source_check=source_check,
        )


def _protect_roots(space, path):
    canonical = spaces.namespace_path(space.backend, path)
    for root in StorageSpace.objects.select_related("backend").filter(
        backend__namespace=space.backend.namespace
    ):
        configured = spaces.namespace_path(root.backend, root.root_path)
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


def remove(*, mount, normalized_path, folder_entry_id=None):
    """Account a deletion only after the provider confirms it."""
    with _target(mount, normalized_path, write=True) as (space, user, provider, native, path):
        _protect_roots(space, path)
        entry = provider.stat(mount=native, normalized_path=path)
        if entry.entry_type == "folder":
            _remove_empty_folder(
                space, user, provider, native, path, entry, folder_entry_id=folder_entry_id
            )
            return
        _retain_deletion(space, user, provider, native, path, entry)


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _retain_deletion(  # noqa: PLR0913
    space, user, provider, native, path, entry, *, folder_entry_id=None, docs_anchor=None
):
    """Atomically quarantine the source; never unlink a path an external client replaced."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_recovery import finish_mount_deletion  # noqa: PLC0415

    if not entry.object_identity or not callable(getattr(provider, "rename_no_replace", None)):
        raise quota.StorageWriteConflict("This storage cannot safely retain a deleted resource.")
    usage = inventory.observe_entry(space.backend, entry)
    with transaction.atomic():
        operation = quota.admit(
            key=usage.key,
            actor=user,
            size=0,
            publication_key=quota.resource_key(f"path:{space.backend.namespace}:{usage.path}"),
        )
        retained = posixpath.join(posixpath.dirname(path), f".drive-txn-{operation.pk.hex}.deleted")
        publication = {
            "kind": "delete",
            "backend_id": str(space.backend_id),
            "path": path,
            "backup_path": retained,
            "backup_identity": entry.object_identity,
            "backup_version": compute_mount_entry_version(entry),
            "source_path": path,
            "source_kind": entry.entry_type,
            "cleanup_pending": True,
        }
        if docs_anchor:
            publication["docs_anchor"] = docs_anchor
            publication["namespace"] = str(space.backend.namespace)
        if folder_entry_id:
            folder_entry = StorageCopyEntry.objects.select_for_update().get(
                pk=folder_entry_id, job__actor=user
            )
            folder_entry.publication = {
                **folder_entry.publication,
                "source_operation": str(operation.pk),
            }
            folder_entry.save(update_fields=["publication", "updated_at"])
            publication["folder_job_id"] = str(folder_entry.job_id)
        quota.begin_publication(
            operation.pk,
            observed_version=compute_mount_entry_version(entry),
            size=0,
            publication=publication,
        )
    provider.rename_no_replace(mount=native, src_normalized_path=path, dst_normalized_path=retained)
    operation.refresh_from_db()
    backup = provider.stat(mount=native, normalized_path=retained)
    if backup.object_identity != entry.object_identity or compute_mount_entry_version(
        backup
    ) != compute_mount_entry_version(entry):
        raise quota.StorageWriteConflict(
            "The source changed during deletion; the retained copy requires reconciliation."
        )
    finish_mount_deletion(operation, space.backend)


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _remove_empty_folder(  # noqa: PLR0913
    space, user, provider, native, path, entry, *, folder_entry_id=None
):
    """Retained private copies must not prevent deleting an otherwise empty folder."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_tree_transfer import (  # noqa: PLC0415
        ensure_subtree_idle,
    )

    with namespace_guard(space.backend, exclusive=True):
        ensure_subtree_idle(space.backend, path)
        children = provider.iter_children(mount=native, normalized_path=path)
        if any(not child.name.startswith(".drive-txn-") for child in children):
            raise quota.StorageWriteConflict("The folder is not empty.")
        from core.services.docs_anchors import prepare_folder_deletion  # noqa: PLC0415

        docs_anchor = prepare_folder_deletion(
            space.backend, spaces.namespace_path(space.backend, path), user
        )
        _retain_deletion(
            space,
            user,
            provider,
            native,
            path,
            entry,
            folder_entry_id=folder_entry_id,
            docs_anchor=docs_anchor,
        )


@contextmanager
def _native_move_destination(source, target):
    """Pin an alias target and verify both credentials resolve the same directory."""
    space, _, provider, native, _ = source
    target_space, _, target_provider, target_native, path = target
    if target_space.backend_id == space.backend_id:
        yield path
        return
    canonical = spaces.namespace_path(target_space.backend, path)
    if not spaces.within(canonical, space.backend.namespace_root):
        raise quota.StorageWriteConflict("The source connection cannot reach this target.")
    target_parent = target_provider.stat(
        mount=target_native, normalized_path=posixpath.dirname(path)
    )
    relative = posixpath.relpath(canonical, space.backend.namespace_root)
    path = "/" if relative == "." else "/" + relative
    confine = getattr(provider, "confine", None)
    with confine(mount=native, normalized_path=path) if confine else nullcontext():
        native_parent = provider.stat(mount=native, normalized_path=posixpath.dirname(path))
        if not target_parent.object_identity or (
            native_parent.object_identity != target_parent.object_identity
        ):
            raise quota.StorageWriteConflict("These connections do not expose the same target.")
        yield path


# pylint: disable-next=too-many-locals
def rename(*, mount, src_normalized_path, dst_normalized_path, job_id=None, destination_mount=None):
    """Move a file after reserving any newly charged scope; never replace a target."""
    with ExitStack() as guards:
        source = guards.enter_context(_target(mount, src_normalized_path, write=True))
        target = guards.enter_context(
            _target(destination_mount or mount, dst_normalized_path, write=True)
        )
        space, user, provider, native, src = source
        target_space, target_user, _, _, _ = target
        if target_space.backend.namespace != space.backend.namespace or target_user.pk != user.pk:
            raise quota.StorageWriteConflict("A native move needs the same storage namespace.")
        guards.enter_context(namespace_guard(space.backend, exclusive=True))
        dst = guards.enter_context(_native_move_destination(source, target))
        _protect_roots(space, src)
        guard_mount_editors(space.backend, src)
        original = provider.stat(mount=native, normalized_path=src)
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_resources import bind_legacy_shares  # noqa: PLC0415

        bind_legacy_shares(space.backend, src)
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
        inventory.refresh_policy(
            destination["owner"] or user, organization=destination["organization"]
        )
        with transaction.atomic():
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
                    "source_version": compute_mount_entry_version(original),
                    "target_attribution": {
                        "path": destination["path"],
                        "organization": destination["organization"],
                        "owner_id": str(destination["owner"].pk) if destination["owner"] else None,
                        "space_id": str(destination["space"].pk) if destination["space"] else None,
                    },
                },
            )
            if job_id:
                StorageMoveJob.objects.filter(pk=job_id, actor=user).update(operation=operation)
        latest = provider.stat(mount=native, normalized_path=src)
        if not same_mount_entry(original, latest):
            quota.cancel(operation.pk, publication_ruled_out=True)
            raise quota.StorageWriteConflict("The source changed before the move.")
        provider.rename_no_replace(mount=native, src_normalized_path=src, dst_normalized_path=dst)
        final = provider.stat(mount=native, normalized_path=dst)
        if not same_mount_entry(original, final):
            raise quota.StorageWriteConflict("Move outcome requires reconciliation.")
        with transaction.atomic():
            quota.commit(operation.pk, size=usage.size, version=compute_mount_entry_version(final))
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_resources import observe_resources  # noqa: PLC0415

            observe_resources(space.backend, [final])
