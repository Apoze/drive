"""Tests for mount move/rename/delete CRUD endpoints."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from core import factories
from core.mounts.providers.base import MountEntry, MountProviderError

pytestmark = pytest.mark.django_db


def _make_smb_mount(*, mount_id: str) -> dict:
    return {
        "mount_id": mount_id,
        "display_name": mount_id,
        "provider": "smb",
        "enabled": True,
        "params": {
            "capabilities": {
                "mount.create_folder": True,
                "mount.move": True,
                "mount.rename": True,
                "mount.delete": True,
                "mount.upload": True,
                "mount.duplicate": True,
                "mount.preview": False,
                "mount.wopi": False,
                "mount.share_link": False,
            }
        },
    }


def test_api_mount_rename_renames_entry_and_returns_updated_payload(monkeypatch, settings):
    """Rename should use provider.rename and return the updated mount entry payload."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    files: dict[str, MountEntry] = {
        "/report.txt": MountEntry(
            entry_type="file",
            normalized_path="/report.txt",
            name="report.txt",
            size=12,
            modified_at=None,
        ),
    }
    rename_calls: list[tuple[str, str]] = []

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = files.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    def _fake_rename(*, mount: dict, src_normalized_path: str, dst_normalized_path: str) -> None:
        _ = mount
        rename_calls.append((src_normalized_path, dst_normalized_path))
        source = files.pop(src_normalized_path)
        files[dst_normalized_path] = MountEntry(
            entry_type=source.entry_type,
            normalized_path=dst_normalized_path,
            name=dst_normalized_path.rsplit("/", maxsplit=1)[-1],
            size=source.size,
            modified_at=source.modified_at,
        )

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.rename", _fake_rename)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/rename/?path=/report.txt",
        {"name": "final-report.txt"},
        format="json",
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["normalized_path"] == "/final-report.txt"
    assert payload["name"] == "final-report.txt"
    assert payload["abilities"]["rename"] is True
    assert payload["abilities"]["destroy"] is True
    assert rename_calls == [("/report.txt", "/final-report.txt")]


def test_api_mount_create_folder_creates_child_folder(monkeypatch, settings):
    """Folder creation should call provider.mkdirs and return the created folder entry."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    entries: dict[str, MountEntry] = {
        "/": MountEntry(
            entry_type="folder",
            normalized_path="/",
            name="/",
            size=None,
            modified_at=None,
        ),
    }
    mkdir_calls: list[str] = []

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = entries.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    def _fake_mkdirs(*, mount: dict, normalized_path: str) -> None:
        _ = mount
        mkdir_calls.append(normalized_path)
        entries[normalized_path] = MountEntry(
            entry_type="folder",
            normalized_path=normalized_path,
            name=normalized_path.rsplit("/", maxsplit=1)[-1],
            size=None,
            modified_at=None,
        )

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.mkdirs", _fake_mkdirs)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/folders/?path=/",
        {"name": "projects"},
        format="json",
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["normalized_path"] == "/projects"
    assert payload["entry_type"] == "folder"
    assert payload["abilities"]["create_folder"] is True
    assert mkdir_calls == ["/projects"]


def test_api_mount_create_folder_rejects_existing_target(monkeypatch, settings):
    """Folder creation must fail deterministically when the child already exists."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    entries: dict[str, MountEntry] = {
        "/": MountEntry(
            entry_type="folder",
            normalized_path="/",
            name="/",
            size=None,
            modified_at=None,
        ),
        "/projects": MountEntry(
            entry_type="folder",
            normalized_path="/projects",
            name="projects",
            size=None,
            modified_at=None,
        ),
    }

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = entries.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.mkdirs", lambda **_: None)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/folders/?path=/",
        {"name": "projects"},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "mount.create_folder.target_exists"


def test_api_mount_create_folder_reuses_existing_folder_when_opted_in(monkeypatch, settings):
    """Folder creation may reuse an existing folder only when the request opts in."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    entries: dict[str, MountEntry] = {
        "/": MountEntry(
            entry_type="folder",
            normalized_path="/",
            name="/",
            size=None,
            modified_at=None,
        ),
        "/projects": MountEntry(
            entry_type="folder",
            normalized_path="/projects",
            name="projects",
            size=None,
            modified_at=None,
        ),
    }
    mkdir_calls: list[str] = []

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = entries.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    def _fake_mkdirs(*, mount: dict, normalized_path: str) -> None:
        _ = mount
        mkdir_calls.append(normalized_path)

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.mkdirs", _fake_mkdirs)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/folders/?path=/",
        {"name": "projects", "reuse_existing": True},
        format="json",
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["normalized_path"] == "/projects"
    assert payload["entry_type"] == "folder"
    assert not mkdir_calls


def test_api_mount_create_folder_reuse_existing_still_rejects_existing_file(monkeypatch, settings):
    """Reuse-existing must not turn a conflicting file into a folder merge."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    entries: dict[str, MountEntry] = {
        "/": MountEntry(
            entry_type="folder",
            normalized_path="/",
            name="/",
            size=None,
            modified_at=None,
        ),
        "/projects": MountEntry(
            entry_type="file",
            normalized_path="/projects",
            name="projects",
            size=42,
            modified_at=None,
        ),
    }

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = entries.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.mkdirs", lambda **_: None)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/folders/?path=/",
        {"name": "projects", "reuse_existing": True},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "mount.create_folder.target_exists"


def test_api_mount_move_moves_file_to_existing_folder(monkeypatch, settings):
    """Move should use provider.rename for intra-mount file moves."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    entries: dict[str, MountEntry] = {
        "/report.txt": MountEntry(
            entry_type="file",
            normalized_path="/report.txt",
            name="report.txt",
            size=12,
            modified_at=None,
        ),
        "/archive": MountEntry(
            entry_type="folder",
            normalized_path="/archive",
            name="archive",
            size=None,
            modified_at=None,
        ),
    }
    rename_calls: list[tuple[str, str]] = []

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = entries.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    def _fake_rename(*, mount: dict, src_normalized_path: str, dst_normalized_path: str) -> None:
        _ = mount
        rename_calls.append((src_normalized_path, dst_normalized_path))
        source = entries.pop(src_normalized_path)
        entries[dst_normalized_path] = MountEntry(
            entry_type=source.entry_type,
            normalized_path=dst_normalized_path,
            name=dst_normalized_path.rsplit("/", maxsplit=1)[-1],
            size=source.size,
            modified_at=source.modified_at,
        )

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.rename", _fake_rename)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/move/?path=/report.txt",
        {"target_path": "/archive"},
        format="json",
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["normalized_path"] == "/archive/report.txt"
    assert payload["abilities"]["move"] is True
    assert payload["abilities"]["destroy"] is True
    assert rename_calls == [("/report.txt", "/archive/report.txt")]


def test_api_mount_move_moves_folder_to_existing_folder(monkeypatch, settings):
    """Move should also support non-root folders when provider.rename does."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    entries: dict[str, MountEntry] = {
        "/projects": MountEntry(
            entry_type="folder",
            normalized_path="/projects",
            name="projects",
            size=None,
            modified_at=None,
        ),
        "/archive": MountEntry(
            entry_type="folder",
            normalized_path="/archive",
            name="archive",
            size=None,
            modified_at=None,
        ),
    }
    rename_calls: list[tuple[str, str]] = []

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = entries.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    def _fake_rename(*, mount: dict, src_normalized_path: str, dst_normalized_path: str) -> None:
        _ = mount
        rename_calls.append((src_normalized_path, dst_normalized_path))
        source = entries.pop(src_normalized_path)
        entries[dst_normalized_path] = MountEntry(
            entry_type=source.entry_type,
            normalized_path=dst_normalized_path,
            name=dst_normalized_path.rsplit("/", maxsplit=1)[-1],
            size=source.size,
            modified_at=source.modified_at,
        )

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.rename", _fake_rename)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/move/?path=/projects",
        {"target_path": "/archive"},
        format="json",
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["normalized_path"] == "/archive/projects"
    assert payload["entry_type"] == "folder"
    assert payload["abilities"]["move"] is True
    assert rename_calls == [("/projects", "/archive/projects")]


def test_api_mount_move_to_current_parent_is_noop(monkeypatch, settings):
    """Moving into the current parent is a deterministic no-op."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    entries: dict[str, MountEntry] = {
        "/archive": MountEntry(
            entry_type="folder",
            normalized_path="/archive",
            name="archive",
            size=None,
            modified_at=None,
        ),
        "/archive/report.txt": MountEntry(
            entry_type="file",
            normalized_path="/archive/report.txt",
            name="report.txt",
            size=12,
            modified_at=None,
        ),
    }
    rename_calls: list[tuple[str, str]] = []

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = entries.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr(
        "core.mounts.providers.smb.rename",
        lambda **kwargs: rename_calls.append(
            (kwargs["src_normalized_path"], kwargs["dst_normalized_path"])
        ),
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/move/?path=/archive/report.txt",
        {"target_path": "/archive"},
        format="json",
    )

    assert resp.status_code == 200
    assert resp.json()["normalized_path"] == "/archive/report.txt"
    assert not rename_calls


def test_api_mount_move_rejects_invalid_folder_destination(monkeypatch, settings):
    """Folders cannot be moved into themselves or one of their descendants."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    entries: dict[str, MountEntry] = {
        "/projects": MountEntry(
            entry_type="folder",
            normalized_path="/projects",
            name="projects",
            size=None,
            modified_at=None,
        ),
        "/projects/nested": MountEntry(
            entry_type="folder",
            normalized_path="/projects/nested",
            name="nested",
            size=None,
            modified_at=None,
        ),
    }

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = entries.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.rename", lambda **_: None)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/move/?path=/projects",
        {"target_path": "/projects/nested"},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "mount.move.invalid_destination"


def test_api_mount_move_rejects_existing_target(monkeypatch, settings):
    """Move must fail deterministically when the target path already exists."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    entries: dict[str, MountEntry] = {
        "/report.txt": MountEntry(
            entry_type="file",
            normalized_path="/report.txt",
            name="report.txt",
            size=12,
            modified_at=None,
        ),
        "/archive": MountEntry(
            entry_type="folder",
            normalized_path="/archive",
            name="archive",
            size=None,
            modified_at=None,
        ),
        "/archive/report.txt": MountEntry(
            entry_type="file",
            normalized_path="/archive/report.txt",
            name="report.txt",
            size=12,
            modified_at=None,
        ),
    }

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = entries.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.rename", lambda **_: None)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/move/?path=/report.txt",
        {"target_path": "/archive"},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "mount.move.target_exists"


def test_api_mount_rename_rejects_existing_target(monkeypatch, settings):
    """Rename must fail deterministically when the destination already exists."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    files: dict[str, MountEntry] = {
        "/report.txt": MountEntry(
            entry_type="file",
            normalized_path="/report.txt",
            name="report.txt",
            size=12,
            modified_at=None,
        ),
        "/final-report.txt": MountEntry(
            entry_type="file",
            normalized_path="/final-report.txt",
            name="final-report.txt",
            size=12,
            modified_at=None,
        ),
    }

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = files.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.rename", lambda **_: None)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.post(
        "/api/v1.0/mounts/alpha-mount/rename/?path=/report.txt",
        {"name": "final-report.txt"},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "mount.rename.target_exists"


def test_api_mount_delete_removes_file(monkeypatch, settings):
    """Delete should call provider.remove for files and return 204."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    files: dict[str, MountEntry] = {
        "/report.txt": MountEntry(
            entry_type="file",
            normalized_path="/report.txt",
            name="report.txt",
            size=12,
            modified_at=None,
        ),
    }
    removed: list[str] = []

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = files.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    def _fake_remove(*, mount: dict, normalized_path: str) -> None:
        _ = mount
        removed.append(normalized_path)
        files.pop(normalized_path)

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.remove", _fake_remove)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.delete("/api/v1.0/mounts/alpha-mount/delete/?path=/report.txt")

    assert resp.status_code == 204
    assert removed == ["/report.txt"]
    assert "/report.txt" not in files


def test_api_mount_delete_removes_empty_folder(monkeypatch, settings):
    """Delete should call provider.remove for empty folders and return 204."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    entries: dict[str, MountEntry] = {
        "/projects": MountEntry(
            entry_type="folder",
            normalized_path="/projects",
            name="projects",
            size=None,
            modified_at=None,
        ),
    }
    removed: list[str] = []

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        entry = entries.get(normalized_path)
        if entry is None:
            raise MountProviderError(
                failure_class="mount.path.not_found",
                next_action_hint="Verify the path exists and retry.",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        return entry

    def _fake_remove(*, mount: dict, normalized_path: str) -> None:
        _ = mount
        removed.append(normalized_path)
        entries.pop(normalized_path)

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.remove", _fake_remove)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.delete("/api/v1.0/mounts/alpha-mount/delete/?path=/projects")

    assert resp.status_code == 204
    assert removed == ["/projects"]
    assert "/projects" not in entries


def test_api_mount_delete_rejects_root_folder(monkeypatch, settings):
    """Delete must fail closed for the mount root."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

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

    removed: list[str] = []

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr(
        "core.mounts.providers.smb.remove",
        lambda **kwargs: removed.append(kwargs["normalized_path"]),
    )

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.delete("/api/v1.0/mounts/alpha-mount/delete/?path=/")

    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "mount.delete.root_forbidden"
    assert not removed


def test_api_mount_delete_rejects_non_empty_folder(monkeypatch, settings):
    """Delete must surface a stable error when the target folder is not empty."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount
        assert normalized_path == "/projects"
        return MountEntry(
            entry_type="folder",
            normalized_path="/projects",
            name="projects",
            size=None,
            modified_at=None,
        )

    def _fake_remove(*, mount: dict, normalized_path: str) -> None:
        _ = mount
        assert normalized_path == "/projects"
        raise MountProviderError(
            failure_class="mount.path.not_empty",
            next_action_hint="Empty the folder before retrying the delete.",
            public_message="Mount path is not empty.",
            public_code="mount.path.not_empty",
        )

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.remove", _fake_remove)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.delete("/api/v1.0/mounts/alpha-mount/delete/?path=/projects")

    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "mount.path.not_empty"


def test_api_mount_delete_missing_path_returns_404(monkeypatch, settings):
    """Delete must keep a stable not-found contract for missing targets."""

    settings.MOUNTS_REGISTRY = [_make_smb_mount(mount_id="alpha-mount")]

    def _fake_stat(*, mount: dict, normalized_path: str) -> MountEntry:
        _ = mount, normalized_path
        raise MountProviderError(
            failure_class="mount.path.not_found",
            next_action_hint="Verify the path exists and retry.",
            public_message="Mount path not found.",
            public_code="mount.path.not_found",
        )

    monkeypatch.setattr("core.mounts.providers.smb.stat", _fake_stat)
    monkeypatch.setattr("core.mounts.providers.smb.remove", lambda **_: None)

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    resp = client.delete("/api/v1.0/mounts/alpha-mount/delete/?path=/missing")

    assert resp.status_code == 404
    assert resp.json()["errors"][0]["code"] == "mount.path.not_found"
