"""Move an S3 subtree between spaces on one connection without copying bytes."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models.expressions import RawSQL

from rest_framework.exceptions import APIException

from core.models import (
    DocsBinding,
    Item,
    ItemActivityActionChoices,
    StorageMoveJob,
    StorageResource,
    StorageResourceFavorite,
    StorageSpace,
    StorageUsage,
    User,
)
from core.services import storage_inventory as inventory
from core.services import storage_quota as quota
from core.services.docs_lifecycle import queue_change, queue_tree_changes
from core.services.docs_quota import attribution as document_attribution
from core.services.item_activity import record_item_activity
from core.services.storage_move_job import dispatch_move
from core.services.storage_namespace import StorageOperationBusy, namespace_guard
from core.services.storage_resources import (
    revoke_incompatible_links,
    revoke_item_tree_links,
    transfer_item_links,
    transfer_staged_item_links,
)
from core.services.storage_transfer_location import resolve_location
from core.services.storage_tree_transfer import finish_transfer, prepare_transfer
from wopi.services.lock import LockService


def _validate(source, destination, actor):
    if (
        source.kind != "folder"
        or source.backend.family != "s3"
        or source.backend.pk != destination.backend.pk
        or not source.reference.get_abilities(actor).get("move")
    ):
        raise quota.StorageWriteConflict("This folder cannot be moved between these spaces.")
    if StorageSpace.objects.filter(root_item__path__descendants=source.reference.path).exists():
        raise quota.StorageWriteConflict(
            "A folder containing a storage-space root cannot be moved."
        )
    if Item.objects.filter(
        pk=destination.reference.pk, path__descendants=source.reference.path
    ).exists():
        raise quota.StorageWriteConflict("A folder cannot be moved inside itself.")


def validate_tree_transfer(source, destination, actor):
    """Cross-connection folder moves keep all descendants on one source allocation."""
    if (
        source.kind != "folder"
        or source.backend.family != "s3"
        or destination.kind != "folder"
        or not source.reference.get_abilities(actor).get("move")
    ):
        raise quota.StorageWriteConflict("This folder cannot be transferred.")
    tree = Item.objects.filter(path__descendants=source.reference.path)
    if (
        StorageSpace.objects.filter(root_item__in=tree).exists()
        or tree.exclude(type="docs")
        .exclude(storage_backend=source.backend, storage_space=source.space)
        .exists()
        or tree.filter(deleted_at__isnull=False).exists()
        or tree.filter(hard_deleted_at__isnull=False).exists()
    ):
        raise quota.StorageWriteConflict(
            "Resolve nested allocations or deleted descendants before moving this folder."
        )


def _finish_native_folder(original, temporary, target):
    """Bind the original folder UUID to its verified native destination."""
    fields = {
        field: getattr(temporary, field)
        for field in (
            "namespace",
            "identity_key",
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
        )
    }
    StorageResource.objects.filter(pk=temporary.pk).update(
        identity_key=quota.resource_key(f"retired-staging:{temporary.pk}")
    )
    resource, _ = StorageResource.objects.update_or_create(pk=original.pk, defaults=fields)
    for favorite in StorageResourceFavorite.objects.filter(resource=temporary).iterator(
        chunk_size=100
    ):
        previous, _ = StorageResourceFavorite.objects.get_or_create(
            user=favorite.user, resource=resource, defaults={"space": target.space}
        )
        previous.favorite |= favorite.favorite
        if favorite.last_opened_at and (
            not previous.last_opened_at or favorite.last_opened_at > previous.last_opened_at
        ):
            previous.last_opened_at = favorite.last_opened_at
        previous.save(update_fields=["favorite", "last_opened_at", "updated_at"])
    if isinstance(original, Item):
        transfer_item_links(original, target.space, target.path)
    else:
        StorageResourceFavorite.objects.filter(resource=resource).update(space=target.space)
    temporary.share_links.update(resource=resource)
    if settings.DOCS_DRIVE_ENABLED:
        DocsBinding.objects.filter(mounted_parent=temporary).update(mounted_parent=resource)
        for binding in (
            DocsBinding.objects.filter(mounted_parent=resource)
            .select_related("item")
            .iterator(chunk_size=100)
        ):
            queue_change(binding.item)
            queue_tree_changes(binding.item)
    StorageResource.objects.filter(pk=temporary.pk).delete()
    if isinstance(original, Item):
        Item.objects.filter(pk=original.pk).delete()
    revoke_incompatible_links(original.pk)


@transaction.atomic
def finish_tree_manifest(job):
    """Keep original folder rows and references after every file has reached its destination."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_folder_copy import _resolve  # noqa: PLC0415

    destination = _resolve(job.payload["destination"], job.actor, destination=True)
    for entry in (
        job.copy_entries.filter(kind="folder")
        .select_related("parent")
        .order_by("-created_at", "-pk")
        .iterator(chunk_size=100)
    ):
        source = _resolve(entry.source, job.actor)
        validate_tree_transfer(source, destination, job.actor)
        target = _resolve(entry.publication["target"], job.actor, destination=True)
        if source.reference.children().exists():
            raise quota.StorageWriteConflict(
                "The source folder has unfinished children. Completed transfers are retained."
            )
        original, temporary = source.reference, target.reference
        if destination.backend.family == "mount":
            _finish_native_folder(original, temporary, target)
            entry.target_id = original.pk
            entry.save(update_fields=["target_id", "updated_at"])
            continue
        old_parent = original.parent()
        new_parent = temporary.parent()
        path = f"{new_parent.path}.{original.pk}"
        Item.objects.filter(pk=original.pk).update(
            path=path,
            title=temporary.title,
            storage_backend=destination.backend,
            storage_space=destination.space,
        )
        Item.objects.filter(path__descendants=temporary.path).exclude(pk=temporary.pk).update(
            path=RawSQL("%s || subpath(path, nlevel(%s))", (path, str(temporary.path))),
        )
        transfer_staged_item_links(temporary, original)
        Item.objects.filter(pk=temporary.pk).delete()
        original.refresh_from_db()
        queue_tree_changes(original)
        entry.target_id = original.pk
        entry.save(update_fields=["target_id", "updated_at"])
        record_item_activity(
            item=original,
            actor=job.actor,
            action=ItemActivityActionChoices.MOVED,
            payload={
                "old_parent_id": str(old_parent.pk),
                "old_parent_name": old_parent.title,
                "new_parent_id": str(entry.parent.source_id if entry.parent_id else new_parent.pk),
                "new_parent_name": new_parent.title,
            },
        )
    job.state, job.reason = "done", ""
    job.payload = {
        **job.payload,
        "result": job.source_path,
        "source_retained": job.copy_entries.filter(
            child_job__payload__source_retained=True
        ).exists(),
    }
    job.save(update_fields=["state", "reason", "payload", "updated_at"])


def enqueue_item_tree_move(*, actor, source, destination):
    """Record a same-connection tree change for an atomic metadata worker."""
    _validate(source, destination, actor)
    job, _ = StorageMoveJob.objects.get_or_create(
        actor=actor,
        kind="item_tree_move",
        space=source.space,
        source_path=str(source.reference.pk),
        destination_path=str(destination.reference.pk),
        state__in=["queued", "running", "conflict"],
        defaults={
            "source_identity": str(source.reference.pk),
            "payload": {
                "source": source.descriptor(),
                "destination": destination.descriptor(),
                "title": source.name,
                "destination_title": destination.name,
            },
        },
    )
    transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


def _locations(job):
    job.actor.refresh_from_db()
    source = resolve_location(job.source_path, job.actor)
    destination = resolve_location(job.destination_path, job.actor, destination=True)
    if (source.descriptor(), destination.descriptor()) != (
        job.payload["source"],
        job.payload["destination"],
    ):
        raise quota.StorageWriteConflict("A folder location changed.")
    _validate(source, destination, job.actor)
    return source, destination


def _refresh_target_policy(source, destination, actor):
    """Resolve authoritative owners before entering the metadata transaction."""
    if not destination.space.attribute_to_creator:
        inventory.refresh_policy(
            destination.space.owner or actor, organization=destination.backend.organization
        )
        return
    owners = Item.objects.filter(
        path__descendants=source.reference.path, type__in=["file", "docs"]
    ).values("creator_id")
    for owner in User.objects.filter(pk__in=owners).iterator(chunk_size=100):
        inventory.refresh_policy(owner, organization=destination.backend.organization)


def _records(source, destination):
    """Keep every object key and creator while deriving its new quota attribution."""
    items = Item.objects.filter(path__descendants=source.reference.path)
    if (
        items.exclude(type="docs")
        .exclude(storage_space=source.space, storage_backend=source.backend)
        .exists()
    ):
        raise quota.StorageWriteConflict("The folder contains another storage allocation.")
    if items.filter(type__in=["file", "docs"], storageusage__isnull=True).exists():
        raise quota.StorageWriteConflict("Reconcile this folder's accounting before moving it.")
    usages = StorageUsage.objects.filter(item__path__descendants=source.reference.path)
    quota.guard_metadata_change(usages)
    for usage in usages.select_related("item__creator").order_by("key").iterator(chunk_size=500):
        if usage.item.type == "docs":
            if usage.attribution_conflict:
                raise quota.StorageWriteConflict("Resolve document ownership first.")
            target = document_attribution(
                usage.item, placement_override=(destination.reference, destination.space)
            )
            yield usage, {"path": usage.path, **target}
            continue
        if usage.item.type != "file":
            continue
        if (
            usage.attribution_conflict
            or LockService(usage.item).is_locked()
            or (not usage.item.hard_deleted_at and usage.item.effective_upload_state() != "ready")
        ):
            raise quota.StorageWriteConflict(
                "Resolve file ownership or close editing sessions first."
            )
        planned = Item(
            creator=usage.item.creator,
            storage_backend=destination.backend,
            storage_space=destination.space,
        )
        target = inventory.item_attribution(planned)
        if destination.space.attribute_to_creator and target["owner"] is None:
            raise quota.StorageWriteConflict("Assign the file's creator before moving it.")
        yield (
            usage,
            {
                "path": usage.path,
                "organization": target["organization"],
                "owner": target["owner"],
                "space": destination.space,
                "scope_keys": target["scope_keys"],
            },
        )


@transaction.atomic
def _move(job):
    source, destination = _locations(job)
    list(
        Item.objects.select_for_update()
        .filter(pk__in=[source.reference.pk, destination.reference.pk])
        .order_by("pk")
    )
    records = iter(_records(source, destination))
    first = next(records, None)
    if first:
        usage, target = first
        operation = quota.admit(
            key=usage.key,
            actor=job.actor,
            size=usage.size,
            target_scopes=target["scope_keys"],
            lifetime=timedelta(hours=1),
            publication_key=quota.resource_key(f"item-tree:{source.reference.pk}"),
        )
        prepare_transfer(operation, records)
        quota.begin_publication(
            operation.pk,
            size=usage.size,
            observed_version=usage.version,
            publication={
                "kind": "item_tree_move",
                "job_id": str(job.pk),
                "target_attribution": {
                    "owner_id": str(target["owner"].pk) if target["owner"] else None,
                    "space_id": str(destination.space.pk),
                    "organization": target["organization"],
                    "path": usage.path,
                },
            },
        )
        finish_transfer(operation.pk, version=usage.version)
        job.operation = operation
    previous = source.reference.path
    parent = source.reference.parent() if source.reference.depth > 1 else None
    target_path = f"{destination.reference.path}.{source.reference.pk}"
    Item.objects.filter(pk=source.reference.pk).update(
        path=target_path, storage_space=destination.space
    )
    Item.objects.filter(path__descendants=previous).update(
        path=RawSQL("%s || subpath(path, nlevel(%s))", (target_path, str(previous))),
    )
    Item.objects.filter(path__descendants=target_path).exclude(type="docs").update(
        storage_space=destination.space,
    )
    source.reference.refresh_from_db()
    queue_tree_changes(source.reference)
    revoke_item_tree_links(target_path)
    record_item_activity(
        item=source.reference,
        actor=job.actor,
        action=ItemActivityActionChoices.MOVED,
        payload={
            "old_parent_id": str(parent.pk) if parent else None,
            "old_parent_name": parent.title if parent else None,
            "new_parent_id": str(destination.reference.pk),
            "new_parent_name": destination.reference.title,
        },
    )
    job.state, job.reason = "done", ""
    job.payload = {**job.payload, "result": job.source_path}
    job.save(update_fields=["state", "reason", "payload", "operation", "updated_at"])


def execute_item_tree_move(job):
    """All references and charges commit together; a crash rolls back the entire tree change."""
    if job.state in {"done", "failed", "conflict"}:
        return job.state
    try:
        source, destination = _locations(job)
        with namespace_guard(source.backend, exclusive=True):
            _refresh_target_policy(source, destination, job.actor)
            _move(job)
        return "done"
    except StorageOperationBusy:
        return "busy"
    except APIException as exc:
        job.state, job.reason = "conflict", str(exc.detail)[:255]
        job.save(update_fields=["state", "reason", "updated_at"])
        return "conflict"
