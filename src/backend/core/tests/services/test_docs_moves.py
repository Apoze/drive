"""One document tree keeps identity and atomic logical budgets across placements."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from core import factories, models
from core.services.docs_lifecycle import change_document
from core.services.docs_quota import initialize_usage
from core.services.storage_quota import StorageQuotaExceeded


@pytest.mark.django_db(transaction=True)
def test_document_move_retries_and_quota_rollback(settings, tmp_path):  # noqa: PLR0915
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    owner, recipient, stranger = factories.UserFactory.create_batch(3)
    roots = []
    for number, account in enumerate([owner, recipient]):
        backend = models.StorageBackend.objects.create(
            registry_id=f"docs-move-{number}", family="s3", name="Storage", organization="local"
        )
        root = models.Item.objects.create(type="folder", title="Root", storage_backend=backend)
        space = models.StorageSpace.objects.create(
            backend=backend, name="Space", root_item=root, owner=account, explicit_access=True
        )
        models.Item.objects.filter(pk=root.pk).update(storage_space=space)
        models.StorageGrant.objects.create(space=space, user=owner, writable=True, shareable=True)
        root.refresh_from_db()
        roots.append(root)
    item = models.Item.objects.create_child(
        parent=roots[0], type="docs", title="Document", creator=owner
    )
    binding = models.DocsBinding.objects.create(item=item, state="active", applied_revision=1)
    models.ItemAccess.objects.create(item=item, user=owner, role="owner")
    child = models.Item.objects.create_child(parent=item, type="docs", title="Child", creator=owner)
    models.DocsBinding.objects.create(item=child, state="active", applied_revision=1)
    initialize_usage(item, size=3, version="first")
    initialize_usage(child, size=4, version="child")
    models.StorageQuota.objects.get_or_create(
        key=f"user:{recipient.pk}", defaults={"limit_bytes": 6}
    )
    intent = {
        "action": "move",
        "document_id": binding.document_id,
        "destination": roots[1].pk,
        "request_key": uuid4(),
    }
    with (
        patch("core.services.docs_moves.refresh_policy"),
        patch("core.services.docs_lifecycle.synchronize", return_value=False),
    ):
        with pytest.raises(PermissionDenied):
            change_document(stranger, intent)
        with pytest.raises(StorageQuotaExceeded):
            change_document(owner, intent)
        item.refresh_from_db()
        assert item.parent().pk == roots[0].pk
        assert models.StorageQuota.objects.get(key=f"user:{owner.pk}").used_bytes == 7
        assert not models.StorageReservation.objects.exists()
        models.StorageQuota.objects.filter(key=f"user:{recipient.pk}").update(limit_bytes=20)
        receipt = change_document(owner, intent)
        assert change_document(owner, intent) == receipt
        with pytest.raises(ValidationError):
            change_document(owner, {**intent, "request_key": uuid4(), "destination": child.pk})
    item.refresh_from_db()
    child.refresh_from_db()
    assert item.parent().pk == roots[1].pk and child.parent().pk == item.pk
    assert item.docs_binding.document_id == binding.document_id
    assert models.StorageQuota.objects.get(key=f"user:{owner.pk}").used_bytes == 0
    assert models.StorageQuota.objects.get(key=f"user:{recipient.pk}").used_bytes == 7
    assert models.StorageQuota.objects.get(key="instance:drive").used_bytes == 7
    assert models.StorageUsage.objects.filter(backend__isnull=False).count() == 0
    assert models.StorageReservation.objects.filter(state="committed").count() == 2

    # Exercise the reverse placement family as well: Item.move increments the
    # binding revision before the native anchor is attached.
    from core.services.storage_inventory import scan_backend  # noqa: PLC0415

    (tmp_path / "folder").mkdir()
    settings.MOUNTS_REGISTRY = [
        {
            "mount_id": "docs-move-native",
            "enabled": True,
            "provider": "localfs",
            "params": {"root_dir": str(tmp_path)},
        }
    ]
    backend = models.StorageBackend.objects.create(
        registry_id="docs-move-native", family="mount", name="Native", organization="local"
    )
    space = models.StorageSpace.objects.create(
        backend=backend, owner=owner, name="Native", root_path="/", explicit_access=True
    )
    models.StorageGrant.objects.create(space=space, user=owner, writable=True, shareable=True)
    with patch("core.services.storage_inventory.refresh_policy"):
        scan_backend(backend.pk)
    anchor = models.StorageResource.objects.get(namespace=backend.namespace, path="/folder")
    with (
        patch("core.services.docs_moves.refresh_policy"),
        patch("core.services.docs_lifecycle.synchronize", return_value=False),
    ):
        move = {**intent, "request_key": uuid4(), "destination": anchor.pk, "space_id": space.pk}
        receipt = change_document(owner, move)
        assert change_document(owner, move) == receipt
        item.refresh_from_db()
        child.refresh_from_db()
        assert item.is_root and child.parent().pk == item.pk
        assert item.docs_binding.mounted_parent_id == anchor.pk
        assert item.storageusage.space_id == space.pk
        assert child.storageusage.space_id == space.pk
        change_document(owner, {**intent, "request_key": uuid4(), "destination": roots[0].pk})
    item.refresh_from_db()
    assert item.parent().pk == roots[0].pk and item.docs_binding.mounted_parent_id is None
    assert models.StorageQuota.objects.get(key="instance:drive").used_bytes == 7
