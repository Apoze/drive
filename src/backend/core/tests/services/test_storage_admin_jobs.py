"""One native fixture verifies broker repair, root creation and reclassification recovery."""

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from core import factories, models
from core.mounts.providers import virtual
from core.services.storage_admin_jobs import execute_admin_job
from core.services.storage_inventory import initialize_items
from core.services.storage_spaces import resolve_space_mount


@pytest.mark.django_db(transaction=True)
# The scenario includes the interrupted journal and its retry, with one native fixture.
# pylint: disable-next=too-many-locals,too-many-statements
def test_administration_delivery_and_reclassification_recovery(settings, tmp_path):  # noqa: PLR0915
    """Retries keep the same publication and never lose already attributed bytes."""
    admin = factories.UserFactory(is_staff=True, is_superuser=True)
    alice, bob = factories.UserFactory.create_batch(2)
    backend = models.StorageBackend.objects.create(
        registry_id="admin-jobs", name="NAS", organization="local"
    )
    space = models.StorageSpace.objects.create(
        backend=backend, name="Personal", root_path="/personal", owner=alice
    )
    settings.STORAGE_GOVERNANCE_ENABLED = True
    settings.MOUNTS_REGISTRY = [
        {
            "mount_id": "admin-jobs",
            "display_name": "NAS",
            "provider": "localfs",
            "enabled": True,
            "params": {"root_dir": str(tmp_path)},
        }
    ]
    api = APIClient()
    api.force_authenticate(admin)
    with patch(
        "core.services.storage_admin_jobs.app.send_task", side_effect=OSError("broker down")
    ):
        root = api.post(f"/api/v1.0/storage-spaces-admin/{space.pk}/initialize-root/")
        assert root.status_code == 202
        job = models.StorageAdminJob.objects.get(pk=root.data["id"])
        assert job.state == "queued"
        assert execute_admin_job(job.pk) == "done"
        assert execute_admin_job(job.pk) == "done"
        assert (tmp_path / "personal").is_dir()
        (tmp_path / "personal" / "file.txt").write_bytes(b"payload")
        inventory = api.post(f"/api/v1.0/storage-connections/{backend.pk}/inventory/")
        assert inventory.status_code == 202
        assert execute_admin_job(inventory.data["id"]) == "done"
        initialize_items()
        assert (
            api.post(f"/api/v1.0/storage-connections/{backend.pk}/maintenance/").status_code == 200
        )
        space.owner = bob
        space.save()
        queued = api.post(f"/api/v1.0/storage-connections/{backend.pk}/reclassify/")
        assert queued.status_code == 202
        with patch(
            "core.services.storage_tree_transfer.finish_transfer",
            side_effect=OSError("worker lost"),
        ):
            assert execute_admin_job(queued.data["id"]) == "failed"
        job = models.StorageAdminJob.objects.get(pk=queued.data["id"])
        assert job.operation_id
        original_operation = job.operation_id
        original_requester = admin.pk
        admin.is_active = False
        admin.save(update_fields=["is_active"])
        admin = factories.UserFactory(is_superuser=True, is_staff=False)
        api.force_authenticate(admin)
        retry = api.post(f"/api/v1.0/storage-administration-jobs/{job.pk}/retry/")
        assert retry.status_code == 202
        assert retry.data["id"] == str(job.pk)
        assert execute_admin_job(job.pk) == "done"
        job.refresh_from_db()
        assert job.operation_id == original_operation
        assert job.payload["requested_by"] == str(original_requester)
        assert job.actor_id == admin.pk
        assert job.operation.state == "committed"
        usage = models.StorageUsage.objects.get(path="/personal/file.txt")
        assert (usage.owner_id, usage.size) == (bob.pk, 7)
        assert models.StorageQuota.objects.get(key=f"user:{bob.pk}").used_bytes == 7
        backend.refresh_from_db()
        assert not backend.maintenance
        models.StorageGrant.objects.create(space=space, user=admin, writable=True)
        mount = resolve_space_mount(space.pk, admin)
        virtual.write_stream(mount=mount, final_path="/file.txt", chunks=[b"updated"])
        retained = api.get("/api/v1.0/storage-administration-jobs/retained-versions/")
        assert retained.status_code == 200 and retained.data["count"] == 1
        restored = api.post(
            "/api/v1.0/storage-administration-jobs/restore/",
            {
                "version": retained.data["results"][0]["id"],
                "space": str(space.pk),
                "path": "/restored.txt",
            },
            format="json",
        )
        assert restored.status_code == 202, restored.data
        with patch(
            "core.services.storage_mount_write.quota.commit", side_effect=OSError("reply lost")
        ):
            assert execute_admin_job(restored.data["id"]) == "failed"
        restoration = models.StorageAdminJob.objects.get(pk=restored.data["id"])
        assert restoration.operation.state == "publishing"
        retry = api.post(f"/api/v1.0/storage-administration-jobs/{restoration.pk}/retry/")
        assert retry.status_code == 202
        assert execute_admin_job(restoration.pk) == "done"
        assert (tmp_path / "personal" / "restored.txt").read_bytes() == b"payload"
        assert (tmp_path / "personal" / "file.txt").read_bytes() == b"updated"
        assert models.StorageQuota.objects.get(key=f"user:{bob.pk}").used_bytes == 14
    api.force_authenticate(alice)
    assert api.get("/api/v1.0/storage-administration-jobs/").status_code == 403
