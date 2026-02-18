"""Tests for mount browse abilities computation (no dead actions)."""

from __future__ import annotations

import contextlib

from django.core.cache import cache

import pytest
from rest_framework.test import APIClient

from core import factories
from core.mounts.providers.base import MountEntry
from wopi.tasks.configure_wopi import WOPI_CONFIGURATION_CACHE_KEY

pytestmark = pytest.mark.django_db


def _make_smb_mount(*, mount_id: str, capabilities: dict[str, bool]) -> dict:
    return {
        "mount_id": mount_id,
        "display_name": mount_id,
        "provider": "smb",
        "enabled": True,
        "params": {"capabilities": capabilities},
    }


def test_api_mounts_browse_folder_upload_ability(monkeypatch, settings):
    """Folder entries expose upload ability when capability enabled and provider supports IO."""

    settings.MOUNTS_REGISTRY = [
        _make_smb_mount(
            mount_id="alpha-mount",
            capabilities={
                "mount.upload": True,
                "mount.preview": False,
                "mount.wopi": False,
                "mount.share_link": False,
            },
        )
    ]

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/"
        return MountEntry(
            entry_type="folder",
            normalized_path="/",
            name="/",
            size=None,
            modified_at=None,
        )

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.list_children", lambda **_: [])

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.get("/api/v1.0/mounts/alpha-mount/browse/?path=/")
    assert resp.status_code == 200
    assert resp.json()["entry"]["abilities"]["upload"] is True


def test_api_mounts_browse_file_wopi_preview_download_abilities(monkeypatch, settings):
    """File entries expose preview/download and WOPI when eligible."""

    settings.MOUNTS_REGISTRY = [
        _make_smb_mount(
            mount_id="alpha-mount",
            capabilities={
                "mount.upload": True,
                "mount.preview": True,
                "mount.wopi": True,
                "mount.share_link": False,
            },
        )
    ]
    settings.WOPI_CLIENTS = ["collabora"]
    cache.set(
        WOPI_CONFIGURATION_CACHE_KEY,
        {"mimetypes": {}, "extensions": {"docx": "https://wopi.example/edit?"}},
        timeout=60,
    )

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/doc.docx"
        return MountEntry(
            entry_type="file",
            normalized_path="/doc.docx",
            name="doc.docx",
            size=123,
            modified_at=None,
        )

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)

    @contextlib.contextmanager
    def _fake_open_read(*, mount: dict, normalized_path: str):
        # Abilities computation only checks provider capability; keep it defined.
        _ = (mount, normalized_path)
        yield None

    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.get("/api/v1.0/mounts/alpha-mount/browse/?path=/doc.docx")
    assert resp.status_code == 200
    abilities = resp.json()["entry"]["abilities"]
    assert abilities["download"] is True
    assert abilities["preview"] is True
    assert abilities["wopi"] is True
