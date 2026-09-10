"""One NAS connection can expose private virtual roots without path escape."""

from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

import pytest
from rest_framework.test import APIClient

from core import factories, models
from core.mounts.providers import virtual
from core.mounts.providers.base import MountProviderError
from core.services.storage_inventory import initialize_items, scan_backend
from core.services.storage_move_job import execute_move
from core.services.storage_quota import StorageQuotaExceeded, StorageWriteConflict, apply_policy
from core.services.storage_recovery import cleanup_operation, reconcile_operation, restore_backup
from core.services.storage_spaces import resolve_space_mount
from core.services.storage_tree_transfer import enter_maintenance, reclassify_backend
from wopi.services.lock import MountLockService


# Fixture scenarios keep setup and assertions together.
# pylint: disable=too-many-locals,too-many-statements
@pytest.mark.django_db
# pylint: disable-next=too-many-statements
def test_virtual_root_discovery_streaming_and_revocation(tmp_path):  # noqa: PLR0915
    """A private root cannot reveal a sibling through raw mounts or symlinks."""
    (tmp_path / "alice").mkdir()
    (tmp_path / "alice" / "hello.txt").write_text("hello")
    (tmp_path / "bob").mkdir()
    (tmp_path / "bob" / "private.txt").write_text("private")
    (tmp_path / "alice" / "escape").symlink_to(tmp_path / "bob", target_is_directory=True)
    user = factories.UserFactory()
    stranger = factories.UserFactory()
    operator = factories.UserFactory(is_staff=True, is_superuser=True)
    backend = models.StorageBackend.objects.create(
        registry_id="nas", name="NAS", organization="lab"
    )
    space = models.StorageSpace.objects.create(
        backend=backend,
        name="Personal",
        root_path="/alice",
        owner=user,
    )
    shared = models.StorageSpace.objects.create(backend=backend, name="Whole NAS")
    models.StorageGrant.objects.create(space=shared, user=operator, writable=True)
    registry = [
        {
            "mount_id": "nas",
            "display_name": "NAS",
            "enabled": True,
            "provider": "localfs",
            "params": {"root_dir": str(tmp_path)},
        }
    ]
    with override_settings(STORAGE_GOVERNANCE_ENABLED=True, MOUNTS_REGISTRY=registry):
        client = APIClient()
        client.force_authenticate(user)
        response = client.get("/api/v1.0/mounts/")
        assert response.status_code == 200
        assert [entry["mount_id"] for entry in response.data] == [str(space.pk)]
        assert client.get("/api/v1.0/mounts/nas/").status_code == 404
        mount = resolve_space_mount(space.pk, user)
        assert [
            entry.name for entry in virtual.list_children(mount=mount, normalized_path="/")
        ] == ["hello.txt"]
        with virtual.open_read(mount=mount, normalized_path="/hello.txt") as stream:
            assert stream.read(5) == b"hello"
        with pytest.raises(MountProviderError):
            with virtual.open_read(mount=mount, normalized_path="/escape/private.txt"):
                pytest.fail("A symlink must not cross the virtual root")
        assert resolve_space_mount(space.pk, stranger) is None
        scan_backend(backend.pk)
        scan_backend(backend.pk)
        initialize_items()
        observed = virtual.stat(mount=mount, normalized_path="/hello.txt")
        (tmp_path / "alice" / "hello.txt").write_text("external edit")
        with pytest.raises(StorageWriteConflict, match="opened for editing"):
            virtual.write_stream(
                mount=mount,
                final_path="/hello.txt",
                chunks=[b"stale editor"],
                expected_entry=observed,
            )
        assert (tmp_path / "alice" / "hello.txt").read_text() == "external edit"
        (tmp_path / "alice" / "hello.txt").write_text("hello")
        with pytest.raises(ValidationError, match="identities before"):
            models.UserReconciliation(
                active_user=user, inactive_user=stranger
            ).process_reconciliation_request()
        with (
            patch(
                "core.mounts.providers.localfs.capacity",
                return_value={"caller_available_bytes": 0},
            ),
            pytest.raises(StorageWriteConflict, match="insufficient space"),
        ):
            virtual.write_stream(mount=mount, final_path="/hello.txt", chunks=[b"new"])
        assert (tmp_path / "alice" / "hello.txt").read_bytes() == b"hello"
        assert not models.StorageReservation.objects.filter(
            state__in=["reserved", "writing", "publishing"]
        ).exists()
        space.root_path = "/changed"
        with pytest.raises(ValidationError, match="maintenance"):
            space.clean()
        space.root_path = "/alice"
        assert models.StorageQuota.objects.get(key="organization:lab").used_bytes == 12
        assert models.StorageQuota.objects.get(key=f"user:{user.pk}").used_bytes == 5
        (tmp_path / "alice" / "external.txt").write_text("more")
        (tmp_path / "alice" / "hello.txt").unlink()
        scan_backend(backend.pk)
        assert models.StorageQuota.objects.get(key="organization:lab").used_bytes == 11
        assert models.StorageQuota.objects.get(key=f"user:{user.pk}").used_bytes == 4
        apply_policy({"organization:lab": {"limit_bytes": 14}}, revision="test")
        with pytest.raises(StorageQuotaExceeded):
            virtual.write_stream(mount=mount, final_path="/rejected.txt", chunks=[b"x" * 20])
        assert not (tmp_path / "alice" / "rejected.txt").exists()
        assert not models.StorageResource.objects.filter(
            namespace=backend.namespace, path="/alice/rejected.txt", missing=False
        ).exists()
        with pytest.raises(StorageQuotaExceeded):
            virtual.write_stream(mount=mount, final_path="/external.txt", chunks=[b"x" * 20])
        assert (tmp_path / "alice" / "external.txt").read_text() == "more"
        virtual.write_stream(mount=mount, final_path="/external.txt", chunks=[b"longer"])
        assert models.StorageQuota.objects.get(key="organization:lab").used_bytes == 13
        apply_policy({"organization:lab": {"limit_bytes": 8}}, revision="lower")
        virtual.write_stream(mount=mount, final_path="/external.txt", chunks=[b"new"])
        assert models.StorageQuota.objects.get(key="organization:lab").used_bytes == 10
        assert (tmp_path / "alice" / "external.txt").read_bytes() == b"new"
        whole_mount = resolve_space_mount(shared.pk, operator)
        virtual.mkdirs(mount=whole_mount, normalized_path="/target")
        enter_maintenance(backend)
        models.StorageSpace.objects.create(
            backend=backend,
            name="Target",
            root_path="/target",
            owner=stranger,
        )
        reclassify_backend(backend.pk, operator.pk)
        apply_policy({f"user:{stranger.pk}": {"limit_bytes": 2}}, revision="destination")
        with pytest.raises(StorageQuotaExceeded):
            virtual.rename(
                mount=whole_mount,
                src_normalized_path="/alice/external.txt",
                dst_normalized_path="/target/moved.txt",
            )
        assert (tmp_path / "alice" / "external.txt").read_bytes() == b"new"
        apply_policy({f"user:{stranger.pk}": {"limit_bytes": 3}}, revision="destination-raised")
        virtual.rename(
            mount=whole_mount,
            src_normalized_path="/alice/external.txt",
            dst_normalized_path="/target/moved.txt",
        )
        assert (tmp_path / "target" / "moved.txt").read_bytes() == b"new"
        assert models.StorageQuota.objects.get(key="organization:lab").used_bytes == 10
        assert models.StorageQuota.objects.get(key=f"user:{user.pk}").used_bytes == 0
        assert models.StorageQuota.objects.get(key=f"user:{stranger.pk}").used_bytes == 3
        (tmp_path / "alice" / "folder").mkdir()
        (tmp_path / "alice" / "folder" / "part.txt").write_bytes(b"batch")
        scan_backend(backend.pk)
        with pytest.raises(StorageQuotaExceeded):
            virtual.rename(
                mount=whole_mount,
                src_normalized_path="/alice/folder",
                dst_normalized_path="/target/folder",
            )
        assert (tmp_path / "alice" / "folder" / "part.txt").read_bytes() == b"batch"
        apply_policy({f"user:{stranger.pk}": {"limit_bytes": 8}}, revision="folder-raised")
        with patch(
            "core.services.storage_tree_transfer.finish_transfer",
            side_effect=RuntimeError("Interrupted"),
        ):
            with pytest.raises(RuntimeError, match="Interrupted"):
                virtual.rename(
                    mount=whole_mount,
                    src_normalized_path="/alice/folder",
                    dst_normalized_path="/target/folder",
                )
        operation = models.StorageReservation.objects.get(
            publication__kind="tree_move", state="publishing"
        )
        operation.expires_at = timezone.now() - timedelta(seconds=1)
        operation.save()
        assert reconcile_operation(operation.pk) == "committed"
        assert reconcile_operation(operation.pk) == "committed"
        assert models.StorageQuota.objects.get(key="organization:lab").used_bytes == 15
        assert models.StorageQuota.objects.get(key=f"user:{user.pk}").used_bytes == 0
        assert models.StorageQuota.objects.get(key=f"user:{stranger.pk}").used_bytes == 8
        assert (tmp_path / "target" / "folder" / "part.txt").read_bytes() == b"batch"
        retained = models.StorageReservation.objects.get(
            state="committed", publication__backup_size=6
        )
        apply_policy(
            {"organization:lab": {"limit_bytes": 30}, f"user:{stranger.pk}": {"limit_bytes": 30}},
            revision="restore",
        )
        restore_backup(
            retained.pk,
            space_id=shared.pk,
            actor_id=operator.pk,
            destination="/target/recovered.txt",
        )
        assert (tmp_path / "target" / "recovered.txt").read_bytes() == b"longer"
        with pytest.raises(StorageWriteConflict):
            restore_backup(
                retained.pk,
                space_id=shared.pk,
                actor_id=operator.pk,
                destination="/target/recovered.txt",
            )
        virtual.mkdirs(mount=whole_mount, normalized_path="/alice/todelete")
        virtual.write_stream(
            mount=whole_mount, final_path="/alice/todelete/file.txt", chunks=[b"v1"]
        )
        virtual.write_stream(
            mount=whole_mount, final_path="/alice/todelete/file.txt", chunks=[b"v2"]
        )
        saved = models.StorageReservation.objects.get(state="committed", publication__backup_size=2)
        virtual.remove(mount=whole_mount, normalized_path="/alice/todelete/file.txt")
        deleted_file = models.StorageReservation.objects.get(
            state="committed",
            publication__kind="delete",
            publication__source_path="/alice/todelete/file.txt",
        )
        virtual.remove(mount=whole_mount, normalized_path="/alice/todelete")
        assert not (tmp_path / "alice" / "todelete").exists()
        deleted = models.StorageReservation.objects.get(
            state="committed",
            publication__kind="delete",
            publication__source_path="/alice/todelete",
        )
        with override_settings(STORAGE_BACKUP_RETENTION_DAYS=0):
            assert cleanup_operation(saved.pk) == "cleaned"
            assert cleanup_operation(deleted.pk) == "retained"
            assert cleanup_operation(deleted_file.pk) == "cleaned"
            assert cleanup_operation(deleted.pk) == "cleaned"
        virtual.mkdirs(mount=whole_mount, normalized_path="/alice/queued")
        virtual.write_stream(mount=whole_mount, final_path="/alice/queued/q.txt", chunks=[b"q"])
        client.force_authenticate(operator)
        response = client.post(
            f"/api/v1.0/mounts/{shared.pk}/rename/?path=/alice/queued",
            {"name": "finished"},
            format="json",
        )
        assert response.status_code == 202
        job_id = response.data["job_id"]
        status_url = f"/api/v1.0/mounts/{shared.pk}/operations/{job_id}/"
        assert client.get(status_url).status_code == 202
        with patch(
            "core.services.storage_tree_transfer.finish_transfer",
            side_effect=RuntimeError("Interrupted"),
        ):
            assert execute_move(job_id) == "running"
        job = models.StorageMoveJob.objects.get(pk=job_id)
        models.StorageReservation.objects.filter(pk=job.operation_id).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        assert execute_move(job_id) == "done"
        assert execute_move(job_id) == "done"
        assert client.get(status_url).status_code == 200
        assert (tmp_path / "alice" / "finished" / "q.txt").read_bytes() == b"q"
        client.force_authenticate(stranger)
        assert client.get(status_url).status_code == 404
        user.is_active = False
        user.save()
        with pytest.raises(MountProviderError):
            virtual.stat(mount=mount, normalized_path="/hello.txt")


@pytest.mark.django_db
def test_external_replacement_and_rename_across_inventory_batches(tmp_path):
    """A recreated path cannot steal a moved object's attribution in a later batch."""
    user, other = factories.UserFactory.create_batch(2)
    backend = models.StorageBackend.objects.create(
        registry_id="nas", name="NAS", organization="lab"
    )
    for name, owner in (("a", user), ("b", other)):
        (tmp_path / name).mkdir()
        models.StorageSpace.objects.create(
            backend=backend, name=name, root_path=f"/{name}", owner=owner
        )
    original = tmp_path / "a" / "original.txt"
    original.write_bytes(b"old")
    # Exceed the real batch size; metadata staging must work independently of order.
    for index in range(510):
        (tmp_path / "a" / f"empty-{index}").touch()
    registry = [
        {
            "mount_id": "nas",
            "provider": "localfs",
            "enabled": True,
            "params": {"root_dir": str(tmp_path)},
        }
    ]
    with override_settings(MOUNTS_REGISTRY=registry):
        scan_backend(backend.pk)
        charged = models.StorageUsage.objects.get(backend=backend, path="/a/original.txt")
        moved = tmp_path / "b" / "moved.txt"
        original.rename(moved)
        original.write_bytes(b"recreated")
        scan_backend(backend.pk)
        charged.refresh_from_db()
        assert (charged.path, charged.owner_id, charged.attribution_conflict) == (
            "/b/moved.txt",
            user.pk,
            True,
        )
        recreated = models.StorageUsage.objects.get(backend=backend, path="/a/original.txt")
        assert recreated.pk != charged.pk
        assert models.StorageQuota.objects.get(key=f"user:{user.pk}").used_bytes == 12
        replacement = tmp_path / "b" / "replacement.tmp"
        replacement.write_bytes(b"edited externally")
        replacement.replace(moved)
        scan_backend(backend.pk)
        charged.refresh_from_db()
        assert (charged.path, charged.size, charged.owner_id) == ("/b/moved.txt", 17, user.pk)
        assert models.StorageQuota.objects.get(key=f"user:{user.pk}").used_bytes == 26
        assert not models.StorageInventoryEntry.objects.exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("folder", [False, True])
def test_native_move_keeps_reference_and_recovers(tmp_path, settings, folder):  # noqa: PLR0915
    """Separate grants permit one durable native move with no duplicate quota charge."""
    actor = factories.UserFactory()
    stranger = factories.UserFactory()
    backend = models.StorageBackend.objects.create(
        registry_id="move-nas", name="NAS", organization="local"
    )
    destination_backend = models.StorageBackend.objects.create(
        registry_id="move-nas-alias",
        name="NAS alias",
        organization="local",
        namespace=backend.namespace,
        namespace_root="/target",
    )
    spaces = []
    for name in ("source", "target"):
        (tmp_path / name).mkdir()
        spaces.append(
            models.StorageSpace.objects.create(
                backend=backend if name == "source" else destination_backend,
                name=name,
                root_path="/source" if name == "source" else "/",
                owner=actor,
                allow_sharing=True,
            )
        )
    alias = models.StorageSpace.objects.create(
        backend=backend, name="Alias", owner=actor, allow_sharing=False
    )
    source = tmp_path / "source" / "entry"
    if folder:
        source.mkdir()
        (source / "file.txt").write_bytes(b"payload")
    else:
        source.write_bytes(b"payload")
    settings.MOUNTS_REGISTRY = [
        {
            "mount_id": "move-nas",
            "enabled": True,
            "provider": "localfs",
            "params": {"root_dir": str(tmp_path), "capabilities": {"mount.share_link": True}},
        },
        {
            "mount_id": "move-nas-alias",
            "enabled": True,
            "provider": "localfs",
            "params": {
                "root_dir": str(tmp_path / "target"),
                "capabilities": {"mount.share_link": True},
            },
        },
    ]
    settings.STORAGE_GOVERNANCE_ENABLED = True
    settings.STORAGE_UNIFIED_ENABLED = True
    scan_backend(backend.pk)
    initialize_items()
    reference = models.StorageResource.objects.get(
        namespace=backend.namespace, path="/source/entry"
    )
    target = models.StorageResource.objects.get(namespace=backend.namespace, path="/target")
    models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=7)
    edited_path = "/entry/file.txt" if folder else "/entry"
    lock = MountLockService(mount_id=str(spaces[0].pk), normalized_path=edited_path)
    alias_lock = MountLockService(mount_id=str(alias.pk), normalized_path="/source" + edited_path)
    lock.lock("synthetic-native-edit")
    assert alias_lock.get_lock() == "synthetic-native-edit"
    with pytest.raises(StorageWriteConflict, match="Another editing session"):
        alias_lock.lock("other-native-edit")
    with pytest.raises(StorageWriteConflict, match="active editing sessions"):
        virtual.rename(
            mount=resolve_space_mount(spaces[0].pk, actor),
            destination_mount=resolve_space_mount(spaces[1].pk, actor),
            src_normalized_path="/entry",
            dst_normalized_path="/entry",
        )
    alias_lock.unlock()
    assert not lock.is_locked()
    impostor = tmp_path / "impostor"
    impostor.mkdir()
    alias_params = settings.MOUNTS_REGISTRY[1]["params"]
    with patch.dict(alias_params, {"root_dir": str(impostor)}):
        with pytest.raises(StorageWriteConflict, match="same target"):
            virtual.rename(
                mount=resolve_space_mount(spaces[0].pk, actor),
                destination_mount=resolve_space_mount(spaces[1].pk, actor),
                src_normalized_path="/entry",
                dst_normalized_path="/entry",
            )
    assert source.exists()
    client = APIClient()
    client.force_authenticate(stranger)
    request = {
        "source": str(reference.pk),
        "destination": str(target.pk),
        "mode": "move",
        "source_space": str(spaces[0].pk),
        "destination_space": str(spaces[1].pk),
    }
    assert client.post("/api/v1.0/storage-transfers/", request, format="json").status_code == 404
    client.force_authenticate(actor)
    if folder:
        link = models.MountShareLink.objects.create(
            mount_id=str(spaces[0].pk),
            normalized_path="/entry",
            created_by=actor,
            token="synthetic-legacy-link",
        )
    else:
        shared = client.post(
            f"/api/v1.0/mounts/{spaces[0].pk}/share-links/",
            {"path": "/entry"},
            format="json",
        )
        assert shared.status_code == 201
        link = models.MountShareLink.objects.get(resource=reference)
    resource_url = f"/api/v1.0/resources/{reference.pk}/"
    assert client.post(resource_url + f"favorite/?space={spaces[0].pk}").status_code == 204
    assert client.get(resource_url, {"space": str(spaces[0].pk)}).status_code == 200
    assert client.post(resource_url + f"favorite/?space={alias.pk}").status_code == 204
    assert (
        models.StorageResourceFavorite.objects.filter(resource=reference, user=actor).count() == 1
    )
    with patch("core.services.storage_move_job.dispatch_move"):
        queued = client.post("/api/v1.0/storage-transfers/", request, format="json")
    assert queued.status_code == 202, queued.data
    interruption = (
        "core.services.storage_tree_transfer.finish_transfer"
        if folder
        else "core.mounts.providers.virtual.quota.commit"
    )
    with patch(interruption, side_effect=RuntimeError("Interrupted")):
        outcome = execute_move(queued.data["id"])
        assert outcome == "running", models.StorageMoveJob.objects.get(pk=queued.data["id"]).reason
    job = models.StorageMoveJob.objects.get(pk=queued.data["id"])
    assert job.operation_id
    models.StorageReservation.objects.filter(pk=job.operation_id).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    spaces[1].enabled = False
    spaces[1].save(update_fields=["enabled"])
    assert reconcile_operation(job.operation_id) == "conflict"
    job.operation.refresh_from_db()
    assert job.operation.state == "publishing"
    spaces[1].enabled = True
    spaces[1].save(update_fields=["enabled"])
    with patch("core.services.storage_move_job.dispatch_move"):
        assert client.post(f"/api/v1.0/storage-transfers/{job.pk}/recover/").status_code == 202
    assert execute_move(job.pk) == "done"
    assert execute_move(job.pk) == "done"
    reference.refresh_from_db()
    assert reference.path == "/target/entry" and not reference.missing
    for mode in ("favorites", "recent", "search"):
        results = client.get("/api/v1.0/resources/", {"mode": mode, "q": "entry"})
        assert results.status_code == 200
        assert [row["id"] for row in results.data["results"]] == [str(reference.pk)]
        assert results.data["count"] == 1
    assert client.delete(resource_url + f"favorite/?space={spaces[1].pk}").status_code == 204
    assert client.get("/api/v1.0/resources/", {"mode": "favorites"}).data["count"] == 0
    assert not source.exists()
    output = tmp_path / "target" / "entry"
    assert (output / "file.txt" if folder else output).read_bytes() == b"payload"
    account = models.StorageQuota.objects.get(key=f"user:{actor.pk}")
    assert (account.used_bytes, account.reserved_bytes) == (7, 0)
    link.refresh_from_db()
    assert link.resource_id == reference.pk
    public_url = f"/api/v1.0/mount-share-links/{link.token}/browse/"
    assert APIClient().get(public_url).status_code == 200
    # A new object at the previous path must never capture the existing link.
    source.write_bytes(b"replacement")
    scan_backend(backend.pk)
    public = APIClient().get(public_url)
    assert public.status_code == 200
    assert public.data["entry"]["entry_type"] == ("folder" if folder else "file")
    downloaded = APIClient().get(
        f"/api/v1.0/mount-share-links/{link.token}/download/",
        {"path": "/file.txt" if folder else "/"},
    )
    assert downloaded.status_code == 200
    assert b"".join(downloaded.streaming_content) == b"payload"
    spaces[1].allow_sharing = False
    spaces[1].save()
    assert APIClient().get(public_url).status_code == 410
