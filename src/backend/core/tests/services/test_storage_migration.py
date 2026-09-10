"""Unified storage backfill preserves identities, access and existing policy ceilings."""

from datetime import timedelta

from django.contrib.auth.models import Group
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

import pytest

from core import factories, models
from core.services.storage_inventory import initialize_items
from core.services.storage_migration import migrate_storage, migration_report, rebind_usage
from core.services.storage_quota import apply_policy


@pytest.mark.django_db(transaction=True)
def test_repeatable_backfill_preserves_shared_trees_keys_and_quota(settings):
    """Two passes retain old links/accesses and add accounting scopes exactly once."""
    settings.MOUNTS_REGISTRY = []
    alice, bob = factories.UserFactory.create_batch(2, claims={})
    root = factories.ItemFactory(type="folder", creator=alice)
    child = models.Item.objects.create_child(
        parent=root, creator=bob, type="file", filename="shared.txt", title="Shared", size=7
    )
    standalone = factories.ItemFactory(type="file", creator=alice, size=3)
    models.ItemAccess.objects.create(item=root, user=alice, role="owner")
    models.ItemAccess.objects.create(item=child, user=bob, role="editor")
    orphan = models.Item.objects.create(
        type="file", creator=None, title="orphan.txt", filename="orphan.txt", size=5
    )
    models.ItemAccess.objects.create(item=orphan, user=alice, role="owner")
    trashed = models.Item.objects.create_child(
        parent=root,
        creator=alice,
        type="file",
        title="deleted.txt",
        filename="deleted.txt",
        size=2,
        deleted_at=timezone.now(),
    )
    reader = factories.UserFactory(claims={})
    group = Group.objects.create(name="Migration readers")
    reader.groups.add(group)
    models.ItemAccess.objects.create(item=root, team=f"group:{group.pk}", role="reader")
    objects = (root, child, standalone, orphan, trashed)
    keys = {item.pk: item.file_key for item in objects if item.type == "file"}
    paths = {item.pk: list(item.path) for item in objects}
    before_rights = {
        (item.pk, user.pk): (
            item.get_abilities(user)["retrieve"],
            item.get_abilities(user)["update"],
        )
        for item in objects
        for user in (alice, bob, reader)
    }
    initialize_items()
    for usage in models.StorageUsage.objects.all():
        rebind_usage(
            usage, {"scope_keys": [key for key in usage.scope_keys if key != "instance:drive"]}
        )
    apply_policy({"backend:s3": {"limit_bytes": 11}}, revision="original")
    before = migration_report()
    assert before["unmapped_items"] == 5
    assert not models.StorageSpace.objects.exists()
    settings.STORAGE_GOVERNANCE_ENABLED = True
    settings.STORAGE_MIGRATION_MODE = True
    first = migrate_storage()
    assert first["unmapped_items"] == 0
    assert migrate_storage() == first
    assert models.StorageSpace.objects.count() == 3
    for item in models.Item.objects.all():
        assert list(item.path) == paths[item.pk]
        for user in (alice, bob, reader):
            assert (
                item.get_abilities(user)["retrieve"],
                item.get_abilities(user)["update"],
            ) == before_rights[(item.pk, user.pk)]
        if item.pk in keys:
            assert item.file_key == keys[item.pk]
    orphan.refresh_from_db()
    trashed.refresh_from_db()
    assert orphan.creator_id is None
    assert trashed.deleted_at is not None
    child.refresh_from_db()
    assert child.get_abilities(bob)["update"]
    assert models.StorageQuota.objects.get(key="backend:s3").limit_bytes == 11
    assert models.StorageQuota.objects.get(key="instance:drive").used_bytes == 17
    assert models.StorageQuota.objects.get(key=f"user:{bob.pk}").used_bytes == 7


@pytest.mark.django_db(transaction=True)
def test_registry_import_retains_existing_audience_and_public_tokens(settings, tmp_path):
    """Import uses stable IDs and keeps secret references under external management."""
    user = factories.UserFactory(claims={})
    settings.MOUNTS_REGISTRY = [
        {
            "mount_id": "legacy-nas",
            "display_name": "Files",
            "provider": "localfs",
            "params": {"root_dir": str(tmp_path)},
        }
    ]
    settings.STORAGE_GOVERNANCE_ENABLED = True
    settings.STORAGE_MIGRATION_MODE = True
    link = models.MountShareLink.objects.create(
        mount_id="legacy-nas",
        normalized_path="/shared.txt",
        created_by=user,
        token="synthetic-migration-token",
    )
    assert migration_report()["unregistered_mounts"] == ["legacy-nas"]
    assert not migrate_storage()["unregistered_mounts"]
    space = models.StorageSpace.objects.get(backend__registry_id="legacy-nas")
    assert space.grants.get(user=user).writable
    assert not space.backend.managed
    link.refresh_from_db()
    assert link.mount_id == str(space.pk) and link.token == "synthetic-migration-token"
    migrate_storage()
    assert models.StorageSpace.objects.count() == models.StorageGrant.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_favorites_migration_merges_views_without_losing_favorite_or_visit():
    """Migrate real duplicate rows, retaining both favorite intent and latest visit."""
    previous = [("core", "0046_mounted_share_resource")]
    current = [("core", "0047_resource_favorites_across_views")]
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    executor.migrate(previous)
    try:
        old = executor.loader.project_state(previous).apps.get_model(
            "core", "StorageResourceFavorite"
        )
        user = factories.UserFactory()
        backend = models.StorageBackend.objects.create(
            registry_id="favorite-migration", name="NAS", organization="local"
        )
        first = models.StorageSpace.objects.create(
            backend=backend, name="Private", root_path="/a", owner=user
        )
        second = models.StorageSpace.objects.create(backend=backend, name="All", owner=user)
        resource = models.StorageResource.objects.create(
            namespace=backend.namespace,
            identity_key="f" * 64,
            provider_identity="fixture",
            path="/a/file",
            parent_path="/a",
            name="file",
            kind="file",
            version="fixture",
        )
        recent = timezone.now()
        old.objects.create(
            user_id=user.pk,
            resource_id=resource.pk,
            space_id=first.pk,
            favorite=True,
            last_opened_at=recent - timedelta(days=1),
        )
        kept = old.objects.create(
            user_id=user.pk,
            resource_id=resource.pk,
            space_id=second.pk,
            favorite=False,
            last_opened_at=recent,
        )
        MigrationExecutor(connection).migrate(current)
        favorite = models.StorageResourceFavorite.objects.get(user=user, resource=resource)
        assert favorite.pk == kept.pk and favorite.favorite and favorite.last_opened_at == recent
        assert favorite.space_id == second.pk
        historical = MigrationExecutor(connection).loader.project_state(current).apps
        historical.get_model("core", "StorageSpace").objects.get(pk=second.pk).delete()
        favorite.refresh_from_db()
        assert favorite.favorite and favorite.space_id is None
    finally:
        MigrationExecutor(connection).migrate(latest)
