"""Estimate transfer impact from authorized metadata without reading file contents."""

from itertools import pairwise

from django.conf import settings
from django.db.models import Count, Exists, OuterRef, Q, Sum

from core.models import DocsBinding, Item, MountShareLink, StorageResource, StorageUsage
from core.services.storage_access import bound_queryset
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_resources import mounted_queryset
from core.services.storage_spaces import authorize


def transfer_impact(sources, destination, actor, mode):
    """One aggregate counts logical bytes once; publication revalidates all limits."""
    selected = sorted(
        (
            "s3" if isinstance(source.reference, Item) else "mount",
            str(source.backend.namespace),
            str(source.reference.path),
        )
        for source in sources
    )
    for previous, current in pairwise(selected):
        separator = "." if current[0] == "s3" else "/"
        if current[:2] == previous[:2] and (
            current[2] == previous[2]
            or current[2].startswith(previous[2].rstrip(separator) + separator)
        ):
            raise StorageWriteConflict("Select each resource once, without its selected parent.")
    item_roots, native_roots = Q(pk__in=[]), Q(pk__in=[])
    for source in sources:
        if isinstance(source.reference, Item):
            if mode == "move" and not source.reference.get_abilities(actor).get("move"):
                raise StorageWriteConflict("This resource cannot be moved.")
            item_roots |= Q(path__descendants=source.reference.path)
        else:
            authorize(source.space, actor, source.path, write=mode == "move")
            selected = mounted_queryset(source.space, actor).filter(
                Q(path=source.reference.path)
                | Q(path__startswith=source.reference.path.rstrip("/") + "/")
            )
            native_roots |= Q(pk__in=selected.values("pk"))
    resources = StorageResource.objects.filter(native_roots, missing=False)
    candidates = Item.objects.all()
    if settings.DOCS_DRIVE_ENABLED:
        anchors = DocsBinding.objects.filter(
            mounted_parent__in=resources, item__path__ancestors=OuterRef("path")
        )
        candidates = candidates.alias(mounted_document_selected=Exists(anchors))
        if candidates.filter(
            pk__in=[
                source.reference.pk for source in sources if isinstance(source.reference, Item)
            ],
            mounted_document_selected=True,
        ).exists():
            raise StorageWriteConflict("Select either a folder or its nested documents, not both.")
        item_roots |= Q(mounted_document_selected=True)
    items = bound_queryset(candidates.filter(item_roots), actor).filter(
        deleted_at__isnull=True, hard_deleted_at__isnull=True, ancestors_deleted_at__isnull=True
    )
    native_file = resources.filter(
        kind="file", namespace=OuterRef("backend__namespace"), path=OuterRef("path")
    )
    usages = (
        StorageUsage.objects.alias(selected_native=Exists(native_file))
        .filter(Q(item__in=items.filter(type__in=["file", "docs"])) | Q(selected_native=True))
        .exclude(version="missing")
    )
    added = Q() if mode == "copy" else ~Q(scope_keys__contains=[f"space:{destination.space.pk}"])
    metrics = usages.aggregate(
        files=Count("pk"),
        bytes=Sum("size", default=0),
        space_bytes=Sum("size", filter=added, default=0),
    )
    public_items = items.filter(link_reach="public")
    public_links = MountShareLink.objects.filter(
        Q(resource__in=resources) | Q(resource_id__in=items.values("pk"))
    )
    names = list(public_items.order_by("title", "pk").values_list("title", flat=True)[:10])
    names += list(
        public_links.order_by("resource__name", "pk").values_list("resource__name", flat=True)[:10]
    )
    return {
        "files": metrics["files"],
        "bytes": metrics["bytes"],
        "global_additional_bytes": metrics["bytes"] if mode == "copy" else 0,
        "space_additional_bytes": metrics["space_bytes"],
        "attribution": "creator"
        if destination.space.attribute_to_creator
        else ("owner" if destination.space.owner_id else "common"),
        "sharing_allowed": destination.space.allow_sharing,
        "public_links": public_items.count() + public_links.count() if mode == "move" else 0,
        "shared_names": names[:10] if mode == "move" else [],
    }
