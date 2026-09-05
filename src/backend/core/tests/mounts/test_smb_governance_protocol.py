"""Opt-in real SMB qualification against the disposable docker/qualification server."""

import os

from django.test import override_settings

import pytest

from core import factories, models
from core.mounts.providers import smb, virtual
from core.mounts.providers.base import MountProviderError
from core.services.storage_inventory import initialize_items, scan_backend
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_spaces import resolve_space_mount


@pytest.mark.skipif(
    os.environ.get("DRIVE_SMB_QUALIFICATION") != "1", reason="Requires disposable Samba fixture."
)
@pytest.mark.django_db
def test_real_smb_virtual_roots_sessions_and_publication():
    """No credential borrowing, symlink escape, or unprotected final replacement."""
    connections = [
        {
            "mount_id": name,
            "display_name": name,
            "enabled": True,
            "provider": "smb",
            "params": {
                "server": "drive-storage-samba-qa",
                "share": "nas",
                "username": name,
                "password_secret_path": f"/run/secrets/{name}",
            },
        }
        for name in ("qa-a", "qa-b")
    ]
    first, second = connections
    assert smb.stat(mount=first, normalized_path="/alice/hello.txt").size == 5
    assert smb.stat(mount=second, normalized_path="/bob/private.txt").size == 7
    forbidden = {**second, "params": {**second["params"], "share": "only-a"}}
    with pytest.raises(MountProviderError):
        smb.stat(mount=forbidden, normalized_path="/hello.txt")
    user = factories.UserFactory()
    backend = models.StorageBackend.objects.create(
        registry_id="qa-a", name="Samba QA", organization="local"
    )
    space = models.StorageSpace.objects.create(
        backend=backend, name="Private", root_path="/alice", owner=user
    )
    with override_settings(STORAGE_GOVERNANCE_ENABLED=True, MOUNTS_REGISTRY=connections):
        initialize_items()
        mount = resolve_space_mount(space.pk, user)
        with pytest.raises(MountProviderError):
            with virtual.open_read(mount=mount, normalized_path="/escape/private.txt"):
                pytest.fail("SMB server followed a link outside the virtual root")
        scan_backend(backend.pk)
        scan_backend(backend.pk, root_path="/ALICE")
        assert not models.StorageUsage.objects.filter(path__startswith="/ALICE").exists()
        assert models.StorageUsage.objects.get(path="/alice/hello.txt").owner_id == user.pk
        # Simulate a bad administrator configuration: do not infer common ownership.
        models.StorageSpace.objects.filter(pk=space.pk).update(root_path="/ALICE")
        with pytest.raises(StorageWriteConflict, match="root spelling"):
            scan_backend(backend.pk)
        backend.refresh_from_db()
        assert backend.inventory_completed_at is None
        models.StorageSpace.objects.filter(pk=space.pk).update(root_path="/alice")
        scan_backend(backend.pk)
        virtual.write_stream(mount=mount, final_path="/hello.txt", chunks=[b"new content"])
        with virtual.open_read(mount=mount, normalized_path="/hello.txt") as stream:
            assert stream.read() == b"new content"
        assert models.StorageQuota.objects.get(key=f"user:{user.pk}").used_bytes == 11
