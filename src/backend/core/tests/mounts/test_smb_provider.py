"""Unit tests for SMB MountProvider (stat/list contract)."""
# pylint: disable=missing-function-docstring,no-value-for-parameter

from __future__ import annotations

import stat as statlib
from types import SimpleNamespace

import pytest
from smbprotocol.exceptions import (
    BadNetworkName,
    LogonFailure,
    SharingViolation,
    SMBOSError,
)
from smbprotocol.header import NtStatus

from core.mounts.providers import smb as smb_provider
from core.mounts.providers.base import MountProviderError

pytestmark = pytest.mark.django_db


def _mount(*, password_ref: str = "SMB_PASSWORD") -> dict:
    return {
        "mount_id": "alpha-mount",
        "provider": "smb",
        "password_secret_ref": password_ref,
        "params": {
            "server": "smb.internal",
            "share": "finance",
            "username": "svc",
            "port": 445,
        },
    }


class _FakeDirEntry:
    def __init__(self, *, name: str, st_mode: int, st_size: int = 0) -> None:
        self.name = name
        self._st = SimpleNamespace(st_mode=st_mode, st_size=st_size, st_mtime=1700000000)

    def stat(self):
        """Return a minimal stat-like object."""

        return self._st


def test_smb_provider_stat_returns_entry(monkeypatch):
    """stat returns a MountEntry with normalized paths."""
    monkeypatch.setenv("SMB_PASSWORD", "pw")

    calls: list[str] = []

    def _register_session(server: str, **kwargs):
        calls.append(f"register:{server}")

    def _stat(path: str, **kwargs):
        calls.append(f"stat:{path}")
        return SimpleNamespace(st_mode=statlib.S_IFDIR, st_size=0, st_mtime=1700000000)

    monkeypatch.setattr(smb_provider.smbclient, "register_session", _register_session)
    monkeypatch.setattr(smb_provider.smbclient, "stat", _stat)

    entry = smb_provider.stat(mount=_mount(), normalized_path="/")
    assert entry.entry_type == "folder"
    assert entry.normalized_path == "/"
    assert entry.name == "/"
    assert any("stat:\\\\" in c for c in calls)


def test_smb_provider_list_children_is_deterministically_sorted(monkeypatch):
    """list_children returns folders-first ordering (case-insensitive by name)."""
    monkeypatch.setenv("SMB_PASSWORD", "pw")

    def _register_session(server: str, **kwargs):
        _ = server

    def _stat(path: str, **kwargs):
        _ = path
        return SimpleNamespace(st_mode=statlib.S_IFDIR, st_size=0, st_mtime=1700000000)

    def _scandir(path: str, **kwargs):
        _ = path, kwargs
        return [
            _FakeDirEntry(name="z", st_mode=statlib.S_IFDIR),
            _FakeDirEntry(name="A.txt", st_mode=statlib.S_IFREG, st_size=10),
            _FakeDirEntry(name="b", st_mode=statlib.S_IFDIR),
        ]

    monkeypatch.setattr(smb_provider.smbclient, "register_session", _register_session)
    monkeypatch.setattr(smb_provider.smbclient, "stat", _stat)
    monkeypatch.setattr(smb_provider.smbclient, "scandir", _scandir)

    entries = smb_provider.list_children(mount=_mount(), normalized_path="/")
    assert [e.normalized_path for e in entries] == ["/b", "/z", "/A.txt"]


def test_smb_provider_maps_missing_path_to_mount_path_not_found(monkeypatch):
    """Missing SMB paths map to mount.path.not_found deterministically."""
    monkeypatch.setenv("SMB_PASSWORD", "pw")

    def _register_session(server: str, **kwargs):
        _ = server

    def _stat(path: str, **kwargs):
        raise SMBOSError(NtStatus.STATUS_OBJECT_NAME_NOT_FOUND, path)

    monkeypatch.setattr(smb_provider.smbclient, "register_session", _register_session)
    monkeypatch.setattr(smb_provider.smbclient, "stat", _stat)

    with pytest.raises(MountProviderError) as excinfo:
        smb_provider.stat(mount=_mount(), normalized_path="/missing")

    assert excinfo.value.public_code == "mount.path.not_found"
    assert excinfo.value.failure_class == "mount.path.not_found"


def test_smb_provider_maps_share_not_found(monkeypatch):
    """Share not found is mapped to mount.smb.env.share_not_found."""
    monkeypatch.setenv("SMB_PASSWORD", "pw")

    def _register_session(server: str, **kwargs):
        _ = server

    def _stat(path: str, **kwargs):
        raise BadNetworkName()  # pylint: disable=no-value-for-parameter

    monkeypatch.setattr(smb_provider.smbclient, "register_session", _register_session)
    monkeypatch.setattr(smb_provider.smbclient, "stat", _stat)

    with pytest.raises(MountProviderError) as excinfo:
        smb_provider.stat(mount=_mount(), normalized_path="/")
    assert excinfo.value.failure_class == "mount.smb.env.share_not_found"


def test_smb_provider_maps_auth_failure(monkeypatch):
    """Auth failures are mapped to mount.smb.env.auth_failed."""
    monkeypatch.setenv("SMB_PASSWORD", "pw")

    def _register_session(server: str, **kwargs):
        _ = server

    def _stat(path: str, **kwargs):
        raise LogonFailure()  # pylint: disable=no-value-for-parameter

    monkeypatch.setattr(smb_provider.smbclient, "register_session", _register_session)
    monkeypatch.setattr(smb_provider.smbclient, "stat", _stat)

    with pytest.raises(MountProviderError) as excinfo:
        smb_provider.stat(mount=_mount(), normalized_path="/")
    assert excinfo.value.failure_class == "mount.smb.env.auth_failed"


def test_smb_provider_open_read_allows_shared_readers(monkeypatch):
    """open_read must not take an exclusive SMB handle for read-only previews."""
    monkeypatch.setenv("SMB_PASSWORD", "pw")

    calls: list[tuple[str, str | None]] = []

    class _FakeFile:
        def close(self):
            return None

    def _register_session(server: str, **kwargs):
        _ = server, kwargs

    def _open_file(path: str, **kwargs):
        calls.append((path, kwargs.get("share_access")))
        return _FakeFile()

    monkeypatch.setattr(smb_provider.smbclient, "register_session", _register_session)
    monkeypatch.setattr(smb_provider.smbclient, "open_file", _open_file)

    with smb_provider.open_read(mount=_mount(), normalized_path="/demo.txt"):
        pass

    assert calls
    assert calls[0][1] == "r"


def test_smb_provider_maps_sharing_violation_to_busy(monkeypatch):
    """Concurrent access conflicts should not be reported as path-not-found."""
    monkeypatch.setenv("SMB_PASSWORD", "pw")

    def _register_session(server: str, **kwargs):
        _ = server, kwargs

    def _open_file(path: str, **kwargs):
        _ = path, kwargs
        raise SharingViolation()

    monkeypatch.setattr(smb_provider.smbclient, "register_session", _register_session)
    monkeypatch.setattr(smb_provider.smbclient, "open_file", _open_file)

    with pytest.raises(MountProviderError) as excinfo:
        with smb_provider.open_read(mount=_mount(), normalized_path="/busy.txt"):
            pass

    assert excinfo.value.public_code == "mount.path.busy"
    assert excinfo.value.failure_class == "mount.path.busy"


def test_smb_provider_remove_uses_rmdir_for_folders(monkeypatch):
    """remove should delete empty folders with rmdir instead of file remove."""
    monkeypatch.setenv("SMB_PASSWORD", "pw")

    calls: list[tuple[str, str]] = []

    def _register_session(server: str, **kwargs):
        _ = server, kwargs

    def _stat(path: str, **kwargs):
        _ = kwargs
        calls.append(("stat", path))
        return SimpleNamespace(st_mode=statlib.S_IFDIR, st_size=0, st_mtime=1700000000)

    def _rmdir(path: str, **kwargs):
        _ = kwargs
        calls.append(("rmdir", path))

    def _remove(path: str, **kwargs):
        _ = kwargs
        calls.append(("remove", path))

    monkeypatch.setattr(smb_provider.smbclient, "register_session", _register_session)
    monkeypatch.setattr(smb_provider.smbclient, "stat", _stat)
    monkeypatch.setattr(smb_provider.smbclient, "rmdir", _rmdir)
    monkeypatch.setattr(smb_provider.smbclient, "remove", _remove)

    smb_provider.remove(mount=_mount(), normalized_path="/projects")

    assert calls[0][0] == "stat"
    assert calls[1][0] == "rmdir"
    assert all(call[0] != "remove" for call in calls)


def test_smb_provider_remove_maps_non_empty_folder(monkeypatch):
    """remove should surface a stable not-empty code for non-empty folders."""
    monkeypatch.setenv("SMB_PASSWORD", "pw")

    def _register_session(server: str, **kwargs):
        _ = server, kwargs

    def _stat(path: str, **kwargs):
        _ = path, kwargs
        return SimpleNamespace(st_mode=statlib.S_IFDIR, st_size=0, st_mtime=1700000000)

    def _rmdir(path: str, **kwargs):
        _ = path, kwargs
        raise OSError(39, "Directory not empty")

    monkeypatch.setattr(smb_provider.smbclient, "register_session", _register_session)
    monkeypatch.setattr(smb_provider.smbclient, "stat", _stat)
    monkeypatch.setattr(smb_provider.smbclient, "rmdir", _rmdir)
    monkeypatch.setattr(smb_provider.smbclient, "remove", lambda *args, **kwargs: None)

    with pytest.raises(MountProviderError) as excinfo:
        smb_provider.remove(mount=_mount(), normalized_path="/projects")

    assert excinfo.value.public_code == "mount.path.not_empty"
    assert excinfo.value.failure_class == "mount.path.not_empty"
