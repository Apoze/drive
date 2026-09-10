"""A native replacement never inherits a document's stored location identity."""

from types import SimpleNamespace
from unittest.mock import patch

from django.db import transaction

import pytest
from rest_framework.exceptions import APIException

from core import factories, models
from core.mounts.providers import localfs
from core.mounts.providers.base import MountProviderError
from core.services.docs_anchors import current_anchor
from core.services.docs_resources import access_ttl


@pytest.mark.django_db(transaction=True)
def test_native_folder_deletion_is_fenced_and_retains_document_bytes(tmp_path, settings):  # noqa: PLR0915
    from datetime import timedelta  # noqa: PLC0415
    from uuid import uuid4  # noqa: PLC0415

    from django.utils import timezone  # noqa: PLC0415

    from rest_framework.exceptions import PermissionDenied  # noqa: PLC0415

    from core.mounts.providers.virtual import _remove_empty_folder  # noqa: PLC0415
    from core.services.docs_anchors import guard_locations, recovery_page  # noqa: PLC0415
    from core.services.docs_lifecycle import change_document  # noqa: PLC0415
    from core.services.docs_quota import initialize_usage  # noqa: PLC0415
    from core.services.storage_inventory import scan_backend  # noqa: PLC0415
    from core.services.storage_quota import StorageWriteConflict  # noqa: PLC0415
    from core.services.storage_recovery import reconcile_operation  # noqa: PLC0415

    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    owner = factories.UserFactory()
    (tmp_path / "folder").mkdir()
    mount = {"provider": "localfs", "params": {"root_dir": str(tmp_path)}}
    settings.MOUNTS_REGISTRY = [{"mount_id": "docs-delete", "enabled": True, **mount}]
    backend = models.StorageBackend.objects.create(
        registry_id="docs-delete", family="mount", name="Storage", organization="local"
    )
    space = models.StorageSpace.objects.create(
        backend=backend, owner=owner, name="Space", root_path="/", explicit_access=True
    )
    models.StorageGrant.objects.create(space=space, user=owner, writable=True, shareable=True)
    with patch("core.services.storage_inventory.refresh_policy"):
        scan_backend(backend.pk)
    anchor = models.StorageResource.objects.get(namespace=backend.namespace, path="/folder")
    document = models.Item.objects.create(type="docs", title="Document", creator=owner)
    models.DocsBinding.objects.create(
        item=document,
        mounted_parent=anchor,
        anchor_space=space,
        state="active",
        applied_revision=1,
    )
    initialize_usage(document, size=7, version="original")
    entry = localfs.stat(mount=mount, normalized_path="/folder")
    with pytest.raises(PermissionDenied):
        _remove_empty_folder(space, owner, localfs, mount, "/folder", entry)
    assert (tmp_path / "folder").is_dir()
    models.ItemAccess.objects.create(item=document, user=owner, role="owner")
    with patch("core.services.storage_recovery.finish_mount_deletion", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            _remove_empty_folder(space, owner, localfs, mount, "/folder", entry)
    assert not (tmp_path / "folder").exists()
    with pytest.raises(StorageWriteConflict):
        with guard_locations((anchor, space)):
            pytest.fail("A delayed creation must not enter a deleting namespace.")
    operation = models.StorageReservation.objects.get(publication__kind="delete")
    operation.expires_at = timezone.now() - timedelta(seconds=1)
    operation.save(update_fields=["expires_at"])
    assert reconcile_operation(operation.pk) == "committed"
    assert reconcile_operation(operation.pk) == "committed"
    document.refresh_from_db()
    anchor.refresh_from_db()
    assert anchor.missing
    assert document.deleted_at and document.docs_binding.state == "trash"
    assert document.storageusage.size == 7
    assert models.StorageQuota.objects.get(key=f"user:{owner.pk}").used_bytes == 7
    assert models.ItemActivity.objects.filter(item=document, action="trashed").count() == 1
    stranger = factories.UserFactory()
    models.StorageGrant.objects.create(space=space, user=stranger, writable=True, shareable=True)
    assert recovery_page(stranger)["results"] == []
    row = recovery_page(owner)["results"][0]
    assert row["can_recover"] and row["state"] == "trash" and row["reason"] == "missing"
    target_backend = models.StorageBackend.objects.create(
        registry_id="docs-recovery", family="s3", name="Recovery", organization="local"
    )
    target = models.Item.objects.create(
        type="folder", title="Recovery", storage_backend=target_backend
    )
    target_space = models.StorageSpace.objects.create(
        backend=target_backend, root_item=target, owner=owner, name="Recovery", explicit_access=True
    )
    models.Item.objects.filter(pk=target.pk).update(storage_space=target_space)
    models.StorageGrant.objects.create(
        space=target_space, user=owner, writable=True, shareable=True
    )
    intent = {
        "action": "recover",
        "document_id": document.docs_binding.document_id,
        "request_key": uuid4(),
        "revision": row["revision"],
        "destination": target.pk,
    }
    with (
        patch("core.services.docs_moves.refresh_policy"),
        patch("core.services.docs_lifecycle.synchronize", return_value=False),
    ):
        with pytest.raises(PermissionDenied):
            change_document(stranger, intent)
        receipt = change_document(owner, intent)
        assert change_document(owner, intent) == receipt
    document.refresh_from_db()
    assert document.parent().pk == target.pk and document.deleted_at
    assert document.docs_binding.mounted_parent_id is None
    assert recovery_page(owner)["results"] == []
    assert document.storageusage.size == 7 and document.storageusage.space_id == target_space.pk
    assert models.StorageQuota.objects.get(key=f"user:{owner.pk}").used_bytes == 7


@pytest.mark.django_db(transaction=True)
def test_native_folder_move_transfers_document_budgets(tmp_path, settings):  # noqa: PLR0915
    from core.services.docs_quota import initialize_usage  # noqa: PLC0415
    from core.services.storage_inventory import scan_backend  # noqa: PLC0415
    from core.services.storage_namespace import namespace_guard  # noqa: PLC0415
    from core.services.storage_quota import StorageQuotaExceeded  # noqa: PLC0415
    from core.services.storage_tree_transfer import move_tree  # noqa: PLC0415

    settings.DOCS_DRIVE_ENABLED = True
    settings.STORAGE_GOVERNANCE_ENABLED = False
    owner, recipient = factories.UserFactory.create_batch(2)
    (tmp_path / "source").mkdir()
    (tmp_path / "target").mkdir()
    mount = {"provider": "localfs", "params": {"root_dir": str(tmp_path)}}
    settings.MOUNTS_REGISTRY = [{"mount_id": "docs-native-move", "enabled": True, **mount}]
    backend = models.StorageBackend.objects.create(
        registry_id="docs-native-move", family="mount", name="Storage", organization="local"
    )
    source_space = models.StorageSpace.objects.create(
        backend=backend, owner=owner, name="Source", root_path="/"
    )
    target_space = models.StorageSpace.objects.create(
        backend=backend, owner=recipient, name="Target", root_path="/target"
    )
    with patch("core.services.storage_inventory.refresh_policy"):
        scan_backend(backend.pk)
    anchor = models.StorageResource.objects.get(namespace=backend.namespace, path="/source")
    document = models.Item.objects.create(type="docs", title="Document", creator=owner)
    models.DocsBinding.objects.create(
        item=document,
        mounted_parent=anchor,
        anchor_space=source_space,
        state="active",
        applied_revision=1,
    )
    initialize_usage(document, size=7, version="original")
    models.StorageQuota.objects.get_or_create(key=f"user:{recipient.pk}")
    models.StorageQuota.objects.filter(key=f"user:{recipient.pk}").update(limit_bytes=6)
    with (
        patch("core.services.storage_inventory.refresh_policy"),
        namespace_guard(backend, exclusive=True),
    ):
        with pytest.raises(StorageQuotaExceeded):
            move_tree(
                space=source_space,
                actor=owner,
                provider=localfs,
                mount=mount,
                source=localfs.stat(mount=mount, normalized_path="/source"),
                destination_path="/target/source",
            )
        assert (tmp_path / "source").is_dir()
        assert not (tmp_path / "target" / "source").exists()
        models.StorageQuota.objects.filter(key=f"user:{recipient.pk}").update(limit_bytes=20)
        move_tree(
            space=source_space,
            actor=owner,
            provider=localfs,
            mount=mount,
            source=localfs.stat(mount=mount, normalized_path="/source"),
            destination_path="/target/source",
        )
    anchor.refresh_from_db()
    document.refresh_from_db()
    assert anchor.path == "/target/source"
    assert document.docs_binding.mounted_parent_id == anchor.pk
    assert document.docs_binding.anchor_space_id == target_space.pk
    assert document.storageusage.owner_id == recipient.pk
    assert document.storageusage.backend_id is None
    assert models.StorageQuota.objects.get(key=f"user:{recipient.pk}").used_bytes == 7
    assert models.StorageQuota.objects.get(key=f"space:{source_space.pk}").used_bytes == 7
    assert models.StorageQuota.objects.get(key=f"space:{target_space.pk}").used_bytes == 7
    assert models.StorageQuota.objects.get(key=f"backend:{backend.namespace}").used_bytes == 0

    # Finalizing a transferred folder replaces the staging UUID; its Docs
    # projection must learn the surviving parent even though no bytes move.
    from core.services.storage_item_tree_move import _finish_native_folder  # noqa: PLC0415

    original = models.StorageResource.objects.create(
        namespace=backend.namespace,
        identity_key="retained-source-folder",
        path="/old",
        parent_path="/",
        name="old",
        kind="folder",
        missing=True,
    )
    child = models.Item.objects.create_child(
        parent=document, type="docs", title="Child", creator=owner
    )
    child_binding = models.DocsBinding.objects.create(
        item=child, state="active", applied_revision=1
    )
    previous_revision = document.docs_binding.revision
    with transaction.atomic():
        _finish_native_folder(original, anchor, SimpleNamespace(space=target_space, path="/source"))
    document.refresh_from_db()
    child_binding.refresh_from_db()
    assert document.docs_binding.mounted_parent_id == original.pk
    assert document.docs_binding.revision == previous_revision + 1
    assert child_binding.revision == 2
    assert not models.StorageResource.objects.filter(pk=anchor.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_anchor_observation_is_bounded_and_never_performs_io_under_lock(tmp_path):
    folder = tmp_path / "documents"
    folder.mkdir()
    mount = {"provider": "localfs", "params": {"root_dir": str(tmp_path)}}
    observed = localfs.stat(mount=mount, normalized_path="/documents")
    backend = models.StorageBackend.objects.create(
        registry_id="anchor-proof", family="mount", name="Storage", organization="local"
    )
    resource = models.StorageResource.objects.create(
        namespace=backend.namespace,
        identity_key="anchor-proof",
        provider_identity=observed.object_identity,
        path="/documents",
        parent_path="/",
        name="Documents",
        kind="folder",
    )
    with patch("core.services.docs_anchors.native_connection", return_value=mount) as native:
        with transaction.atomic(), pytest.raises(APIException) as error:
            current_anchor(resource, backend)
        assert error.value.status_code == 503
        native.assert_not_called()
        assert current_anchor(resource, backend)
        item = SimpleNamespace(_docs_access_deadline=resource._docs_anchor_deadline)
        assert 0 < access_ttl(item) <= 10
        with patch(
            "core.services.docs_resources.time.time", return_value=item._docs_access_deadline + 1
        ):
            with pytest.raises(APIException) as expired:
                access_ttl(item)
            assert expired.value.status_code == 503
        with transaction.atomic():
            assert current_anchor(resource, backend)
        assert native.call_count == 1
        # Keep the old inode allocated, so replacement is deterministic.
        folder.rename(tmp_path / "old-documents")
        folder.mkdir()
        assert current_anchor(resource, backend)  # Bounded observation lease.
        with patch("core.services.docs_anchors.cache.get", return_value=None):
            assert not current_anchor(resource, backend)
            folder.rmdir()
            assert not current_anchor(resource, backend)
            with (
                patch(
                    "core.services.docs_anchors.get_mount_provider",
                    side_effect=MountProviderError("timeout", "retry", "Unavailable", "timeout"),
                ),
                pytest.raises(APIException) as error,
            ):
                current_anchor(resource, backend)
            assert error.value.status_code == 503
        resource.refresh_from_db()
        assert not resource.missing  # Neither absence nor outage destroys metadata.
        resource.provider_identity = ""
        assert not current_anchor(resource, backend)
