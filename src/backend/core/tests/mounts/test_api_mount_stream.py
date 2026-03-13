"""Tests for mount browser-stream tickets and tokenized stream URLs."""
# pylint: disable=missing-function-docstring,no-member,unsubscriptable-object

from __future__ import annotations

import contextlib
import io
from urllib.parse import urlparse

import pytest
from rest_framework.test import APIClient

from core import factories
from core.mounts.providers.base import MountEntry

pytestmark = pytest.mark.django_db


def _make_smb_mount(*, mount_id: str, preview_enabled: bool = True) -> dict:
    return {
        "mount_id": mount_id,
        "display_name": mount_id,
        "provider": "smb",
        "enabled": True,
        "params": {"capabilities": {"mount.preview": preview_enabled}},
    }


def test_api_mount_stream_ticket_supports_head_and_range_get(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    content = b"0123456789"

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/bundle.zip"
        return MountEntry(
            entry_type="file",
            normalized_path=normalized_path,
            name="bundle.zip",
            size=len(content),
            modified_at=None,
        )

    @contextlib.contextmanager
    def _fake_open_read(*, mount: dict, normalized_path: str):
        _ = (mount, normalized_path)
        yield io.BytesIO(content)

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: "application/zip",
    )

    user = factories.UserFactory()
    auth_client = APIClient()
    auth_client.force_login(user)

    ticket = auth_client.post(
        "/api/v1.0/mounts/alpha-mount/stream-tickets/",
        {"path": "/bundle.zip", "disposition": "inline", "purpose": "archive"},
        format="json",
    )
    assert ticket.status_code == 201
    payload = ticket.json()
    assert "/api/v1.0/mount-stream/" in payload["stream_url"]
    assert payload["supports_range"] is True
    stream_path = urlparse(payload["stream_url"]).path

    public_client = APIClient()

    head = public_client.head(stream_path)
    assert head.status_code == 200
    assert head["Content-Length"] == str(len(content))
    assert head["Accept-Ranges"] == "bytes"
    assert head["ETag"] == payload["etag"]

    get = public_client.get(stream_path, HTTP_RANGE="bytes=0-3")
    assert get.status_code == 206
    assert get["Content-Range"] == f"bytes 0-3/{len(content)}"
    assert b"".join(get.streaming_content) == b"0123"


def test_api_mount_stream_ticket_rejects_stale_version(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    current_size = {"value": 10}

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        return MountEntry(
            entry_type="file",
            normalized_path=normalized_path,
            name="doc.pdf",
            size=current_size["value"],
            modified_at=None,
        )

    @contextlib.contextmanager
    def _fake_open_read(*, mount: dict, normalized_path: str):
        _ = (mount, normalized_path)
        yield io.BytesIO(b"x" * current_size["value"])

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: "application/pdf",
    )

    user = factories.UserFactory()
    auth_client = APIClient()
    auth_client.force_login(user)

    ticket = auth_client.post(
        "/api/v1.0/mounts/alpha-mount/stream-tickets/",
        {"path": "/doc.pdf", "disposition": "inline", "purpose": "preview"},
        format="json",
    )
    assert ticket.status_code == 201
    payload = ticket.json()
    stream_path = urlparse(payload["stream_url"]).path

    current_size["value"] = 11

    public_client = APIClient()
    response = public_client.get(stream_path)
    assert response.status_code == 409
