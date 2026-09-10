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


@pytest.fixture(autouse=True)
def isolate_session_pools():
    """Each test owns its mocked SMB connections."""
    smb_provider._SESSIONS.clear()  # pylint: disable=protected-access
    smb_provider.get_mount_secret_resolver.cache_clear()
    yield
    smb_provider._SESSIONS.clear()  # pylint: disable=protected-access
    smb_provider.get_mount_secret_resolver.cache_clear()


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

    visited = []
    closed = []

    def _scandir(path: str, **kwargs):
        _ = path, kwargs
        entries = [
            _FakeDirEntry(name="z", st_mode=statlib.S_IFDIR),
            _FakeDirEntry(name="A.txt", st_mode=statlib.S_IFREG, st_size=10),
            _FakeDirEntry(name="b", st_mode=statlib.S_IFDIR),
        ]
        try:
            for entry in entries:
                visited.append(entry.name)
                yield entry
        finally:
            closed.append(True)

    monkeypatch.setattr(smb_provider.smbclient, "register_session", _register_session)
    monkeypatch.setattr(smb_provider.smbclient, "stat", _stat)
    monkeypatch.setattr(smb_provider.smbclient, "scandir", _scandir)

    stream = smb_provider.iter_children(mount=_mount(), normalized_path="/")
    assert next(stream).name == "z"
    assert visited == ["z"]
    stream.close()
    assert closed == [True]
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
    """Share failures keep SMB diagnostics but expose generic public fields."""
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
    assert excinfo.value.public_code == "mount.provider.location_not_found"
    assert excinfo.value.public_message == "Mount location not found."
    assert "SMB" not in excinfo.value.public_message


def test_smb_provider_maps_auth_failure(monkeypatch):
    """Auth failures keep SMB diagnostics but expose generic public fields."""
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
    assert excinfo.value.public_code == "mount.provider.auth_failed"
    assert excinfo.value.public_message == "Mount authentication failed."
    assert "SMB" not in excinfo.value.public_message


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


def test_smb_connections_isolate_accounts_and_retire_after_last_reader(monkeypatch, tmp_path):
    """Rotation must not borrow another account or close an active reader."""
    secret_file = tmp_path / "nas.secret"
    secret_file.write_text("first", encoding="utf-8")
    monkeypatch.setenv("SMB_OTHER_PASSWORD", "other")
    registrations = []
    reads = []
    closed = []
    monkeypatch.setattr(
        smb_provider.smbclient,
        "register_session",
        lambda server, **kwargs: registrations.append(kwargs),
    )
    monkeypatch.setattr(
        smb_provider.smbclient,
        "reset_connection_cache",
        lambda **kwargs: closed.append(kwargs["connection_cache"]),
    )

    def open_file(path, **kwargs):
        assert path
        reads.append(kwargs)
        return SimpleNamespace(close=lambda: None)

    monkeypatch.setattr(smb_provider.smbclient, "open_file", open_file)
    first = _mount()
    first["password_secret_path"] = str(secret_file)
    second = _mount(password_ref="SMB_OTHER_PASSWORD")
    second["mount_id"] = "second-mount"
    second["params"]["username"] = "second-account"
    second["params"]["port"] = 1445
    with smb_provider.open_read(mount=first, normalized_path="/a"):
        with smb_provider.open_read(mount=second, normalized_path="/b"):
            assert reads[-1]["username"] == "second-account"
            assert reads[-1]["port"] == 1445
            assert reads[0]["connection_cache"] is not reads[1]["connection_cache"]
        secret_file.write_text("rotated", encoding="utf-8")
        with smb_provider.open_read(mount=first, normalized_path="/c"):
            assert reads[-1]["password"] == "rotated"
            assert reads[0]["connection_cache"] is not reads[-1]["connection_cache"]
            assert not closed
        assert not closed
    assert len(registrations) == 3
    assert len(closed) == 1
    assert closed[0] is reads[0]["connection_cache"]
