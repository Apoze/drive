"""Tests for mount inline preview responses (PDF/media contract)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import contextlib
import io

import pytest
from rest_framework.test import APIClient

from core import factories
from core.mounts.providers.base import MountEntry

pytestmark = pytest.mark.django_db


def _make_smb_mount(*, mount_id: str) -> dict:
    return {
        "mount_id": mount_id,
        "display_name": mount_id,
        "provider": "smb",
        "enabled": True,
        "params": {"capabilities": {"mount.preview": True}},
    }


def test_api_mount_inline_preview_streams_pdf(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    content = b"%PDF-1.7\n"

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/doc.pdf"
        return MountEntry(
            entry_type="file",
            normalized_path=normalized_path,
            name="doc.pdf",
            size=len(content),
            modified_at=None,
        )

    @contextlib.contextmanager
    def _fake_open_read(*, mount: dict, normalized_path: str):
        _ = (mount, normalized_path)
        yield io.BytesIO(content)

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr("core.mounts.providers.smb.supports_range_reads", lambda **_: True)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: "application/pdf",
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    response = client.get("/api/v1.0/mounts/alpha-mount/inline-preview/?path=/doc.pdf")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/pdf")
    assert response["Content-Disposition"].startswith("inline;")
    assert response["Cache-Control"] == "no-store"
    assert response.headers.get("ETag") is None
    assert response.headers.get("X-Frame-Options") is None
    assert response["Accept-Ranges"] == "bytes"
    assert b"".join(response.streaming_content) == content


def test_api_mount_inline_preview_supports_range(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    content = b"0123456789"

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        return MountEntry(
            entry_type="file",
            normalized_path=normalized_path,
            name="clip.mp4",
            size=len(content),
            modified_at=None,
        )

    @contextlib.contextmanager
    def _fake_open_read(*, mount: dict, normalized_path: str):
        _ = (mount, normalized_path)
        yield io.BytesIO(content)

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr("core.mounts.providers.smb.supports_range_reads", lambda **_: True)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: "video/mp4",
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    response = client.get(
        "/api/v1.0/mounts/alpha-mount/inline-preview/?path=/clip.mp4",
        HTTP_RANGE="bytes=0-3",
    )
    assert response.status_code == 206
    assert response["Content-Range"] == f"bytes 0-3/{len(content)}"
    assert response["Content-Disposition"].startswith("inline;")
    assert b"".join(response.streaming_content) == b"0123"
