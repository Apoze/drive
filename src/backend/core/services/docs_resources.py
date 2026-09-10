"""Drive's document permissions; Docs owns content, never these decisions."""

import time
from contextlib import contextmanager
from contextvars import ContextVar
from copy import copy

from django.conf import settings
from django.contrib.postgres.expressions import ArraySubquery
from django.db.models import Exists, OuterRef, Q, Subquery
from django.db.models.functions import JSONObject

from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from suite_identity.access import require_access

from core.models import DocsBinding, Item, ItemAccess, LinkTrace, StorageResource, StorageSpace
from core.mounts.providers.base import MountProviderError
from core.services.docs_anchors import current_anchor
from core.services.storage_access import bound_abilities, cache_item_grants, principal
from core.services.storage_resources import mounted_queryset, space_root
from core.services.storage_spaces import authorize, within

ROLES = ("reader", "commenter", "editor", "administrator", "owner")
FILE_ACTIONS = (
    "download",
    "upload_ended",
    "upload_policy",
    "wopi",
    "convert",
    "text",
    "media_auth",
)


_read_page = ContextVar("docs_read_page", default=None)


def _page_actor(user):
    return user.pk, user.is_active, tuple(getattr(user, "teams", ()))


def _prepared(item, user=None):
    page = _read_page.get()
    if page is None or (user is not None and page[0] != _page_actor(user)):
        return None
    row = page[1].get(item.pk)
    return row if row and row["path"] == str(item.path) else None


@contextmanager
def document_page(items, user):
    """Prefetch this read-only response only; never retain rights between requests."""
    documents = [item for item in items if item.type == "docs"]
    if not documents or not enabled():
        yield
        return
    if len(documents) > 100:
        raise ValueError("Document serialization must use bounded pages.")
    ancestors = Item.objects.filter(path__ancestors=OuterRef("path"))
    links = (
        ancestors.filter(type="docs", ancestors_deleted_at__isnull=True)
        .annotate(definition=JSONObject(link_reach="link_reach", link_role="link_role"))
        .values("definition")
    )
    rows = list(
        Item.objects.filter(pk__in=[item.pk for item in documents])
        .annotate_user_roles(user)
        .annotate(
            docs_root=Subquery(ancestors.filter(type="docs").order_by("path").values("pk")[:1]),
            docs_folder=Subquery(
                ancestors.filter(type="folder").order_by("-path").values("pk")[:1]
            ),
            docs_links=ArraySubquery(links),
        )
    )
    roots = {
        binding.item_id: binding
        for binding in DocsBinding.objects.filter(
            item_id__in={row.docs_root for row in rows} | {row.pk for row in rows}
        ).select_related("mounted_parent", "anchor_space__backend")
    }
    folders = (
        Item.objects.filter(pk__in=[row.docs_folder for row in rows if row.docs_folder])
        .select_related("storage_backend", "storage_space__backend")
        .annotate_user_roles(user)
        .in_bulk()
    )
    for item in documents:
        if item.pk in roots:
            item.docs_binding = roots[item.pk]
    prepared, locations, scopes = {}, {}, list(folders.values())
    for row in rows:
        root = roots.get(row.docs_root)
        if root is None:
            continue
        parent = root.mounted_parent if root.mounted_parent_id else folders.get(row.docs_folder)
        space = (
            root.anchor_space
            if root.mounted_parent_id
            else parent.storage_space
            if parent
            else None
        )
        scope = None
        if isinstance(parent, Item):
            scope = copy(row)
            scope.storage_backend, scope.storage_space = parent.storage_backend, space
            scopes.append(scope)
        prepared[row.pk] = {
            "path": str(row.path),
            "roles": row.user_roles,
            "links": row.docs_links,
            "placement": (parent, space),
            "scope": scope,
            "location": locations.setdefault(
                (parent.pk if parent else None, space.pk if space else None), {}
            ),
        }
    cache_item_grants(scopes, user)
    token = _read_page.set((_page_actor(user), prepared))
    try:
        yield
    finally:
        _read_page.reset(token)


def enabled():
    """An unconfigured integration cannot grant access to documentary pointers."""
    return getattr(settings, "DOCS_DRIVE_ENABLED", False)


def highest_role(roles):
    """Keep the comment-only role between reader and editor, without escalation."""
    return max((role for role in roles if role in ROLES), key=ROLES.index, default=None)


def access_ttl(item):
    """A downstream coediting lease cannot outlive the observed NAS location."""
    deadline = getattr(item, "_docs_access_deadline", None)
    remaining = min(15, deadline - time.time()) if deadline is not None else 15
    if remaining < 1:
        error = APIException("Document location verification expired. Retry shortly.")
        error.status_code = 503
        raise error
    return int(remaining)


def binding_for(item):
    """Use a prefetched binding when present; a missing binding is never a file."""
    try:
        return item.docs_binding
    except DocsBinding.DoesNotExist:
        raise NotFound("Document is not available.") from None


def scoped_queryset(queryset, user, *, grants_only=False):
    """Bound document placement in SQL before counts and pagination."""
    from core.services.storage_access import _bound_file_queryset  # noqa: PLC0415

    if not enabled():
        return queryset.none()
    folders = Item.objects.filter(type="folder", path__ancestors=OuterRef("path"))
    allowed_folders = _bound_file_queryset(
        Item.objects.filter(pk=OuterRef("_docs_folder")), user, grants_only=grants_only
    )
    mounted_roots = DocsBinding.objects.filter(
        mounted_parent__isnull=False, item__path__ancestors=OuterRef("path")
    )
    mount_scope = Q(pk__in=[])
    for space in StorageSpace.objects.filter(
        enabled=True, backend__enabled=True, backend__family="mount"
    ).select_related("backend"):
        anchors = mounted_queryset(space, user)
        if (
            not grants_only
            and space.allow_sharing
            and not space.grants.filter(principal(user)).exists()
        ):
            # A direct document share grants no ability to browse sibling NAS files.
            root = space_root(space).rstrip("/")
            anchors = StorageResource.objects.filter(
                namespace=space.backend.namespace,
                missing=False,
            ).filter(Q(path=root or "/") | Q(path__startswith=root + "/"))
        mount_scope |= Q(anchor_space=space, mounted_parent__in=anchors.values("pk"))
    queryset = queryset.alias(
        _docs_folder=Subquery(folders.order_by("-path").values("pk")[:1]),
        _docs_folder_allowed=Exists(allowed_folders),
        _docs_mounted=Exists(mounted_roots),
        _docs_mount_allowed=Exists(mounted_roots.filter(mount_scope)),
    ).filter(docs_binding__state__in=["active", "trash"])
    unmounted = Q(_docs_mounted=False, _docs_folder_allowed=True)
    if not grants_only:
        unmounted |= Q(_docs_mounted=False, _docs_folder__isnull=True)
    return queryset.filter(unmounted | Q(_docs_mount_allowed=True))


def visible_documents(user, query):
    """Use the authoritative tree and permissions before selecting a Docs page."""
    parent_id = query.get("parent_document_id")
    if not user.is_authenticated and not parent_id:
        raise PermissionDenied()
    items = scoped_queryset(Item.objects.filter(type="docs"), user)
    if parent_id:
        binding = DocsBinding.objects.select_related("item").filter(document_id=parent_id).first()
        if (
            binding is None
            or binding.item is None
            or not binding.item.get_abilities(user).get("children_list")
        ):
            raise PermissionDenied()
        parent = binding.item
        items = items.filter(path__descendants=parent.path).exclude(pk=parent.pk)
        if not query.get("descendants"):
            items = items.filter(path__depth=parent.depth + 1)
    accesses = ItemAccess.objects.filter(principal(user), item__path__ancestors=OuterRef("path"))
    if query.get("trash"):
        items = (
            items.filter(ancestors_deleted_at__isnull=False)
            .alias(_document_owner=Exists(accesses.filter(role="owner")))
            .filter(_document_owner=True)
        )
    elif parent_id:
        items = items.filter(ancestors_deleted_at__isnull=True)
    else:
        from core.services.docs_links import contextual_scope  # noqa: PLC0415

        granted = scoped_queryset(Item.objects.filter(type="docs"), user, grants_only=True)
        visited = LinkTrace.objects.filter(user=user, item_id=OuterRef("pk"))
        context_scope = contextual_scope()
        linked = Item.objects.filter(
            type="docs",
            path__ancestors=OuterRef("path"),
            ancestors_deleted_at__isnull=True,
            link_reach__in=["public", "authenticated"],
        )
        items = (
            items.filter(ancestors_deleted_at__isnull=True)
            .alias(
                _document_access=Exists(accesses),
                _document_visited=Exists(visited),
                _document_linked=Exists(linked),
            )
            .filter(
                Q(_document_access=True)
                | Q(pk__in=granted.values("pk"))
                | Q(_document_visited=True, _document_linked=True)
                | (Q(_document_visited=True) & context_scope)
            )
        )
    if query.get("title"):
        items = items.filter(title__icontains=query["title"])
    if "is_creator_me" in query:
        if not user.is_authenticated:
            raise PermissionDenied()
        items = (
            items.filter(creator=user) if query["is_creator_me"] else items.exclude(creator=user)
        )
    if "is_favorite" in query:
        items = items.annotate_is_favorite(user).filter(is_favorite=query["is_favorite"])
    if query.get("roots_only", True) and not parent_id:
        ancestors = items.filter(path__ancestors=OuterRef("path")).exclude(pk=OuterRef("pk"))
        items = items.alias(_readable_parent=Exists(ancestors)).filter(_readable_parent=False)
    return items


def placement(item):
    """Return the existing file folder or mounted anchor above the document tree."""
    if prepared := _prepared(item):
        return prepared["placement"]
    documents = Item.objects.filter(path__ancestors=item.path, type="docs").order_by("path")
    root = documents.select_related(
        "docs_binding__anchor_space__backend", "docs_binding__mounted_parent"
    ).first()
    if root is None:
        raise NotFound("Document is not available.")
    binding = binding_for(root)
    if binding.mounted_parent_id:
        return binding.mounted_parent, binding.anchor_space
    parent = root.parent() if root.depth > 1 else None
    if parent is not None:
        return parent, parent.storage_space
    return None, None


def placement_capabilities(item, user):
    """A page shares current location checks, never decisions between requests."""
    prepared = _prepared(item, user)
    location = prepared["location"] if prepared is not None else {}
    if "caps" not in location:
        location["caps"] = _placement_capabilities(item, user)
        location["deadline"] = getattr(item, "_docs_access_deadline", None)
    if location.get("deadline") is not None:
        item._docs_access_deadline = location["deadline"]  # noqa: SLF001
        access_ttl(item)
    return dict(location["caps"])


def _placement_capabilities(item, user):
    """Apply the same current folder permissions as a file at this location."""
    parent, space = placement(item)
    if parent is None:
        return {"retrieve": True, "update": True, "accesses_manage": True}
    if isinstance(parent, Item):
        prepared = _prepared(item, user)
        scope = prepared["scope"] if prepared is not None else copy(item)
        scope.storage_backend = parent.storage_backend
        scope.storage_space = parent.storage_space
        return bound_abilities(
            scope, user, {"retrieve": True, "update": True, "accesses_manage": True}
        )
    if parent.missing or not space or not space.enabled or not space.backend.enabled:
        return {}
    if not within(parent.path, space_root(space)) or not current_anchor(parent, space.backend):
        return {}
    if deadline := getattr(parent, "_docs_anchor_deadline", None):
        item._docs_access_deadline = min(  # noqa: SLF001
            getattr(item, "_docs_access_deadline", deadline), deadline
        )
    if space.allow_sharing and not space.grants.filter(principal(user)).exists():
        return {"retrieve": True, "update": not space.backend.maintenance, "accesses_manage": True}
    path = parent.path[len(space_root(space).rstrip("/")) :] or "/"
    result = {}
    for action, options in (
        ("retrieve", {}),
        ("update", {"write": True}),
        ("accesses_manage", {"share": True}),
    ):
        try:
            authorize(space, user, path, **options)
            result[action] = True
        except MountProviderError:
            result[action] = False
    return result


def role_for_document(item, user):
    """Resolve current principal grants; cached roles cannot survive a revocation."""
    if not enabled() or not user.is_authenticated or not user.is_active:
        return None
    require_access(user)
    binding = binding_for(item)
    if binding.state in {"pending", "preparing", "purging", "purged"}:
        return None
    prepared = _prepared(item, user)
    roles = (
        prepared["roles"]
        if prepared is not None
        else ItemAccess.objects.filter(
            Q(user=user) | Q(team__in=user.teams),
            item__path__ancestors=item.path,
        ).values_list("role", flat=True)
    )
    role = highest_role(roles)
    caps = placement_capabilities(item, user)
    if not caps.get("retrieve"):
        return None
    parent, _space = placement(item)
    location = prepared["location"] if prepared is not None else {}
    if "role" not in location:
        parent_role = None
        if isinstance(parent, Item):
            parent_role = parent.get_role(user)
        elif parent is not None and mounted_queryset(_space, user).filter(pk=parent.pk).exists():
            parent_role = "editor" if caps.get("update") else "reader"
        location["role"] = parent_role
    role = highest_role((role, location["role"]))
    if role in {"editor", "administrator", "owner"} and not caps.get("update"):
        return "reader"
    return role


def document_abilities(item, user):
    """Explicit document abilities keep every binary file endpoint closed."""
    if user.is_authenticated and not user.is_active:
        return {}
    role = role_for_document(item, user)
    active = (
        enabled()
        and binding_for(item).state == "active"
        and not item.ancestors_deleted_at
        and not item.hard_deleted_at
    )
    caps = placement_capabilities(item, user) if enabled() else {}
    from core.services.docs_links import contextual_role  # noqa: PLC0415

    bearer_role = contextual_role(item) if active else None
    if bearer_role:
        caps = {**caps, "retrieve": True, "update": bool(caps.get("update"))}
    link_role = None
    if active and caps.get("retrieve") and caps.get("accesses_manage"):
        prepared = _prepared(item, user)
        links = (
            prepared["links"]
            if prepared is not None
            else list(
                Item.objects.filter(
                    path__ancestors=item.path,
                    type="docs",
                    ancestors_deleted_at__isnull=True,
                    link_reach__in=["public", "authenticated"],
                ).values("link_reach", "link_role")
            )
        )
        # Native Docs gives the widest reach precedence, then the strongest role
        # within that reach. A narrower link must not silently grant more rights.
        reach = "public" if any(row["link_reach"] == "public" for row in links) else "authenticated"
        if reach == "public" or user.is_authenticated:
            link_role = highest_role(
                row["link_role"] for row in links if row["link_reach"] == reach
            )
    effective = highest_role((role, link_role, bearer_role))
    read = bool(active and effective)
    edit = read and effective in {"editor", "administrator", "owner"} and bool(caps.get("update"))
    manage = read and role in {"administrator", "owner"} and bool(caps.get("accesses_manage"))
    owner = role == "owner"
    return {
        **dict.fromkeys(FILE_ACTIONS, False),
        "retrieve": read or bool(owner and item.ancestors_deleted_at and not item.hard_deleted_at),
        "open_docs": read,
        "contextual_access": read and bool(bearer_role),
        "update": edit,
        "partial_update": edit,
        "comment": read and effective != "reader" and bool(caps.get("update")),
        "children_list": read,
        "children_create": edit and user.is_authenticated,
        "accesses_manage": manage,
        "accesses_view": read and bool(role),
        "link_configuration": manage,
        "invite_owner": owner and manage,
        "move": manage and bool(caps.get("update")),
        "duplicate": read and user.is_authenticated,
        "export": read,
        "destroy": manage and bool(caps.get("update")),
        "restore": owner and bool(item.deleted_at) and not item.hard_deleted_at,
        "hard_delete": owner and bool(item.deleted_at),
        "favorite": read and user.is_authenticated,
        "breadcrumb": read,
        "tree": read,
        "activity_view": manage,
        "link_select_options": (
            {"restricted": None, "authenticated": list(ROLES[:3]), "public": list(ROLES[:3])}
            if manage
            else {}
        ),
    }
