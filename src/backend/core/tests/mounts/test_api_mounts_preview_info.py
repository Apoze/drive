"""Tests for mount preview-info contract."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import contextlib
import io

from django.core.cache import cache

import pytest
from rest_framework.test import APIClient

from core import factories
from core.mounts.providers.base import MountEntry
from wopi.tasks.configure_wopi import WOPI_CONFIGURATION_CACHE_KEY

pytestmark = pytest.mark.django_db


def _make_smb_mount(
    *,
    mount_id: str,
    preview_enabled: bool = True,
    wopi_enabled: bool = False,
) -> dict:
    return {
        "mount_id": mount_id,
        "display_name": mount_id,
        "provider": "smb",
        "enabled": True,
        "params": {
            "capabilities": {
                "mount.preview": preview_enabled,
                "mount.wopi": wopi_enabled,
            }
        },
    }


def _fake_file_entry(*, normalized_path: str, name: str, size: int = 4) -> MountEntry:
    return MountEntry(
        entry_type="file",
        normalized_path=normalized_path,
        name=name,
        size=size,
        modified_at=None,
    )


@contextlib.contextmanager
def _fake_open_read(*, mount: dict, normalized_path: str):
    _ = (mount, normalized_path)
    yield io.BytesIO(b"data")


def test_api_mount_preview_info_resolves_image(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [
        _make_smb_mount(mount_id="alpha-mount", preview_enabled=True)
    ]

    monkeypatch.setattr(
        "core.mounts.providers.smb.stat",
        lambda *, mount, normalized_path: _fake_file_entry(
            normalized_path=normalized_path,
            name="picture.png",
        ),
    )
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: "image/png",
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.get("/api/v1.0/mounts/alpha-mount/preview-info/?path=/picture.png")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["preview_kind"] == "image"
    assert payload["mimetype"] == "image/png"
    assert payload["is_wopi_supported"] is False
    assert payload["can_download"] is True
    assert "/api/v1.0/mount-stream/" in payload["stream_url"]
    assert isinstance(payload["stream_expires_at"], int)
    assert payload["inline_url"].endswith(
        "/api/v1.0/mounts/alpha-mount/inline-preview/?path=/picture.png"
    )
    assert payload["download_url"].endswith(
        "/api/v1.0/mounts/alpha-mount/download/?path=/picture.png"
    )


def test_api_mount_preview_info_resolves_wopi(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [
        _make_smb_mount(
            mount_id="alpha-mount",
            preview_enabled=True,
            wopi_enabled=True,
        )
    ]
    settings.WOPI_CLIENTS = ["collabora"]
    cache.set(
        WOPI_CONFIGURATION_CACHE_KEY,
        {
            "mimetypes": {},
            "extensions": {"docx": "https://wopi.example/edit?"},
        },
        timeout=60,
    )

    monkeypatch.setattr(
        "core.mounts.providers.smb.stat",
        lambda *, mount, normalized_path: _fake_file_entry(
            normalized_path=normalized_path,
            name="document.docx",
        ),
    )
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.get("/api/v1.0/mounts/alpha-mount/preview-info/?path=/document.docx")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["preview_kind"] == "wopi"
    assert payload["is_wopi_supported"] is True
    assert payload["inline_url"] is None
    assert payload["download_url"].endswith(
        "/api/v1.0/mounts/alpha-mount/download/?path=/document.docx"
    )


def test_api_mount_preview_info_resolves_text(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [
        _make_smb_mount(
            mount_id="alpha-mount",
            preview_enabled=True,
            wopi_enabled=True,
        )
    ]
    settings.WOPI_CLIENTS = ["collabora"]
    cache.set(
        WOPI_CONFIGURATION_CACHE_KEY,
        {
            "mimetypes": {},
            "extensions": {"md": "https://wopi.example/edit?"},
        },
        timeout=60,
    )

    monkeypatch.setattr(
        "core.mounts.providers.smb.stat",
        lambda *, mount, normalized_path: _fake_file_entry(
            normalized_path=normalized_path,
            name="notes.md",
        ),
    )
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: "text/markdown",
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.get("/api/v1.0/mounts/alpha-mount/preview-info/?path=/notes.md")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["preview_kind"] == "text"
    assert payload["mimetype"] == "text/markdown"
    assert payload["inline_url"] is None
    assert payload["can_edit_text"] is True
    assert payload["download_url"].endswith(
        "/api/v1.0/mounts/alpha-mount/download/?path=/notes.md"
    )


def test_api_mount_preview_info_prefers_wopi_for_txt(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [
        _make_smb_mount(
            mount_id="alpha-mount",
            preview_enabled=True,
            wopi_enabled=True,
        )
    ]
    settings.WOPI_CLIENTS = ["collabora"]
    cache.set(
        WOPI_CONFIGURATION_CACHE_KEY,
        {
            "mimetypes": {},
            "extensions": {"txt": "https://wopi.example/edit?"},
        },
        timeout=60,
    )

    monkeypatch.setattr(
        "core.mounts.providers.smb.stat",
        lambda *, mount, normalized_path: _fake_file_entry(
            normalized_path=normalized_path,
            name="notes.txt",
        ),
    )
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: "text/plain",
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.get("/api/v1.0/mounts/alpha-mount/preview-info/?path=/notes.txt")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["preview_kind"] == "wopi"
    assert payload["is_wopi_supported"] is True
    assert payload["can_edit_text"] is False


def test_api_mount_preview_info_resolves_archive(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [
        _make_smb_mount(mount_id="alpha-mount", preview_enabled=True)
    ]

    monkeypatch.setattr(
        "core.mounts.providers.smb.stat",
        lambda *, mount, normalized_path: _fake_file_entry(
            normalized_path=normalized_path,
            name="bundle.zip",
        ),
    )
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: "application/zip",
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.get("/api/v1.0/mounts/alpha-mount/preview-info/?path=/bundle.zip")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["preview_kind"] == "archive"
    assert "/api/v1.0/mount-stream/" in payload["stream_url"]
    assert payload["download_url"].endswith(
        "/api/v1.0/mounts/alpha-mount/download/?path=/bundle.zip"
    )
