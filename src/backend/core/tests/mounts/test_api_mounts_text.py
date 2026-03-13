"""Tests for mount text preview/editor behavior."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import contextlib
import io
from datetime import datetime, timedelta, timezone

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


def test_api_mount_text_get_ok(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    state = {
        "content": b"# hello\n",
        "modified_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/notes.md"
        return MountEntry(
            entry_type="file",
            normalized_path=normalized_path,
            name="notes.md",
            size=len(state["content"]),
            modified_at=state["modified_at"],
        )

    @contextlib.contextmanager
    def _fake_open_read(*, mount: dict, normalized_path: str):
        _ = mount
        assert normalized_path == "/notes.md"
        yield io.BytesIO(state["content"])

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: "text/markdown",
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    response = client.get("/api/v1.0/mounts/alpha-mount/text/?path=/notes.md")
    assert response.status_code == 200
    assert response.headers.get("ETag")
    payload = response.json()
    assert payload["content"] == "# hello\n"
    assert payload["truncated"] is False
    assert payload["size"] == len(state["content"])
    assert payload["etag"] == response.headers["ETag"]
    assert payload["read_only"] is True


def test_api_mount_text_put_ok_and_updates_etag(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    state = {
        "content": b"hello",
        "modified_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/notes.txt"
        return MountEntry(
            entry_type="file",
            normalized_path=normalized_path,
            name="notes.txt",
            size=len(state["content"]),
            modified_at=state["modified_at"],
        )

    @contextlib.contextmanager
    def _fake_open_read(*, mount: dict, normalized_path: str):
        _ = mount
        assert normalized_path == "/notes.txt"
        yield io.BytesIO(state["content"])

    @contextlib.contextmanager
    def _fake_open_write(*, mount: dict, normalized_path: str):
        _ = mount
        assert normalized_path == "/notes.txt"

        class _RecordingWriter(io.BytesIO):
            def close(self):  # type: ignore[override]
                state["content"] = self.getvalue()
                state["modified_at"] = state["modified_at"] + timedelta(seconds=1)
                super().close()

        yield _RecordingWriter()

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr("core.mounts.providers.smb.open_write", _fake_open_write)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: "text/plain",
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    get_resp = client.get("/api/v1.0/mounts/alpha-mount/text/?path=/notes.txt")
    etag = get_resp.headers.get("ETag")
    assert etag
    assert get_resp.json()["read_only"] is False

    put_resp = client.put(
        "/api/v1.0/mounts/alpha-mount/text/?path=/notes.txt",
        data={"content": "updated"},
        format="json",
        HTTP_IF_MATCH=etag,
    )
    assert put_resp.status_code == 200
    assert put_resp.headers.get("ETag")

    get_resp2 = client.get("/api/v1.0/mounts/alpha-mount/text/?path=/notes.txt")
    assert get_resp2.json()["content"] == "updated"


def test_api_mount_text_put_etag_mismatch_returns_412(monkeypatch, settings):
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    state = {
        "content": b"hello",
        "modified_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/notes.txt"
        return MountEntry(
            entry_type="file",
            normalized_path=normalized_path,
            name="notes.txt",
            size=len(state["content"]),
            modified_at=state["modified_at"],
        )

    @contextlib.contextmanager
    def _fake_open_read(*, mount: dict, normalized_path: str):
        _ = mount
        assert normalized_path == "/notes.txt"
        yield io.BytesIO(state["content"])

    @contextlib.contextmanager
    def _fake_open_write(*, mount: dict, normalized_path: str):
        _ = (mount, normalized_path)
        yield io.BytesIO()

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr("core.mounts.providers.smb.open_write", _fake_open_write)
    monkeypatch.setattr(
        "core.api.utils.detect_mimetype",
        lambda *_a, **_k: "text/plain",
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    get_resp = client.get("/api/v1.0/mounts/alpha-mount/text/?path=/notes.txt")
    etag = get_resp.headers.get("ETag")
    assert etag

    state["content"] = b"external"
    state["modified_at"] = state["modified_at"] + timedelta(seconds=1)

    put_resp = client.put(
        "/api/v1.0/mounts/alpha-mount/text/?path=/notes.txt",
        data={"content": "updated"},
        format="json",
        HTTP_IF_MATCH=etag,
    )
    assert put_resp.status_code == 412
    assert put_resp.json()["errors"][0]["code"] in {
        "mount.text.changed",
        "precondition_failed",
    }
