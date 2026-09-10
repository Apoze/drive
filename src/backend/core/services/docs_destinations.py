"""Paged destination metadata for Docs, using the existing virtual space rules."""

from rest_framework.exceptions import NotFound, PermissionDenied
from suite_identity.access import require_access

from core.models import Item, StorageSpace
from core.mounts.providers.base import MountProviderError
from core.services.docs_resources import enabled
from core.services.storage_access import bound_queryset
from core.services.storage_resources import (
    mounted_queryset,
    space_entrances,
    space_root,
    visible_spaces,
)
from core.services.storage_spaces import authorize
from core.services.storage_transfer_location import resolve_location


def destinations(user, query):
    """Expose titles and stable references only; storage credentials stay in Drive."""
    if not enabled():
        raise NotFound()
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied()
    require_access(user)
    space_id, parent_id = query.get("space_id"), query.get("parent_id")
    offset, limit = query.get("offset", 0), query.get("limit", 50)
    space = None
    if parent_id:
        parent = Item.objects.filter(pk=parent_id, type="docs").first()
        if parent:
            if not parent.get_abilities(user).get("children_list"):
                raise PermissionDenied()
            rows = bound_queryset(parent.children(), user).filter(ancestors_deleted_at__isnull=True)
        else:
            location = resolve_location(parent_id, user, space_id=space_id)
            if location.kind != "folder":
                raise NotFound()
            parent, space = location.reference, location.space
            rows = (
                bound_queryset(parent.children(), user).filter(
                    type__in=["folder", "docs"],
                    ancestors_deleted_at__isnull=True,
                )
                if isinstance(parent, Item)
                else mounted_queryset(space, user, traverse=True)
                .filter(
                    parent_path=parent.path,
                    kind="folder",
                )
                .exclude(pk=parent.pk)
            )
    elif space_id:
        space = visible_spaces(user).filter(pk=space_id).first()
        if space is None:
            raise NotFound()
        rows = space_entrances(space, user)
    else:
        rows = visible_spaces(user)
    count = rows.count()
    field = "title" if rows.model is Item else "name"
    page = rows.order_by(field, "pk")[offset : offset + limit]
    return {
        "current": _destination_row(parent, user, space, space_id) if parent_id else None,
        "count": count,
        "results": [_destination_row(row, user, space, space_id) for row in page],
        "next_offset": offset + limit if offset + limit < count else None,
    }


def _destination_row(row, user, space, space_id):
    if isinstance(row, StorageSpace):
        return {"id": str(row.pk), "title": row.name, "kind": "space", "can_create": False}
    if isinstance(row, Item):
        writable = row.get_abilities(user).get("children_create", False)
        title, kind = row.title, row.type
    else:
        path = row.path[len(space_root(space).rstrip("/")) :] or "/"
        try:
            authorize(space, user, path, write=True)
            # Creation will stat this identity; a path-only reference is insufficient.
            writable = bool(row.provider_identity)
        except MountProviderError:
            writable = False
        title, kind = row.name or space.name, row.kind
    return {
        "id": str(row.pk),
        "space": str(space.pk) if space else str(space_id or ""),
        "title": title,
        "kind": kind,
        "can_create": writable,
    }
