"""Tests for mount-backed WOPI semantics (version, locks, streaming save)."""

from __future__ import annotations

import contextlib
import io
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, quote_plus, urlparse

from django.core.cache import cache
from django.http import HttpRequest

import pytest
from rest_framework.parsers import BaseParser
from rest_framework.test import APIClient

from core import factories
from core.mounts.providers.base import MountEntry
from wopi import viewsets as wopi_viewsets
from wopi.tasks.configure_wopi import WOPI_CONFIGURATION_CACHE_KEY
from wopi.utils import compute_mount_entry_version

pytestmark = pytest.mark.django_db


def _make_smb_mount(*, mount_id: str) -> dict:
    return {
        "mount_id": mount_id,
        "display_name": mount_id,
        "provider": "smb",
        "enabled": True,
        "params": {"capabilities": {"mount.wopi": True}},
    }


def _extract_file_id_from_launch_url(launch_url: str) -> str:
    parsed = urlparse(launch_url)
    wopisrc = parse_qs(parsed.query).get("WOPISrc", [None])[0]
    assert wopisrc, "expected WOPISrc query param in launch_url"
    wopi_path = urlparse(wopisrc).path
    match = re.search(r"/wopi/mount-files/(?P<file_id>[0-9a-f-]+)/?$", wopi_path)
    assert match, f"unexpected WOPISrc path: {wopi_path!r}"
    return match.group("file_id")


def test_api_mount_wopi_init_issues_access_token_and_launch_url(monkeypatch, settings):
    """WOPI init returns a short-lived token and a launch URL for mount files."""
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]
    settings.WOPI_CLIENTS = ["collabora"]
    settings.WOPI_SRC_BASE_URL = "http://app-dev:8000"

    cache.set(
        WOPI_CONFIGURATION_CACHE_KEY,
        {"mimetypes": {}, "extensions": {"txt": "https://wopi.example/edit?"}},
        timeout=60,
    )

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/hello.txt"
        return MountEntry(
            entry_type="file",
            normalized_path="/hello.txt",
            name="hello.txt",
            size=5,
            modified_at=None,
        )

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.get("/api/v1.0/mounts/alpha-mount/wopi/?path=/hello.txt")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["access_token"]
    assert payload["access_token_ttl"]
    wopi_src = quote_plus(
        "http://app-dev:8000/api/v1.0/wopi/mount-files/"
        + _extract_file_id_from_launch_url(payload["launch_url"])
    )
    assert payload["launch_url"] == (
        f"https://wopi.example/edit?WOPISrc={wopi_src}&closebutton=false&lang={user.language}"
    )
    assert _extract_file_id_from_launch_url(payload["launch_url"])


def test_api_mount_wopi_uses_drive_public_url_when_src_base_url_unset(monkeypatch, settings):
    """Mount WOPISrc should be built from DRIVE_PUBLIC_URL when WOPI_SRC_BASE_URL is unset."""
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]
    settings.WOPI_CLIENTS = ["collabora"]
    settings.WOPI_SRC_BASE_URL = None
    settings.DRIVE_PUBLIC_URL = "https://drive.example.com"

    cache.set(
        WOPI_CONFIGURATION_CACHE_KEY,
        {"mimetypes": {}, "extensions": {"txt": "https://wopi.example/edit?"}},
        timeout=60,
    )

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/hello.txt"
        return MountEntry(
            entry_type="file",
            normalized_path="/hello.txt",
            name="hello.txt",
            size=5,
            modified_at=None,
        )

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.get("/api/v1.0/mounts/alpha-mount/wopi/?path=/hello.txt")
    assert resp.status_code == 200
    payload = resp.json()
    file_id = _extract_file_id_from_launch_url(payload["launch_url"])
    wopi_src = quote_plus(f"https://drive.example.com/api/v1.0/wopi/mount-files/{file_id}")
    assert payload["launch_url"] == (
        f"https://wopi.example/edit?WOPISrc={wopi_src}&closebutton=false&lang={user.language}"
    )


def test_api_mount_wopi_init_keeps_editnew_items_only(monkeypatch, settings):
    """Mount WOPI init must always use the regular edit URL, never editnew."""
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]
    settings.WOPI_CLIENTS = ["collabora"]
    settings.WOPI_SRC_BASE_URL = "http://app-dev:8000"

    cache.set(
        WOPI_CONFIGURATION_CACHE_KEY,
        {
            "mimetypes": {},
            "extensions": {"docx": "https://wopi.example/edit?"},
            "mimetypes_editnew": {},
            "extensions_editnew": {"docx": "https://wopi.example/editnew?"},
        },
        timeout=60,
    )

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/hello.docx"
        return MountEntry(
            entry_type="file",
            normalized_path="/hello.docx",
            name="hello.docx",
            size=5,
            modified_at=None,
        )

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.get("/api/v1.0/mounts/alpha-mount/wopi/?path=/hello.docx")
    assert resp.status_code == 200
    assert resp.json()["launch_url"].startswith("https://wopi.example/edit?")


def _configure_mount_wopi_session(monkeypatch, settings) -> tuple[APIClient, str, str, dict]:
    """Set up an in-memory mount file and open a WOPI session against it."""
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]
    settings.WOPI_CLIENTS = ["collabora"]

    cache.set(
        WOPI_CONFIGURATION_CACHE_KEY,
        {"mimetypes": {}, "extensions": {"txt": "https://wopi.example/edit?"}},
        timeout=60,
    )

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state = {"content": b"old", "modified_at": base, "writes": []}

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/hello.txt"
        return MountEntry(
            entry_type="file",
            normalized_path="/hello.txt",
            name="hello.txt",
            size=len(state["content"]),
            modified_at=state["modified_at"],
        )

    @contextlib.contextmanager
    def _fake_open_read(*, mount: dict, normalized_path: str):
        _ = mount
        assert normalized_path == "/hello.txt"
        yield io.BytesIO(state["content"])

    @contextlib.contextmanager
    def _fake_open_write(*, mount: dict, normalized_path: str):
        _ = mount
        assert normalized_path == "/hello.txt"

        class _RecordingWriter(io.BytesIO):
            def __init__(self):
                super().__init__()
                self.write_calls = 0

            def write(self, b):  # type: ignore[override]
                self.write_calls += 1
                return super().write(b)

        writer = _RecordingWriter()
        yield writer
        state["content"] = writer.getvalue()
        state["modified_at"] = state["modified_at"] + timedelta(seconds=1)
        state["writes"].append(writer.write_calls)

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.open_read", _fake_open_read)
    monkeypatch.setattr("core.mounts.providers.smb.open_write", _fake_open_write)

    user = factories.UserFactory()
    state["user"] = user
    api = APIClient()
    api.force_login(user)

    init = api.get("/api/v1.0/mounts/alpha-mount/wopi/?path=/hello.txt")
    assert init.status_code == 200
    access_token = init.json()["access_token"]
    file_id = _extract_file_id_from_launch_url(init.json()["launch_url"])

    return api, access_token, file_id, state


def test_wopi_mount_check_file_info_keeps_mount_specific_contract(monkeypatch, settings):
    """Mount CheckFileInfo keeps the shared base and mount-only differences."""
    api, access_token, file_id, state = _configure_mount_wopi_session(monkeypatch, settings)

    response = api.get(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )

    assert response.status_code == 200
    assert response.json() == {
        "BaseFileName": "hello.txt",
        "OwnerId": "alpha-mount",
        "IsAnonymousUser": False,
        "UserFriendlyName": state["user"].full_name,
        "Size": len(state["content"]),
        "UserId": str(state["user"].id),
        "Version": compute_mount_entry_version(
            MountEntry(
                entry_type="file",
                normalized_path="/hello.txt",
                name="hello.txt",
                size=len(state["content"]),
                modified_at=state["modified_at"],
            )
        ),
        "UserCanWrite": True,
        "UserCanRename": False,
        "UserCanPresent": False,
        "UserCanAttend": False,
        "UserCanNotWriteRelative": True,
        "ReadOnly": False,
        "SupportsRename": False,
        "SupportsUpdate": True,
        "SupportsDeleteFile": False,
        "SupportsCobalt": False,
        "SupportsContainers": False,
        "SupportsEcosystem": False,
        "SupportsGetFileWopiSrc": False,
        "SupportsGetLock": True,
        "SupportsLocks": True,
        "SupportsUserInfo": False,
    }


def test_wopi_mount_get_file_keeps_headers_and_streaming_contract(monkeypatch, settings):
    """Mount GetFile keeps WOPI headers and streams the provider bytes."""
    api, access_token, file_id, state = _configure_mount_wopi_session(monkeypatch, settings)

    response = api.get(
        f"/api/v1.0/wopi/mount-files/{file_id}/contents/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )

    assert response.status_code == 200
    assert response.headers["X-WOPI-ItemVersion"] == compute_mount_entry_version(
        MountEntry(
            entry_type="file",
            normalized_path="/hello.txt",
            name="hello.txt",
            size=len(state["content"]),
            modified_at=state["modified_at"],
        )
    )
    assert response.headers["Content-Length"] == str(len(state["content"]))
    assert response["Content-Type"] == "application/octet-stream"
    assert b"".join(response.streaming_content) == state["content"]


def test_wopi_mount_get_file_honors_max_expected_size(monkeypatch, settings):
    """Mount GetFile returns 412 when X-WOPI-MaxExpectedSize is exceeded."""
    api, access_token, file_id, _state = _configure_mount_wopi_session(monkeypatch, settings)

    response = api.get(
        f"/api/v1.0/wopi/mount-files/{file_id}/contents/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_MAXEXPECTEDSIZE="2",
    )

    assert response.status_code == 412


def test_wopi_mount_put_file_streams_and_updates_version(monkeypatch, settings):
    """PutFile streams bytes and updates the mount-backed WOPI version string."""
    api, access_token, file_id, state = _configure_mount_wopi_session(monkeypatch, settings)

    info1 = api.get(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )
    assert info1.status_code == 200
    version1 = info1.json()["Version"]

    lock = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="LOCK",
        HTTP_X_WOPI_LOCK="lock-1",
    )
    assert lock.status_code == 200

    body = b"a" * (64 * 1024 + 123)
    put = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/contents/",
        data=body,
        content_type="application/octet-stream",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="PUT",
        HTTP_X_WOPI_LOCK="lock-1",
    )
    assert put.status_code == 200
    assert state["content"] == body
    assert state["writes"][-1] >= 2
    assert "X-WOPI-ItemVersion" in put.headers

    info2 = api.get(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )
    assert info2.status_code == 200
    assert info2.json()["Version"] != version1


def test_wopi_mount_put_file_conflict_and_unlock(monkeypatch, settings):
    """Lock conflicts return 409 and UNLOCK releases deterministically."""
    api, access_token, file_id, _state = _configure_mount_wopi_session(monkeypatch, settings)

    lock = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="LOCK",
        HTTP_X_WOPI_LOCK="lock-1",
    )
    assert lock.status_code == 200

    conflict = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/contents/",
        data=b"new",
        content_type="application/octet-stream",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="PUT",
        HTTP_X_WOPI_LOCK="wrong-lock",
    )
    assert conflict.status_code == 409
    assert conflict.headers.get("X-WOPI-Lock") == "lock-1"

    unlock = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="UNLOCK",
        HTTP_X_WOPI_LOCK="lock-1",
    )
    assert unlock.status_code == 200


def test_wopi_mount_get_lock_and_refresh_lock(monkeypatch, settings):
    """Mount GET_LOCK and REFRESH_LOCK should follow the shared lock lifecycle."""
    api, access_token, file_id, _state = _configure_mount_wopi_session(monkeypatch, settings)

    get_lock_empty = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="GET_LOCK",
    )
    assert get_lock_empty.status_code == 200
    assert get_lock_empty.headers.get("X-WOPI-Lock") == ""

    lock = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="LOCK",
        HTTP_X_WOPI_LOCK="lock-1",
    )
    assert lock.status_code == 200

    refresh_conflict = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="REFRESH_LOCK",
        HTTP_X_WOPI_LOCK="wrong-lock",
    )
    assert refresh_conflict.status_code == 409
    assert refresh_conflict.headers.get("X-WOPI-Lock") == "lock-1"

    refresh_ok = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="REFRESH_LOCK",
        HTTP_X_WOPI_LOCK="lock-1",
    )
    assert refresh_ok.status_code == 200

    get_lock = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="GET_LOCK",
    )
    assert get_lock.status_code == 200
    assert get_lock.headers.get("X-WOPI-Lock") == "lock-1"


def test_wopi_mount_detail_post_keeps_rename_items_only(monkeypatch, settings):
    """Mount detail POST must keep RENAME_FILE unsupported."""
    api, access_token, file_id, _state = _configure_mount_wopi_session(monkeypatch, settings)

    response = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="RENAME_FILE",
        HTTP_X_WOPI_REQUESTEDNAME="renamed",
    )
    assert response.status_code == 404


def test_wopi_mount_put_file_does_not_access_request_body(monkeypatch, settings):
    """Mount PutFile must stream from the request without touching Request.body."""

    def _raise_on_body(_self):
        raise AssertionError("request.body must not be accessed")

    monkeypatch.setattr(HttpRequest, "body", property(_raise_on_body))

    api, access_token, file_id, state = _configure_mount_wopi_session(monkeypatch, settings)

    lock = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="LOCK",
        HTTP_X_WOPI_LOCK="lock-1",
    )
    assert lock.status_code == 200

    put = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/contents/",
        data=b"new content",
        content_type="application/octet-stream",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="PUT",
        HTTP_X_WOPI_LOCK="lock-1",
    )
    assert put.status_code == 200
    assert state["content"] == b"new content"


def test_wopi_mount_put_file_does_not_trigger_drf_parsing(monkeypatch, settings):
    """Mount PutFile must not invoke DRF parsers."""

    class ExplodingParser(BaseParser):
        """Guard parser used to prove mount PutFile never triggers DRF parsing."""

        media_type = "*/*"

        def parse(self, *args, **kwargs):
            raise AssertionError("DRF parser must not be invoked for mount PutFile")

    monkeypatch.setattr(
        wopi_viewsets.MountWopiViewSet,
        "parser_classes",
        [ExplodingParser],
        raising=True,
    )

    api, access_token, file_id, _state = _configure_mount_wopi_session(monkeypatch, settings)

    lock = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="LOCK",
        HTTP_X_WOPI_LOCK="lock-1",
    )
    assert lock.status_code == 200

    put = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/contents/",
        data=b"new content",
        content_type="application/octet-stream",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_WOPI_OVERRIDE="PUT",
        HTTP_X_WOPI_LOCK="lock-1",
    )
    assert put.status_code == 200


def test_wopi_mount_put_file_without_override_header_returns_404(monkeypatch, settings):
    """Mount PutFile without X-WOPI-Override must keep returning 404."""
    api, access_token, file_id, _state = _configure_mount_wopi_session(monkeypatch, settings)

    response = api.post(
        f"/api/v1.0/wopi/mount-files/{file_id}/contents/",
        data=b"new content",
        content_type="application/octet-stream",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )

    assert response.status_code == 404
