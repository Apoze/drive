"""Tests for mounts browse API (deterministic ordering/pagination)."""

import pytest
from rest_framework.test import APIClient
from smbprotocol.exceptions import BadNetworkName

from core import factories

pytestmark = pytest.mark.django_db


def _make_static_mount(*, mount_id: str, entries: list[dict]) -> dict:
    return {
        "mount_id": mount_id,
        "display_name": mount_id,
        "provider": "static",
        "enabled": True,
        "params": {
            "capabilities": {
                "mount.upload": True,
                "mount.preview": False,
                "mount.wopi": False,
                "mount.share_link": False,
            },
            "static_entries": entries,
        },
    }


def _make_smb_mount(*, mount_id: str) -> dict:
    return {
        "mount_id": mount_id,
        "display_name": mount_id,
        "provider": "smb",
        "enabled": True,
        "password_secret_ref": "SMB_PASSWORD",
        "params": {
            "server": "smb.internal",
            "share": "finance",
            "username": "svc",
        },
    }


def test_api_mounts_browse_root_children_ordering_is_deterministic(settings):
    """Children are sorted folder-first, then casefolded name, then path tie-breaker."""
    settings.MOUNTS_REGISTRY = [
        _make_static_mount(
            mount_id="alpha-mount",
            entries=[
                {"path": "/", "entry_type": "folder", "name": "/"},
                {"path": "/a", "entry_type": "folder", "name": "a"},
                {"path": "/A", "entry_type": "folder", "name": "A"},
                {"path": "/b.txt", "entry_type": "file", "name": "b.txt"},
                {"path": "/B.txt", "entry_type": "file", "name": "B.txt"},
            ],
        )
    ]

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    response = client.get("/api/v1.0/mounts/alpha-mount/browse/?path=/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mount_id"] == "alpha-mount"
    assert payload["normalized_path"] == "/"
    assert payload["entry"]["normalized_path"] == "/"
    assert payload["children"]["count"] == 4
    assert [e["normalized_path"] for e in payload["children"]["results"]] == [
        "/A",
        "/a",
        "/B.txt",
        "/b.txt",
    ]
    assert payload["children"]["results"][0]["abilities"]["children_list"] is True
    assert payload["children"]["results"][-1]["abilities"]["children_list"] is False


def test_api_mounts_browse_pagination_limit_offset(settings):
    """Children list supports limit/offset pagination."""
    settings.MOUNTS_REGISTRY = [
        _make_static_mount(
            mount_id="alpha-mount",
            entries=[
                {"path": "/", "entry_type": "folder"},
                {"path": "/a", "entry_type": "folder"},
                {"path": "/b", "entry_type": "folder"},
                {"path": "/c.txt", "entry_type": "file"},
                {"path": "/d.txt", "entry_type": "file"},
            ],
        )
    ]

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    response = client.get("/api/v1.0/mounts/alpha-mount/browse/?path=/&limit=2&offset=1")
    assert response.status_code == 200
    results = response.json()["children"]["results"]
    assert len(results) == 2
    assert [e["normalized_path"] for e in results] == ["/b", "/c.txt"]


def test_api_mounts_browse_rejects_parent_traversal(settings):
    """`..` is rejected deterministically (no-leak)."""
    settings.MOUNTS_REGISTRY = [
        _make_static_mount(
            mount_id="alpha-mount",
            entries=[
                {"path": "/", "entry_type": "folder"},
            ],
        )
    ]

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    response = client.get("/api/v1.0/mounts/alpha-mount/browse/?path=/../secret")
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "mount.path.invalid"


def test_api_mounts_browse_missing_path_is_404(settings):
    """Unknown paths return a deterministic 404."""
    settings.MOUNTS_REGISTRY = [
        _make_static_mount(
            mount_id="alpha-mount",
            entries=[
                {"path": "/", "entry_type": "folder"},
            ],
        )
    ]

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    response = client.get("/api/v1.0/mounts/alpha-mount/browse/?path=/missing")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "mount.path.not_found"


def test_api_mounts_browse_provider_failure_uses_generic_public_error(
    settings,
    monkeypatch,
):
    """Provider failures keep internal diagnostics but public errors stay generic."""
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="branded-failure-mount")]
    monkeypatch.setenv("SMB_PASSWORD", "pw")

    def _register_session(*args, **kwargs):
        _ = args, kwargs

    def _stat(*args, **kwargs):
        _ = args, kwargs
        raise BadNetworkName()  # pylint: disable=no-value-for-parameter

    monkeypatch.setattr(
        "core.mounts.providers.smb.smbclient.register_session",
        _register_session,
    )
    monkeypatch.setattr("core.mounts.providers.smb.smbclient.stat", _stat)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    response = client.get("/api/v1.0/mounts/branded-failure-mount/browse/?path=/")

    assert response.status_code == 400
    payload = response.json()
    assert payload["errors"][0]["code"] == "mount.provider.location_not_found"
    assert payload["errors"][0]["detail"] == "Mount location not found."
    assert "SMB" not in str(payload)
