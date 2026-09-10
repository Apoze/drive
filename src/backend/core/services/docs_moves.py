"""Move document references and their logical budgets without moving native bytes."""

from django.utils import timezone

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from core.models import DocsBinding, Item, StorageUsage, User
from core.services import storage_quota as quota
from core.services.docs_anchors import current_anchor
from core.services.docs_resources import placement, placement_capabilities
from core.services.item_activity import record_item_activity
from core.services.storage_inventory import refresh_policy
from core.services.storage_transfer_location import resolve_location


def prepare(item, user, data):
    """Resolve IO and refresh destination policies before taking metadata locks."""
    from core.services.docs_anchors import can_recover  # noqa: PLC0415

    allowed = (
        can_recover(item, user)
        if data.get("action") == "recover"
        else item.get_abilities(user).get("move")
    )
    if not allowed:
        raise PermissionDenied()
    parent = Item.objects.filter(pk=data["destination"], type="docs").first()
    location = None
    if parent:
        if not parent.get_abilities(user).get("children_create"):
            raise PermissionDenied()
        _, space = placement(parent)
    else:
        location = resolve_location(
            data["destination"], user, space_id=data.get("space_id"), destination=True
        )
        parent = location.reference if isinstance(location.reference, Item) else None
        space = location.space
        if parent is None and not current_anchor(location.reference, location.backend):
            raise ValidationError("This document location cannot be verified.")
    if parent and Item.objects.filter(pk=parent.pk, path__descendants=item.path).exists():
        raise ValidationError("A document cannot be moved inside itself.")
    if relative := data.get("relative_document_id"):
        sibling = Item.objects.filter(docs_binding__document_id=relative).first()
        if sibling is None or not sibling.get_abilities(user).get("retrieve"):
            raise PermissionDenied()
    owners = (
        User.objects.filter(pk=space.owner_id)
        if space and not space.attribute_to_creator
        else User.objects.filter(
            pk__in=Item.objects.filter(path__descendants=item.path).values("creator_id")
        )
    )
    for owner in owners.iterator(chunk_size=100):
        refresh_policy(owner, organization=space.backend.organization if space else None)
    return parent, location


def apply(item, user, destination, data):
    """The caller's transaction commits placement, counters and projection together."""
    from core.services.docs_quota import attribution  # noqa: PLC0415

    parent, location = destination
    previous_parent, _ = placement(item)
    if parent:
        parent = Item.objects.select_for_update().get(pk=parent.pk)
        if not parent.get_abilities(user).get("children_create"):
            raise PermissionDenied()
    elif location is None:
        raise NotFound()
    else:
        # Revalidate the database state as well as the bounded provider observation.
        from core.services.storage_spaces import authorize  # noqa: PLC0415

        location.space.refresh_from_db()
        location.space.backend.refresh_from_db()
        authorize(location.space, user, location.path, write=True)
        location.reference.refresh_from_db()
        if not current_anchor(location.reference, location.backend):
            raise PermissionDenied()
    usages = StorageUsage.objects.filter(item__path__descendants=item.path)
    quota.guard_metadata_change(usages)
    if (
        Item.objects.filter(path__descendants=item.path).exclude(type="docs").exists()
        or DocsBinding.objects.filter(item__path__descendants=item.path)
        .exclude(state__in=["active", "trash"])
        .exists()
        or Item.objects.filter(path__descendants=item.path, storageusage__isnull=True).exists()
    ):
        raise quota.StorageWriteConflict("Finish pending document operations before moving.")
    binding = DocsBinding.objects.select_for_update().get(item=item)
    # Clear the old anchor before the Item becomes a child; set the new one after.
    binding.mounted_parent = None
    binding.anchor_space = None
    binding.save(update_fields=["mounted_parent", "anchor_space", "updated_at"])
    item.move(parent)
    if parent is None:
        # Moving the Item queues a new revision for the whole document tree.
        binding.refresh_from_db()
        binding.mounted_parent = location.reference
        binding.anchor_space = location.space
        binding.save(update_fields=["mounted_parent", "anchor_space", "updated_at"])
    _order(item, parent, location, data)
    for usage in (
        StorageUsage.objects.select_for_update(of=("self",))
        .filter(item__path__descendants=item.path)
        .select_related("item__creator")
        .order_by("key")
        .iterator(chunk_size=100)
    ):
        target = attribution(usage.item)
        if target["space"] and target["space"].attribute_to_creator and not target["owner"]:
            raise quota.StorageWriteConflict("Assign the document creator before moving.")
        operation = quota.admit(
            key=usage.key, actor=user, size=usage.size, target_scopes=target["scope_keys"]
        )
        quota.begin_publication(
            operation.pk,
            observed_version=usage.version,
            size=usage.size,
            publication={
                "kind": "docs_move",
                "target_attribution": {
                    "owner_id": str(target["owner"].pk) if target["owner"] else None,
                    "space_id": str(target["space"].pk) if target["space"] else None,
                    "organization": target["organization"],
                },
            },
        )
        quota.commit(operation.pk, size=usage.size, version=usage.version)
    # A new space may prohibit sharing. Existing direct grants remain recorded but
    # are bounded by placement permissions; document-wide links must also close.
    if not placement_capabilities(item, user).get("accesses_manage"):
        for child in Item.objects.filter(path__descendants=item.path).iterator(chunk_size=100):
            if child.link_reach != "restricted":
                child.link_reach = "restricted"
                child.save(update_fields=["link_reach"])
    record_item_activity(
        item=item,
        actor=user,
        action="moved",
        payload={
            "old_parent_id": str(previous_parent.pk) if previous_parent else None,
            "old_parent_name": (
                previous_parent.title
                if isinstance(previous_parent, Item)
                else previous_parent.name
                if previous_parent
                else None
            ),
            "new_parent_id": str(parent.pk if parent else location.reference.pk),
            "new_parent_name": parent.title if parent else location.name,
        },
    )


def _order(item, parent, location, data):
    """Renumber siblings in bounded batches, preserving an authoritative order."""
    siblings = DocsBinding.objects.filter(item__path__depth=item.depth)
    if parent:
        siblings = siblings.filter(item__path__descendants=parent.path)
    else:
        siblings = siblings.filter(mounted_parent=location.reference)
    relative = data.get("relative_document_id")
    position = data.get("position", "last-child")
    if relative and not siblings.filter(document_id=relative).exclude(item=item).exists():
        raise ValidationError("The relative document is no longer at this destination.")
    if position in {"left", "right"} and not relative:
        raise ValidationError("Choose a relative document for this position.")
    rows, index = [], 0
    moved = DocsBinding.objects.get(item=item)

    def append(row):
        nonlocal index
        index += 1
        if row.sort_order != index:
            row.sort_order = index
            row.revision += 1
            row.retry_at = timezone.now()
            rows.append(row)
        if len(rows) >= 100:
            DocsBinding.objects.bulk_update(rows, ["sort_order", "revision", "retry_at"])
            rows.clear()

    if position in {"first-child", "first-sibling"}:
        append(moved)
    for sibling in (
        siblings.exclude(item=item).order_by("sort_order", "pk").iterator(chunk_size=100)
    ):
        if relative == sibling.document_id and position == "left":
            append(moved)
        append(sibling)
        if relative == sibling.document_id and position == "right":
            append(moved)
    if position in {"last-child", "last-sibling"}:
        append(moved)
    DocsBinding.objects.bulk_update(rows, ["sort_order", "revision", "retry_at"])
