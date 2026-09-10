"""Repeatable metadata-only migration, retaining file identities and historical budgets."""

import uuid

from django.conf import settings
from django.db import transaction

from core.models import (
    Item,
    ItemAccess,
    MountShareLink,
    StorageBackend,
    StorageGrant,
    StorageMoveJob,
    StorageReservation,
    StorageSpace,
    StorageUsage,
    User,
)
from core.mounts.registry import get_mount_provider
from core.services import storage_quota as quota
from core.services.storage_inventory import item_attribution, item_usage, organization_for


def migration_report():
    """Dry-run counts do not read credentials, touch storage or create any database rows."""
    roots = Item.objects.filter(path__depth=1, storage_backend__isnull=True)
    ambiguous = []
    for root in roots.select_related("creator").iterator(chunk_size=200):
        organizations = {
            organization_for(item.creator)
            for item in Item.objects.filter(path__descendants=root.path)
            .select_related("creator")
            .iterator(chunk_size=500)
        }
        if len(organizations) > 1:
            ambiguous.append(str(root.pk))
    registered = set(StorageBackend.objects.values_list("registry_id", flat=True))
    return {
        "unmapped_items": Item.objects.filter(storage_backend__isnull=True).count(),
        "unmapped_roots": roots.count(),
        "mixed_organization_roots": ambiguous,
        "unregistered_mounts": [
            mount.get("mount_id")
            for mount in settings.MOUNTS_REGISTRY
            if mount.get("mount_id") not in registered
        ],
        "unowned_legacy_links": MountShareLink.objects.filter(
            created_by__isnull=True,
            mount_id__in=[mount.get("mount_id") for mount in settings.MOUNTS_REGISTRY],
        ).count(),
        "unsupported_mounts": [
            mount["mount_id"]
            for mount in settings.MOUNTS_REGISTRY
            if not getattr(
                get_mount_provider(mount["provider"]), "supports_virtual_roots", lambda **_: False
            )(mount=mount)
        ],
        "implicit_spaces": StorageSpace.objects.filter(explicit_access=False).count(),
        "active_operations": StorageReservation.objects.filter(
            state__in=["reserved", "writing", "publishing"]
        ).count(),
        "active_moves": StorageMoveJob.objects.filter(state__in=["queued", "running"]).count(),
    }


@transaction.atomic
def rebind_usage(usage, destination):
    """Move a confirmed charge between scopes once; no network operation is involved."""
    usage = StorageUsage.objects.select_for_update().get(pk=usage.pk)
    if StorageReservation.objects.filter(
        resource_key=usage.key, state__in=["reserved", "writing", "publishing"]
    ).exists():
        raise quota.StorageWriteConflict("Reconcile active publications before migration.")
    old, new = set(usage.scope_keys), set(destination["scope_keys"])
    quota.ensure_accounts(old | new)
    accounts = quota.lock_accounts(old | new)
    for account in accounts:
        account.used_bytes += usage.size * (int(account.key in new) - int(account.key in old))
        if account.used_bytes < 0:
            raise quota.StorageWriteConflict("Accounting requires reconciliation.")
        account.save(update_fields=["used_bytes"])
    for key, value in destination.items():
        setattr(usage, key, sorted(new) if key == "scope_keys" else value)
    usage.save()


@transaction.atomic
def migrate_root(root_id):
    """One tree transaction preserves old paths, UUIDs, object keys, access rows and links."""
    root = Item.objects.select_for_update(of=("self",)).select_related("creator").get(pk=root_id)
    if root.storage_backend_id:
        return
    organization = organization_for(root.creator)
    identity = uuid.uuid5(uuid.NAMESPACE_URL, f"drive:legacy-s3:{organization}")
    backend, _ = StorageBackend.objects.get_or_create(
        pk=identity,
        defaults={
            "registry_id": f"legacy-s3-{identity}",
            "family": "s3",
            "legacy_s3": True,
            "name": "Drive S3",
            "organization": organization,
            "connection_status": "ready",
        },
    )
    previous_maintenance, previous_pending = backend.maintenance, backend.attribution_pending
    StorageBackend.objects.filter(pk=backend.pk).update(maintenance=True)
    Item.objects.filter(path__descendants=root.path).update(storage_backend=backend)
    root.refresh_from_db()
    space, _ = StorageSpace.objects.get_or_create(
        root_item=root,
        defaults={
            "backend": backend,
            "name": root.title,
            "attribute_to_creator": True,
            "explicit_access": True,
            "allow_sharing": True,
        },
    )
    Item.objects.filter(path__descendants=root.path).update(storage_space=space)
    StorageBackend.objects.filter(pk=backend.pk).update(
        maintenance=previous_maintenance, attribution_pending=previous_pending
    )
    for access in (
        ItemAccess.objects.filter(item__path__descendants=root.path)
        .select_related("item")
        .iterator(chunk_size=500)
    ):
        StorageGrant.objects.get_or_create(
            space=space,
            user_id=access.user_id,
            team=access.team or "",
            root_item_id=None if access.item_id == root.pk else access.item_id,
            defaults={
                "writable": access.role in {"owner", "administrator", "admin", "editor"},
                "shareable": access.role in {"owner", "administrator", "admin"},
            },
        )


def migrate_storage():
    """Caller has drained all writers and enabled the deployment maintenance fence."""
    if not settings.STORAGE_MIGRATION_MODE or not settings.STORAGE_GOVERNANCE_ENABLED:
        raise quota.StorageWriteConflict(
            "Enable governance and migration mode on all writers first."
        )
    report = migration_report()
    if (
        report["mixed_organization_roots"]
        or report["unowned_legacy_links"]
        or report["unsupported_mounts"]
        or report["active_operations"]
        or report["active_moves"]
    ):
        raise quota.StorageWriteConflict(
            "Resolve the dry-run ambiguities and active operations first."
        )
    for mount in settings.MOUNTS_REGISTRY:
        import_registry_mount(mount)
    for root_id in (
        Item.objects.filter(path__depth=1, storage_backend__isnull=True)
        .values_list("pk", flat=True)
        .iterator(chunk_size=200)
    ):
        migrate_root(root_id)
    for space in StorageSpace.objects.filter(explicit_access=False).iterator(chunk_size=200):
        with transaction.atomic():
            if space.owner_id:
                StorageGrant.objects.get_or_create(
                    space=space,
                    user_id=space.owner_id,
                    path="/",
                    defaults={"writable": True, "shareable": True},
                )
            StorageSpace.objects.filter(pk=space.pk).update(explicit_access=True)
    for item in (
        Item.objects.filter(type="file")
        .select_related("creator", "storage_backend", "storage_space__owner")
        .iterator(chunk_size=500)
    ):
        usage = item_usage(item)
        destination = item_attribution(item)
        destination["owner"] = usage.owner
        scopes = [
            key
            for key in destination["scope_keys"]
            if not key.startswith(("user:", "user-backend:"))
        ]
        if usage.owner_id:
            scopes.append(f"user:{usage.owner_id}")
            scopes.extend(
                f"user-backend:{usage.owner_id}:{key.removeprefix('backend:')}"
                for key in tuple(scopes)
                if key.startswith("backend:")
            )
        destination["scope_keys"] = scopes
        rebind_usage(usage, destination)
    for usage in StorageUsage.objects.filter(item__isnull=True).iterator(chunk_size=500):
        rebind_usage(usage, {"scope_keys": sorted(set(usage.scope_keys) | {"instance:drive"})})
    return migration_report()


@transaction.atomic
def import_registry_mount(mount):
    """Keep external secret references and exactly the legacy authenticated audience."""
    if StorageBackend.objects.filter(registry_id=mount["mount_id"]).exists():
        return
    identity = uuid.uuid5(uuid.NAMESPACE_URL, f"drive:legacy-mount:{mount['mount_id']}")
    backend = StorageBackend.objects.create(
        pk=identity,
        registry_id=mount["mount_id"],
        namespace=identity,
        name=mount["display_name"],
        organization=settings.STORAGE_ORGANIZATION_ID,
        enabled=mount.get("enabled", True),
        managed=False,
    )
    space = StorageSpace.objects.create(
        pk=uuid.uuid5(identity, "legacy-space"),
        backend=backend,
        name=backend.name,
        explicit_access=True,
        enabled=backend.enabled,
    )
    # The old registry was visible to every authenticated account. Keep those
    # existing accounts; new accounts now receive explicit space assignments.
    for user_id in User.objects.values_list("pk", flat=True).iterator(chunk_size=200):
        StorageGrant.objects.create(space=space, user_id=user_id, writable=True, shareable=True)
    MountShareLink.objects.filter(mount_id=mount["mount_id"]).update(mount_id=str(space.pk))
