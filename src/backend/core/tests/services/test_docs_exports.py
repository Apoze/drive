"""An uncertain PDF publication resumes without exporting later native edits."""

import hashlib
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from django.utils import timezone

import pytest

from core import factories, models
from core.services.docs_exports import export_file
from core.services.docs_quota import initialize_usage
from core.services.storage_inventory import scan_backend


@pytest.mark.django_db(transaction=True)
def test_pdf_publication_recovery_after_native_edit(tmp_path, settings):
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = True
    models.StorageQuota.objects.create(key="backend:s3", accounting_ready_at=timezone.now())
    user = factories.UserFactory()
    settings.MOUNTS_REGISTRY = [
        {
            "mount_id": "pdf-export",
            "provider": "localfs",
            "enabled": True,
            "params": {"root_dir": str(tmp_path)},
        }
    ]
    backend = models.StorageBackend.objects.create(
        registry_id="pdf-export", family="mount", name="Storage", organization="local"
    )
    space = models.StorageSpace.objects.create(
        backend=backend, owner=user, root_path="/", name="Space", explicit_access=True
    )
    models.StorageGrant.objects.create(space=space, user=user, writable=True, shareable=True)
    (tmp_path / "Folder").mkdir()
    with patch("core.services.storage_inventory.refresh_policy"):
        scan_backend(backend.pk)
    folder = models.StorageResource.objects.get(namespace=backend.namespace, path="/Folder")
    document = models.Item.objects.create(type="docs", title="Document", creator=user)
    binding = models.DocsBinding.objects.create(
        item=document, mounted_parent=folder, anchor_space=space, state="active", applied_revision=1
    )
    models.ItemAccess.objects.create(item=document, user=user, role="owner")
    binding.refresh_from_db()
    initialize_usage(document, size=3, version="original")
    pdf = b"%PDF-1.4\nCaptured version\n%%EOF"
    data = {
        "document_id": binding.document_id,
        "revision": binding.revision,
        "version": "original",
        "request_key": uuid4(),
        "destination": folder.pk,
        "space_id": space.pk,
        "name": "Captured.pdf",
        "size": len(pdf),
        "digest": hashlib.sha256(pdf).hexdigest(),
    }
    with (
        patch("core.services.storage_inventory.refresh_policy"),
        patch(
            "core.services.storage_mount_write.quota.commit",
            side_effect=OSError("interrupted acknowledgement"),
        ),
    ):
        result = export_file(user, data, BytesIO(pdf))
    job = models.StorageMoveJob.objects.get(pk=result["id"])
    assert job.operation.state == "publishing"
    assert (tmp_path / "Folder" / "Captured.pdf").read_bytes() == pdf
    document.title = "Later native edit"
    document.save(update_fields=["title"])
    models.StorageUsage.objects.filter(item=document).update(version="later")
    with patch("core.services.storage_inventory.refresh_policy"):
        result = export_file(user, data, BytesIO(b""))
    assert result["state"] == "done"
    job.refresh_from_db()
    assert job.operation.state == "committed"
    assert not models.StorageQuota.objects.exclude(reserved_bytes=0).exists()
    assert (tmp_path / "Folder" / "Captured.pdf").read_bytes() == pdf
    assert export_file(user, data, BytesIO(b""))["resource_id"] == result["resource_id"]
