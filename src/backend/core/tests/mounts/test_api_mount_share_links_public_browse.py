"""Tests for public MountProvider share links (unauthenticated browse)."""

import secrets
import zipfile
from io import BytesIO

from django.test import override_settings

import pytest
from rest_framework.test import APIClient

from core import factories, models
from core.api.viewsets import MountShareLinkGone
from core.services.storage_inventory import scan_backend

pytestmark = pytest.mark.django_db


def test_public_download_streams_ranges_and_rechecks_share_access(tmp_path, settings):
    """Public reads cannot escape their root and revocation closes the native stream route."""
    settings.STORAGE_UNIFIED_ENABLED = True
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "file.txt").write_bytes(b"public synthetic bytes")
    (tmp_path / "private.txt").write_bytes(b"private synthetic bytes")
    (tmp_path / "public" / "escape").symlink_to(tmp_path / "private.txt")
    settings.MOUNTS_REGISTRY = [
        {
            "mount_id": "public-nas",
            "provider": "localfs",
            "enabled": True,
            "params": {"root_dir": str(tmp_path), "capabilities": {"mount.share_link": True}},
        }
    ]
    settings.STORAGE_GOVERNANCE_ENABLED = True
    user = factories.UserFactory()
    backend = models.StorageBackend.objects.create(
        registry_id="public-nas", name="Files", organization="local"
    )
    space = models.StorageSpace.objects.create(
        backend=backend, name="Public folder", root_path="/public", owner=user
    )
    scan_backend(backend.pk)
    resource = models.StorageResource.objects.get(namespace=backend.namespace, path="/public")
    link = models.MountShareLink.objects.create(
        token=secrets.token_urlsafe(24),
        mount_id=str(space.pk),
        normalized_path="/",
        created_by=user,
        resource=resource,
    )
    url = f"/api/v1.0/mount-share-links/{link.token}/download/"
    client = APIClient()
    response = client.get(url, {"path": "/file.txt"}, HTTP_RANGE="bytes=0-5")
    assert response.status_code == 206
    assert b"".join(response.streaming_content) == b"public"
    assert response["Content-Range"] == "bytes 0-5/22"
    assert response["Cache-Control"] == "private, no-store"
    assert response["Content-Disposition"].startswith("attachment;")
    head = client.generic("HEAD", url + "?path=/file.txt")
    assert head.headers["Content-Length"] == "22"
    assert client.get(url, {"path": "/file.txt"}, HTTP_RANGE="bytes=200-").status_code == 416
    assert client.get(url, {"path": "/../private.txt"}).status_code == 404
    assert client.get(url, {"path": "/escape"}).status_code in {400, 404}
    exported = client.get(url)
    assert exported.status_code == 200
    with zipfile.ZipFile(BytesIO(b"".join(exported.streaming_content))) as archive:
        assert archive.namelist() == ["file.txt"]
        assert archive.read("file.txt") == b"public synthetic bytes"
    interrupted = client.get(url)
    space.allow_sharing = False
    space.save(update_fields=["allow_sharing"])
    assert client.get(url, {"path": "/file.txt"}).status_code == 410
    with pytest.raises(MountShareLinkGone):
        b"".join(interrupted.streaming_content)
    assert client.get("/api/v1.0/mount-share-links/unknown/download/").status_code == 404


def _make_static_mount(*, mount_id: str) -> dict:
    return {
        "mount_id": mount_id,
        "display_name": mount_id,
        "provider": "static",
        "enabled": True,
        "params": {
            "capabilities": {"mount.share_link": True},
            "static_entries": [
                {"path": "/", "entry_type": "folder"},
                {"path": "/a", "entry_type": "folder"},
                {"path": "/a/b.txt", "entry_type": "file"},
            ],
        },
    }


def test_api_mount_share_links_browse_invalid_token_is_404(settings):
    """Unknown/invalid tokens are generic 404 (no-leak)."""
    settings.MOUNTS_REGISTRY = [_make_static_mount(mount_id="alpha-mount")]

    response = APIClient().get("/api/v1.0/mount-share-links/not-a-token/browse/")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "mount.share_link.not_found"


def test_api_mount_share_links_browse_known_token_missing_mount_is_410(settings):
    """Known token with missing/disabled mount returns 410."""
    settings.MOUNTS_REGISTRY = []

    token = secrets.token_urlsafe(16)
    models.MountShareLink.objects.create(
        token=token,
        mount_id="alpha-mount",
        normalized_path="/a",
        created_by=None,
    )

    response = APIClient().get(f"/api/v1.0/mount-share-links/{token}/browse/")
    assert response.status_code == 410
    assert response.json()["errors"][0]["code"] == "mount.share_link.gone"


def test_api_mount_share_links_browse_known_token_missing_target_is_410(settings):
    """Known token with missing target path returns 410."""
    settings.MOUNTS_REGISTRY = [_make_static_mount(mount_id="alpha-mount")]

    token = secrets.token_urlsafe(16)
    models.MountShareLink.objects.create(
        token=token,
        mount_id="alpha-mount",
        normalized_path="/missing",
        created_by=None,
    )

    response = APIClient().get(f"/api/v1.0/mount-share-links/{token}/browse/")
    assert response.status_code == 410
    assert response.json()["errors"][0]["code"] == "mount.share_link.gone"


@override_settings(DRIVE_PUBLIC_URL="https://drive.example.com")
def test_api_mount_share_links_browse_success_returns_relative_paths_only(settings):
    """Successful browse returns relative normalized paths (no mount_id/path leaks)."""
    settings.MOUNTS_REGISTRY = [_make_static_mount(mount_id="alpha-mount")]

    token = secrets.token_urlsafe(16)
    models.MountShareLink.objects.create(
        token=token,
        mount_id="alpha-mount",
        normalized_path="/a",
        created_by=None,
    )

    response = APIClient().get(f"/api/v1.0/mount-share-links/{token}/browse/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["normalized_path"] == "/"
    assert "mount_id" not in payload
    assert payload["entry"]["normalized_path"] == "/"
    assert payload["entry"]["entry_type"] == "folder"
    assert payload["children"]["count"] == 1
    assert payload["children"]["results"][0]["normalized_path"] == "/b.txt"
