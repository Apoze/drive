"""Space grants bound existing Item permissions, including legacy file endpoints."""

from django.db.models import Exists, OuterRef, Q

from suite_identity.access import require_access

from core.models import RoleChoices, StorageGrant


def principal(user):
    """No grants, including group grants, survive deactivation of their user."""
    if not user.is_authenticated or not user.is_active:
        return Q(pk__in=[])
    require_access(user)
    return Q(user=user) | Q(team__in=user.teams)


def grants_for_item(item, user):
    """Evaluate folder identities rather than mutable titles or object keys."""
    grants = getattr(item, "_storage_grants", None)
    identity = (
        user.pk,
        user.is_active,
        tuple(getattr(user, "teams", ())),
        item.storage_backend_id,
        str(item.path),
    )
    if grants is None or grants[0] != identity:
        rows = list(
            StorageGrant.objects.filter(
                principal(user),
                space__backend_id=item.storage_backend_id,
                space__root_item__path__ancestors=item.path,
                space__enabled=True,
            ).select_related("root_item", "space")
        )
        grants = (identity, rows)
        item.__dict__["_storage_grants"] = grants
    matching = [
        grant
        for grant in grants[1]
        if (
            not grant.root_item_id
            or list(item.path[: grant.root_item.depth]) == list(grant.root_item.path)
        )
    ]
    return grants[1], matching


def cache_item_grants(items, user):
    """Load only grants applicable to this bounded page, preserving nested views."""
    locations = Q(pk__in=[])
    for item in items:
        if item.storage_space_id:
            locations |= Q(
                space__backend_id=item.storage_backend_id,
                space__root_item__path__ancestors=item.path,
            )
    grants = list(
        StorageGrant.objects.filter(principal(user), locations, space__enabled=True).select_related(
            "root_item", "space__root_item"
        )
    )
    for item in items:
        item.__dict__["_storage_grants"] = (
            (
                user.pk,
                user.is_active,
                tuple(getattr(user, "teams", ())),
                item.storage_backend_id,
                str(item.path),
            ),
            [
                grant
                for grant in grants
                if grant.space.backend_id == item.storage_backend_id
                and list(item.path[: grant.space.root_item.depth])
                == list(grant.space.root_item.path)
            ],
        )


def source_write_allowed(space, user, path):
    """Authorize a retained S3 source under current ancestor and subfolder grants."""
    grants = StorageGrant.objects.filter(
        principal(user),
        space__backend_id=space.backend_id,
        space__root_item__path__ancestors=path,
        space__enabled=True,
    ).filter(Q(root_item__isnull=True) | Q(root_item__path__ancestors=path))
    if grants.exists():
        return grants.filter(writable=True).exists()
    return not space.explicit_access and space.owner_id == user.pk


def effective_role(item, user, role):
    """An explicit space grant is sufficient access to its permitted subtree."""
    if item.storage_backend_id and not item.storage_backend.enabled:
        return None
    if not item.storage_space_id:
        return role
    space = item.storage_space
    all_grants, matching = grants_for_item(item, user)
    if not space.enabled and not matching:
        return None
    if not matching:
        return None if all_grants or (space.explicit_access and not space.allow_sharing) else role
    writable = not space.backend.maintenance and any(grant.writable for grant in matching)
    shareable = any(grant.shareable and grant.space.allow_sharing for grant in matching)
    if shareable:
        return RoleChoices.max(role, RoleChoices.ADMIN) if writable else RoleChoices.ADMIN
    return RoleChoices.EDITOR if writable else RoleChoices.READER


def bound_abilities(item, user, abilities):
    """File shares may expose one resource; they never override a user's space cap."""
    if not item.storage_backend_id:
        return abilities
    backend = item.storage_backend
    space = item.storage_space if item.storage_space_id else None
    active = backend.enabled and (not space or space.enabled)
    writable = active and not backend.maintenance
    shareable = active
    if space:
        all_grants, matching = grants_for_item(item, user)
        if all_grants:
            active = backend.enabled and bool(matching)
            writable = (
                active and not backend.maintenance and any(grant.writable for grant in matching)
            )
            shareable = any(grant.shareable and grant.space.allow_sharing for grant in matching)
        elif space.explicit_access:
            active = active and space.allow_sharing
        if not all_grants:
            shareable = shareable and space.allow_sharing
    writes = {
        "children_create",
        "destroy",
        "hard_delete",
        "move",
        "restore",
        "convert",
        "partial_update",
        "update",
        "upload_ended",
        "upload_policy",
    }
    shares = {"accesses_manage", "link_configuration", "invite_owner"}
    for action in abilities:
        if (
            not active
            or (action in writes and not writable)
            or (action in shares and not shareable)
        ):
            abilities[action] = {} if action == "link_select_options" else False
    if not shareable:
        abilities["link_select_options"] = {}
    elif not abilities.get("update"):
        abilities["link_select_options"] = {
            reach: [role for role in roles if role == RoleChoices.READER] if roles else roles
            for reach, roles in abilities.get("link_select_options", {}).items()
        }
    return abilities


def bound_queryset(queryset, user, *, grants_only=False):
    """Apply both native document placement and file-space restrictions in SQL."""
    from core.services.docs_resources import enabled, scoped_queryset  # noqa: PLC0415

    files = _bound_file_queryset(queryset.exclude(type="docs"), user, grants_only=grants_only)
    if not enabled():
        return files
    documents = scoped_queryset(queryset.filter(type="docs"), user, grants_only=grants_only)
    return queryset.filter(Q(pk__in=files.values("pk")) | Q(pk__in=documents.values("pk")))


def _bound_file_queryset(queryset, user, *, grants_only=False):
    """Filter before pagination/count so inaccessible siblings cannot leak metadata."""
    grants = StorageGrant.objects.filter(
        principal(user),
        space__backend_id=OuterRef("storage_backend_id"),
        space__root_item__path__ancestors=OuterRef("path"),
        space__enabled=True,
    )
    matching = grants.filter(
        Q(root_item__isnull=True) | Q(root_item__path__ancestors=OuterRef("path"))
    )
    queryset = queryset.alias(_space_grant=Exists(grants), _matching_grant=Exists(matching))
    active = Q(storage_backend__isnull=True) | Q(
        storage_backend__enabled=True,
    ) & (Q(storage_space__isnull=True) | Q(storage_space__enabled=True) | Q(_matching_grant=True))
    if grants_only:
        return queryset.filter(active, _matching_grant=True)
    permitted = (
        Q(storage_space__isnull=True)
        | Q(_matching_grant=True)
        | Q(_space_grant=False, storage_space__explicit_access=False)
        | Q(_space_grant=False, storage_space__allow_sharing=True)
    )
    return queryset.filter(active, permitted)
