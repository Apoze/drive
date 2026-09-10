"""Mounted metadata identities and authorization shared by catalogue and old routes."""

import posixpath
import secrets
import uuid
from dataclasses import replace

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Value
from django.db.models.functions import Concat, Substr
from django.utils import timezone

from rest_framework.exceptions import NotFound

from core.models import (
    Invitation,
    Item,
    ItemAccess,
    ItemActivity,
    ItemFavorite,
    LinkTrace,
    MountShareLink,
    RoleChoices,
    StorageGrant,
    StorageResource,
    StorageResourceFavorite,
    StorageSpace,
    StorageUsage,
)
from core.mounts.providers.base import MountProviderError
from core.mounts.registry import get_mount_provider
from core.services.storage_access import principal
from core.services.storage_quota import StorageWriteConflict, pending_native_paths, resource_key
from core.services.storage_spaces import (
    authorize,
    namespace_path,
    native_path,
    resolve_space_mount,
    within,
)
from core.utils.share_links import compute_item_share_token
from wopi.utils import compute_mount_entry_version


def transfer_item_links(item, space, path):
    """Move favorites, recents and an explicit public token to an existing native reference."""
    for favorite in ItemFavorite.objects.filter(item=item).iterator(chunk_size=100):
        StorageResourceFavorite.objects.update_or_create(
            user_id=favorite.user_id,
            resource_id=item.pk,
            defaults={"favorite": True, "space": space},
        )

    for trace in LinkTrace.objects.filter(item=item).iterator(chunk_size=100):
        StorageResourceFavorite.objects.update_or_create(
            user_id=trace.user_id,
            resource_id=item.pk,
            defaults={"last_opened_at": trace.updated_at, "space": space},
        )
    if item.link_reach == "public" and item.creator_id:
        MountShareLink.objects.get_or_create(
            token=compute_item_share_token(item.pk, item.share_link_nonce),
            defaults={
                "created_by_id": item.creator_id,
                "resource_id": item.pk,
                "mount_id": str(space.pk),
                "normalized_path": path,
            },
        )


def transfer_native_links(resource, item):
    """Retain favorites and recents when a mounted reference becomes a regular Item."""
    for favorite in StorageResourceFavorite.objects.filter(resource=resource).iterator(
        chunk_size=100
    ):
        if favorite.favorite:
            ItemFavorite.objects.get_or_create(user_id=favorite.user_id, item=item)
        if favorite.last_opened_at:
            trace, _ = LinkTrace.objects.get_or_create(user_id=favorite.user_id, item=item)
            LinkTrace.objects.filter(pk=trace.pk).update(updated_at=favorite.last_opened_at)
    StorageResourceFavorite.objects.filter(resource=resource).delete()
    revoke_incompatible_links(item.pk)


def transfer_staged_item_links(temporary, item):
    """Preserve user interactions with an S3 destination while its folder move was running."""
    item.refresh_from_db()
    if StorageSpace.objects.filter(root_item=temporary).exists():
        raise StorageWriteConflict("The destination became a storage-space root.")
    if Invitation.objects.filter(
        item=item, email__in=Invitation.objects.filter(item=temporary).values("email")
    ).exists():
        raise StorageWriteConflict(
            "Resolve duplicate invitations before finishing this folder move."
        )
    for favorite in ItemFavorite.objects.filter(item=temporary).iterator(chunk_size=100):
        ItemFavorite.objects.get_or_create(item=item, user_id=favorite.user_id)
    for recent in LinkTrace.objects.filter(item=temporary).iterator(chunk_size=100):
        retained, created = LinkTrace.objects.get_or_create(item=item, user_id=recent.user_id)
        if created or recent.updated_at > retained.updated_at:
            LinkTrace.objects.filter(pk=retained.pk).update(updated_at=recent.updated_at)
    for access in ItemAccess.objects.filter(item=temporary).iterator(chunk_size=100):
        retained, _ = ItemAccess.objects.get_or_create(
            item=item, user_id=access.user_id, team=access.team, defaults={"role": access.role}
        )
        role = RoleChoices.max(retained.role, access.role)
        if role != retained.role:
            retained.role = role
            retained.save(update_fields=["role", "updated_at"])
    Invitation.objects.filter(item=temporary).update(item=item)
    StorageGrant.objects.filter(root_item=temporary).update(root_item=item)
    ItemActivity.objects.filter(item=temporary).update(item=item)
    if temporary.link_reach == "public" and temporary.creator_id:
        # A missing sidecar retains an old token; regular bytes still resolve through Item/S3.
        reference, _ = StorageResource.objects.get_or_create(
            pk=item.pk,
            defaults={
                "namespace": item.storage_backend.namespace,
                "identity_key": resource_key(f"item-link:{item.pk}"),
                "path": str(item.path),
                "parent_path": str(item.path[:-1]),
                "name": item.title,
                "kind": "folder",
                "missing": True,
            },
        )
        MountShareLink.objects.get_or_create(
            token=compute_item_share_token(temporary.pk, temporary.share_link_nonce),
            defaults={
                "resource": reference,
                "created_by_id": temporary.creator_id,
                "mount_id": str(item.storage_space_id),
                "normalized_path": "/",
            },
        )

    revoke_incompatible_links(item.pk)


def revoke_item_tree_links(path):
    """Only explicitly shared rows need publication-time sharing checks."""
    shared = Item.objects.filter(path__descendants=path).filter(
        Q(link_reach__in=["public", "authenticated"])
        | Q(pk__in=MountShareLink.objects.values("resource_id"))
    )
    for item_id in shared.values_list("pk", flat=True).iterator(chunk_size=100):
        revoke_incompatible_links(item_id)


def revoke_incompatible_links(resource_id):
    """Run inside publication: incompatible tokens must never revive after a policy change."""
    item = (
        Item.objects.select_related("creator", "storage_space", "storage_backend")
        .filter(pk=resource_id)
        .first()
    )
    if item and item.link_reach in {"public", "authenticated"}:
        if not item.creator or not item.get_abilities(item.creator).get("link_configuration"):
            Item.objects.filter(pk=item.pk).update(
                link_reach="restricted", share_link_nonce=uuid.uuid4()
            )
    for link in (
        MountShareLink.objects.filter(resource_id=resource_id)
        .select_related("resource", "created_by")
        .iterator(chunk_size=100)
    ):
        try:
            if item:
                if not link.created_by or not item.get_abilities(link.created_by).get(
                    "link_configuration"
                ):
                    raise NotFound()
            else:
                shared_resource_location(link)
        except NotFound:
            link.delete()


def observe_resources(backend, entries, *, generation=None):
    """A bounded provider batch updates metadata, never byte ownership or file contents."""
    rows = {}
    now = timezone.now()
    entries = list(entries)
    pending = pending_native_paths(
        backend, [namespace_path(backend, entry.normalized_path) for entry in entries]
    )
    entries = [
        entry for entry in entries if namespace_path(backend, entry.normalized_path) not in pending
    ]
    identities = {}
    for entry in entries:
        path = namespace_path(backend, entry.normalized_path)
        identity = entry.object_identity or f"path:{path}"
        identities[entry.normalized_path] = resource_key(f"mount:{backend.namespace}:{identity}")
    logical = dict(
        StorageUsage.objects.filter(native_key__in=identities.values()).values_list(
            "native_key", "key"
        )
    )
    for entry in entries:
        path = namespace_path(backend, entry.normalized_path)
        identity = entry.object_identity or f"path:{path}"
        native_key = identities[entry.normalized_path]
        if entry.entry_type == "file" and native_key not in logical:
            # A file's attribution must be reconciled before publishing its reference.
            continue
        key = (
            resource_key(f"reference:{logical[native_key]}")
            if entry.entry_type == "file" and native_key in logical
            else native_key
        )
        rows[key] = StorageResource(
            namespace=backend.namespace,
            identity_key=key,
            provider_identity=identity,
            path=path,
            parent_path=posixpath.dirname(path.rstrip("/")) or "/",
            name=entry.name,
            kind=entry.entry_type,
            size=int(entry.size or 0),
            modified_at=entry.modified_at,
            version=compute_mount_entry_version(entry),
            generation=generation,
            missing=False,
            updated_at=now,
        )
    if rows:
        StorageResource.objects.bulk_create(
            list(rows.values()),
            update_conflicts=True,
            unique_fields=["identity_key"],
            update_fields=[
                "provider_identity",
                "path",
                "parent_path",
                "name",
                "kind",
                "size",
                "modified_at",
                "version",
                "generation",
                "missing",
                "updated_at",
            ],
        )


def space_root(space):
    """Canonical namespace path, independent of the credentials used by a view."""
    return namespace_path(space.backend, space.root_path)


def observe_virtual_entry(space, entry):
    """Translate a permitted view before registering its physical metadata identity."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_inventory import observe_entry  # noqa: PLC0415

    native_entry = replace(entry, normalized_path=native_path(space, entry.normalized_path))
    if entry.entry_type == "file":
        observe_entry(space.backend, native_entry)
    else:
        observe_resources(space.backend, [native_entry])


@transaction.atomic
def relocate_resources(operation):
    """A confirmed native folder rename updates indexed paths once without scanning files."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.models import StorageBackend, StorageReservation  # noqa: PLC0415

    operation = StorageReservation.objects.select_for_update().get(pk=operation.pk)
    info = operation.publication
    if info.get("kind") != "tree_move" or info.get("resources_relocated"):
        return
    backend = StorageBackend.objects.get(pk=info["backend_id"])
    source = namespace_path(backend, info["source_path"])
    target = namespace_path(backend, info["path"])
    entries = StorageResource.objects.filter(
        namespace=backend.namespace, created_at__lte=operation.created_at
    )
    entries.filter(path__startswith=source.rstrip("/") + "/").update(
        path=Concat(Value(target), Substr("path", len(source) + 1)),
        parent_path=Concat(Value(target), Substr("parent_path", len(source) + 1)),
        updated_at=timezone.now(),
    )
    entries.filter(path=source).update(
        path=target,
        parent_path=posixpath.dirname(target) or "/",
        name=posixpath.basename(target),
        updated_at=timezone.now(),
    )
    for resource_id in (
        entries.filter(Q(path=target) | Q(path__startswith=target.rstrip("/") + "/"))
        .filter(share_links__isnull=False)
        .values_list("pk", flat=True)
        .distinct()
        .iterator(chunk_size=100)
    ):
        revoke_incompatible_links(resource_id)
    if settings.DOCS_DRIVE_ENABLED:
        from core.models import DocsBinding  # noqa: PLC0415
        from core.services.docs_lifecycle import queue_change, queue_tree_changes  # noqa: PLC0415

        for binding in (
            DocsBinding.objects.filter(
                mounted_parent__in=entries.filter(
                    Q(path=target) | Q(path__startswith=target.rstrip("/") + "/")
                ),
            )
            .select_related("item__storageusage")
            .iterator(chunk_size=100)
        ):
            binding.anchor_space_id = binding.item.storageusage.space_id
            binding.save(update_fields=["anchor_space", "updated_at"])
            queue_change(binding.item)
            queue_tree_changes(binding.item)
    operation.publication = {**info, "resources_relocated": True}
    operation.save(update_fields=["publication", "updated_at"])


def visible_spaces(user):
    """Space discovery requires an actual grant; accounting ownership is not one."""
    if not user.is_authenticated or not user.is_active:
        return StorageSpace.objects.none()
    grants = Q(grants__user=user) | Q(grants__team__in=user.teams)
    legacy_owner = Q(explicit_access=False, owner=user)
    return (
        StorageSpace.objects.filter(
            grants | legacy_owner,
            enabled=True,
            backend__enabled=True,
        )
        .select_related("backend", "root_item")
        .distinct()
        .order_by("name", "id")
    )


def mounted_queryset(space, user, *, traverse=False):
    """Permissions are applied in SQL before search, pagination and counts."""
    root = space_root(space)
    queryset = StorageResource.objects.filter(
        namespace=space.backend.namespace, missing=False
    ).exclude(Q(name__startswith=".drive-txn-") | Q(path__contains="/.drive-txn-"))
    if not space.enabled or not space.backend.enabled:
        return queryset.none()
    if not space.explicit_access and space.owner_id == user.pk:
        return queryset.filter(Q(path=root) | Q(path__startswith=root.rstrip("/") + "/"))
    allowed = Q(pk__in=[])
    for grant in space.grants.filter(principal(user)):
        path = posixpath.normpath(posixpath.join(root, grant.path.lstrip("/")))
        allowed |= Q(path=path) | Q(path__startswith=path.rstrip("/") + "/")
        if traverse:
            parents = []
            while within(path, root):
                parents.append(path)
                if path == root:
                    break
                path = posixpath.dirname(path)
            allowed |= Q(path__in=parents)
    return queryset.filter(allowed)


def space_entrances(space, user):
    """Return accessible roots without making a subfolder grant expose its siblings."""
    if space.backend.family == "mount":
        return mounted_queryset(space, user, traverse=True).filter(path=space_root(space))
    grants = space.grants.filter(principal(user))
    roots = Q(pk__in=grants.exclude(root_item__isnull=True).values("root_item_id"))
    if grants.filter(root_item__isnull=True).exists() or (
        not space.explicit_access and space.owner_id == user.pk
    ):
        roots |= Q(pk=space.root_item_id)
    return Item.objects.filter(roots, type="folder", ancestors_deleted_at__isnull=True)


def item_entrances(user):
    """Visible S3 entrances, including historical files allocated as single-item spaces."""
    spaces = visible_spaces(user).filter(backend__family="s3")
    grants = StorageGrant.objects.filter(principal(user), space__in=spaces)
    whole = spaces.filter(
        Q(pk__in=grants.filter(root_item__isnull=True).values("space_id"))
        | Q(explicit_access=False, owner=user)
    )
    return Item.objects.filter(
        Q(pk__in=whole.values("root_item_id"))
        | Q(pk__in=grants.exclude(root_item__isnull=True).values("root_item_id")),
        ancestors_deleted_at__isnull=True,
        hard_deleted_at__isnull=True,
    )


def resolve_mounted(resource_id, space, user, *, write=False, share=False):
    """Resolve the current path of a stable reference, then recheck its current grant."""
    resource = (
        mounted_queryset(space, user, traverse=not (write or share)).filter(pk=resource_id).first()
    )
    if not resource:
        raise NotFound()
    root = space_root(space)
    path = resource.path[len(root.rstrip("/")) :] or "/"
    try:
        authorize(space, user, path, write=write, share=share, traverse=not (write or share))
        mount = resolve_space_mount(space.pk, user)
        entry = get_mount_provider("virtual").stat(mount=mount, normalized_path=path)
        if entry.object_identity and entry.object_identity != resource.provider_identity:
            # An external replacement is reconciled by inventory before receiving
            # a reference; a stale bookmark must never silently identify that file.
            raise NotFound()
        if not entry.object_identity and compute_mount_entry_version(entry) != resource.version:
            raise NotFound()
    except MountProviderError:
        raise NotFound() from None
    return resource, path


def resolve_resource_space(resource_id, user, preferred_space=None):
    """A bookmark follows its identity through whichever current view permits access."""
    resource = StorageResource.objects.filter(pk=resource_id, missing=False).first()
    if not resource:
        raise NotFound()
    spaces = visible_spaces(user).filter(backend__namespace=resource.namespace)
    preferred = spaces.filter(pk=preferred_space).first() if preferred_space else None
    if (
        preferred
        and mounted_queryset(preferred, user, traverse=True).filter(pk=resource_id).exists()
    ):
        resolve_mounted(resource_id, preferred, user)
        return resource, preferred
    for space in spaces.exclude(pk=preferred_space).iterator(chunk_size=100):
        if mounted_queryset(space, user, traverse=True).filter(pk=resource_id).exists():
            resolve_mounted(resource_id, space, user)
            return resource, space
    raise NotFound()


def shared_resource_location(link):
    """Follow the shared identity only through the creator's current shareable grants."""
    if not link.resource_id or not link.created_by_id:
        raise NotFound()
    spaces = visible_spaces(link.created_by).filter(
        backend__namespace=link.resource.namespace,
        allow_sharing=True,
    )
    for space in spaces.iterator(chunk_size=100):
        try:
            _, path = resolve_mounted(link.resource_id, space, link.created_by, share=True)
        except NotFound:
            continue
        return resolve_space_mount(space.pk, link.created_by), path
    raise NotFound()


def resource_for_virtual_path(mount, path, entry):
    """Bind a newly shared path to its reconciled resource, never to a future replacement."""
    space = StorageSpace.objects.select_related("backend").get(pk=mount["space_id"])
    observe_virtual_entry(space, entry)
    resource = StorageResource.objects.filter(
        namespace=space.backend.namespace,
        path=posixpath.normpath(posixpath.join(space_root(space), path.lstrip("/"))),
        missing=False,
    ).first()
    if not resource:
        raise NotFound()
    return resource


def bind_legacy_shares(backend, source):
    """Freeze old path-only links before a native rename can reuse their former paths."""
    canonical = posixpath.normpath(namespace_path(backend, source))
    for space in (
        StorageSpace.objects.select_related("backend")
        .filter(
            backend__namespace=backend.namespace,
        )
        .iterator(chunk_size=100)
    ):
        root = space_root(space)
        links = MountShareLink.objects.filter(mount_id=str(space.pk), resource__isnull=True)
        if within(canonical, root):
            relative = canonical[len(root.rstrip("/")) :] or "/"
            links = links.filter(
                Q(normalized_path=relative)
                | Q(normalized_path__startswith=relative.rstrip("/") + "/")
            )
        elif not within(root, canonical):
            continue
        for link in links.iterator(chunk_size=100):
            path = posixpath.normpath(posixpath.join(root, link.normalized_path.lstrip("/")))
            resource = StorageResource.objects.filter(
                namespace=backend.namespace,
                path=path,
                missing=False,
            ).first()
            if not resource:
                raise StorageWriteConflict(
                    "Run storage inventory before moving a legacy shared folder."
                )
            link.resource = resource
            link.save(update_fields=["resource", "updated_at"])


def shared_moved_item(link):
    """A mounted file link follows its UUID after S3 migration, under current sharing rights."""
    if not link.resource_id:
        return None
    item = (
        Item.objects.select_related("storage_backend", "storage_space")
        .filter(
            pk=link.resource_id,
        )
        .first()
    )
    if item is None or item.hard_deleted_at:
        return None
    actor = link.created_by
    if not actor or not actor.is_active:
        raise NotFound()
    if (
        item.hard_deleted_at
        or item.deleted_at
        or item.ancestors_deleted_at
        or (item.type == "file" and item.effective_upload_state() != "ready")
    ):
        raise NotFound()
    if not item.storage_space_id or not item.get_abilities(actor).get("link_configuration"):
        raise NotFound()
    return item


def create_resource_share(resource, actor, *, mount_id, path):
    """Create a link after the caller authorizes sharing of this stable reference."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_namespace import advisory_guard  # noqa: PLC0415

    with advisory_guard(f"resource-share:{resource.pk}:{actor.pk}"):
        previous = MountShareLink.objects.filter(resource=resource, created_by=actor).first()
        return previous or MountShareLink.objects.create(
            resource=resource,
            created_by=actor,
            mount_id=str(mount_id),
            normalized_path=path,
            token=secrets.token_urlsafe(32),
        )
