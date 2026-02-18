"""Tests for mount archive extraction gate + job (MountProvider destinations)."""

from __future__ import annotations

import contextlib
import io
import zipfile
from io import BytesIO

import pytest
from lasuite.drf.models.choices import RoleChoices
from rest_framework.test import APIClient

from core import factories, models
from core.mounts.providers.base import MountEntry, MountProviderError
from core.services.mount_security import MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT_PUBLIC_MESSAGE

pytestmark = pytest.mark.django_db


def _make_zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _make_smb_mount(*, mount_id: str) -> dict:
    return {
        "mount_id": mount_id,
        "display_name": mount_id,
        "provider": "smb",
        "enabled": True,
        "params": {
            "capabilities": {
                "mount.upload": True,
                "mount.preview": True,
                "mount.wopi": True,
                "mount.share_link": False,
            }
        },
    }


def test_api_mount_archive_extractions_refused_without_hardening_gate(settings):
    """Gate off => explicit refusal with required message."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="test.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=_make_zip_bytes({"root.txt": b"root"}),
        upload_bytes__filename="test.zip",
    )

    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/archive-extractions/?path=/",
        {"item_id": str(archive.id), "mode": "all"},
        format="json",
    )
    assert resp.status_code == 403
    assert (
        resp.json()["errors"][0]["detail"]
        == MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT_PUBLIC_MESSAGE
    )
    assert resp.json()["errors"][0]["code"] == "mount.archive_extract.unsafe"


def test_api_mount_archive_extractions_extracts_zip_when_gate_enabled(  # noqa: PLR0915
    monkeypatch, settings
):
    """Gate on => job runs and writes extracted files to the provider."""

    monkeypatch.setenv("MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT", "true")
    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="test.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=_make_zip_bytes(
            {"folder/hello.txt": b"hello", "root.txt": b"root"}
        ),
        upload_bytes__filename="test.zip",
    )

    dirs: set[str] = {"/"}
    files: dict[str, bytes] = {}

    def _not_found() -> MountProviderError:
        return MountProviderError(
            failure_class="mount.path.not_found",
            next_action_hint="",
            public_message="Mount path not found.",
            public_code="mount.path.not_found",
        )

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        if normalized_path in dirs:
            return MountEntry(
                entry_type="folder",
                normalized_path=normalized_path,
                name=normalized_path.rsplit("/", 1)[-1] or "/",
                size=None,
                modified_at=None,
            )
        if normalized_path in files:
            return MountEntry(
                entry_type="file",
                normalized_path=normalized_path,
                name=normalized_path.rsplit("/", 1)[-1],
                size=len(files[normalized_path]),
                modified_at=None,
            )
        raise _not_found()

    def _fake_mkdirs(*, mount: dict, normalized_path: str) -> None:
        _ = mount
        parts = normalized_path.split("/")
        cur = ""
        for p in parts:
            if p == "":
                cur = "/"
                dirs.add(cur)
                continue
            if cur == "/":
                cur = f"/{p}"
            else:
                cur = f"{cur}/{p}"
            dirs.add(cur)

    @contextlib.contextmanager
    def _fake_open_write(*, mount: dict, normalized_path: str):
        _ = mount
        buf = io.BytesIO()
        try:
            yield buf
        finally:
            files[normalized_path] = buf.getvalue()

    def _fake_rename(
        *, mount: dict, src_normalized_path: str, dst_normalized_path: str
    ):
        _ = mount
        files[dst_normalized_path] = files.pop(src_normalized_path)

    def _fake_remove(*, mount: dict, normalized_path: str) -> None:
        _ = mount
        files.pop(normalized_path, None)

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.mkdirs", _fake_mkdirs)
    monkeypatch.setattr("core.mounts.providers.smb.open_write", _fake_open_write)
    monkeypatch.setattr("core.mounts.providers.smb.rename", _fake_rename)
    monkeypatch.setattr("core.mounts.providers.smb.remove", _fake_remove)

    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/archive-extractions/?path=/",
        {"item_id": str(archive.id), "mode": "all"},
        format="json",
    )
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]

    status_resp = client.get(f"/api/v1.0/mount-archive-extractions/{job_id}/")
    assert status_resp.status_code == 200
    payload = status_resp.json()
    assert payload["state"] == "done"
    assert payload["progress"]["total"] == 2

    assert files["/folder/hello.txt"] == b"hello"
    assert files["/root.txt"] == b"root"
