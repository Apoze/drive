"""Tests for mount duplicate streaming semantics."""

from __future__ import annotations

import contextlib
import io

import pytest
from rest_framework.test import APIClient

from core import factories
from core.mounts.providers.base import MountEntry, MountProviderError

pytestmark = pytest.mark.django_db


def _make_smb_mount(*, mount_id: str, duplicate_enabled: bool = True) -> dict:
    return {
        "mount_id": mount_id,
        "display_name": mount_id,
        "provider": "smb",
        "enabled": True,
        "params": {
            "capabilities": {
                "mount.upload": True,
                "mount.duplicate": duplicate_enabled,
                "mount.preview": False,
                "mount.wopi": False,
                "mount.share_link": False,
            }
        },
    }


def test_api_mount_duplicate_streams_to_temp_and_renames_unique_target(  # noqa: PLR0915
    monkeypatch, settings
):
    """Duplicate streams via temp path and picks the next available suffixed name."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    files: dict[str, bytes] = {
        "/hello.txt": b"hello",
        "/hello_01.txt": b"existing",
    }
    rename_calls: list[tuple[str, str]] = []
    temp_buffers: dict[str, io.BytesIO] = {}

    def _entry_for(path: str) -> MountEntry:
        if path == "/":
            return MountEntry(
                entry_type="folder",
                normalized_path="/",
                name="/",
                size=None,
                modified_at=None,
            )
        if path in files:
            name = path.rsplit("/", maxsplit=1)[-1]
            return MountEntry(
                entry_type="file",
                normalized_path=path,
                name=name,
                size=len(files[path]),
                modified_at=None,
            )
        raise MountProviderError(
            failure_class="mount.path.not_found",
            next_action_hint="Verify the path exists in the mount and retry.",
            public_message="Mount path not found.",
            public_code="mount.path.not_found",
        )

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        return _entry_for(normalized_path)

    def _fake_list_children(*, mount: dict, normalized_path: str) -> list[MountEntry]:
        _ = mount
        assert normalized_path == "/"
        return [_entry_for("/hello.txt"), _entry_for("/hello_01.txt")]

    @contextlib.contextmanager
    def _fake_open_read(*, mount: dict, normalized_path: str):
        _ = mount
        yield io.BytesIO(files[normalized_path])

    @contextlib.contextmanager
    def _fake_open_write(*, mount: dict, normalized_path: str):
        _ = mount
        buffer = io.BytesIO()
        temp_buffers[normalized_path] = buffer
        yield buffer
        files[normalized_path] = buffer.getvalue()

    def _fake_rename(*, mount: dict, src_normalized_path: str, dst_normalized_path: str):
        _ = mount
        rename_calls.append((src_normalized_path, dst_normalized_path))
        files[dst_normalized_path] = files.pop(src_normalized_path)

    def _fake_remove(*, mount: dict, normalized_path: str):
        _ = mount
        if normalized_path not in files:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists in the mount and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        files.pop(normalized_path)

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.list_children", _fake_list_children)
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr("core.mounts.providers.smb.open_write", _fake_open_write)
    monkeypatch.setattr("core.mounts.providers.smb.rename", _fake_rename)
    monkeypatch.setattr("core.mounts.providers.smb.remove", _fake_remove)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post("/api/v1.0/mounts/alpha-mount/duplicate/?path=/hello.txt")

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["normalized_path"] == "/hello_02.txt"
    assert payload["name"] == "hello_02.txt"
    assert payload["abilities"]["duplicate"] is True
    assert files["/hello_02.txt"] == b"hello"
    assert temp_buffers
    assert rename_calls == [(next(iter(temp_buffers.keys())), "/hello_02.txt")]
