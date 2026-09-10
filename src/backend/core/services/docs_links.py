"""A folder bearer grants only the document subtree explicitly opened through it."""

from django.contrib.auth.models import AnonymousUser

from rest_framework.exceptions import APIException
from suite_identity.document_transport import document_links

from core.models import Item, MountShareLink, StorageResource
from core.services.docs_anchors import current_anchor
from core.services.storage_resources import shared_moved_item, shared_resource_location, space_root
from core.services.storage_spaces import context, within
from core.utils.share_links import current_item_share_token, validate_item_share_token


def _under_item(document, root):
    return root.type == "folder" and str(document.path).startswith(str(root.path) + ".")


def _mount_role(document, token):
    from core.services.docs_resources import placement  # noqa: PLC0415

    link = (
        MountShareLink.objects.select_related("created_by", "resource").filter(token=token).first()
    )
    if not link or not link.created_by_id or not link.created_by.is_active:
        return None
    moved = shared_moved_item(link)
    if moved is not None:
        return "reader" if _under_item(document, moved) else None
    mount, path = shared_resource_location(link)
    space, _actor, _ = context(mount)
    parent, anchor_space = placement(document)
    if (
        not isinstance(parent, StorageResource)
        or anchor_space is None
        or not anchor_space.enabled
        or not anchor_space.allow_sharing
        or not anchor_space.backend.enabled
        or parent.namespace != space.backend.namespace
        or not within(parent.path, space_root(space).rstrip("/") + path)
        or not within(parent.path, space_root(anchor_space))
        or not current_anchor(parent, anchor_space.backend)
    ):
        return None
    return "reader"


def contextual_role(item):
    """A document UUID never reconstructs a parent folder's bearer authorization."""
    links = document_links.get() or {}
    if not links:
        return None
    from core.services.docs_resources import highest_role  # noqa: PLC0415

    roots = Item.objects.filter(
        docs_binding__document_id__in=links,
        path__ancestors=item.path,
        ancestors_deleted_at__isnull=True,
        hard_deleted_at__isnull=True,
    ).select_related("docs_binding")
    roles = []
    for document in roots:
        link = links[str(document.docs_binding.document_id)]
        try:
            if link["kind"] == "mount":
                roles.append(_mount_role(item, link["token"]))
                continue
            root_id = validate_item_share_token(link["token"])
            root = Item.objects.filter(pk=root_id, type="folder").first() if root_id else None
            if (
                root is not None
                and _under_item(item, root)
                and current_item_share_token(root, link["token"])
                and root.computed_link_reach == "public"
                and root.get_abilities(AnonymousUser()).get("retrieve")
            ):
                roles.append(root.computed_link_role)
        except APIException:
            # Missing/revoked links disclose nothing; infrastructure failures
            # still fail closed and do not mutate document ownership.
            continue
    return highest_role(roles)


def context_url(item, kind, token):
    """Open a document without placing its folder bearer in any HTTP request URL."""
    from urllib.parse import urlencode  # noqa: PLC0415

    from django.conf import settings  # noqa: PLC0415

    if not settings.DOCS_DRIVE_ENABLED or not settings.DOCS_PUBLIC_URL:
        return None
    query = urlencode(
        {"document_id": str(item.docs_binding.document_id), "kind": kind, "token": token}
    )
    return settings.DOCS_PUBLIC_URL.rstrip("/") + "/docs/open/#" + query


def public_entry(item, token):
    """Retain the public explorer's existing entry contract for a native document."""
    return {
        "normalized_path": str(item.pk),
        "entry_type": "docs",
        "name": item.title,
        "size": item.size,
        "modified_at": item.updated_at,
        "download_available": False,
        "url_docs": context_url(item, "mount", token),
    }


def append_mounted_documents(page, paginator, mount, path, token):
    """Page documents after native rows without loading either complete directory."""
    from django.conf import settings  # noqa: PLC0415

    from core.services.docs_resources import scoped_queryset  # noqa: PLC0415

    if not settings.DOCS_DRIVE_ENABLED or mount.get("provider") != "virtual":
        return
    space, _actor, _ = context(mount)
    native_path = space_root(space).rstrip("/") + path if path != "/" else space_root(space)
    documents = (
        scoped_queryset(
            Item.objects.filter(
                type="docs",
                docs_binding__state="active",
                ancestors_deleted_at__isnull=True,
                hard_deleted_at__isnull=True,
                docs_binding__mounted_parent__namespace=space.backend.namespace,
                docs_binding__mounted_parent__path=native_path,
            ),
            AnonymousUser(),
        )
        .select_related("docs_binding")
        .order_by("title", "pk")
    )
    native_count = paginator.count
    paginator.count += documents.count()
    paginator.display_page_controls = paginator.count > paginator.limit
    available = paginator.limit - len(page)
    if available > 0:
        offset = max(0, paginator.offset - native_count)
        page.extend(public_entry(item, token) for item in documents[offset : offset + available])


def contextual_scope():
    """Include visited documents only while their actual folder bearer still works."""
    from django.db.models import Q  # noqa: PLC0415

    from core.models import DocsBinding  # noqa: PLC0415

    scope = Q(pk__in=[])
    for binding in DocsBinding.objects.filter(
        document_id__in=document_links.get() or {}
    ).select_related("item"):
        if contextual_role(binding.item):
            scope |= Q(path__descendants=binding.item.path)
    return scope
