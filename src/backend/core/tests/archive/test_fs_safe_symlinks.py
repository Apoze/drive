"""
Tests for filesystem-safe storage helpers (symlink no-follow).
"""

import os
from io import BytesIO

from django.core.files.storage import FileSystemStorage

import pytest

import core.archive.fs_safe as fs_safe_mod
from core.archive.fs_safe import (
    UnsafeFilesystemPath,
    UnsupportedFilesystemSafety,
    safe_open_storage_for_read,
    safe_write_fileobj_to_storage,
)

pytestmark = pytest.mark.django_db


def test_fs_safe_write_refuses_symlink_component(tmp_path):
    """Writing through a pre-existing symlink component must be refused."""

    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()

    os.symlink(str(outside), str(root / "out"))

    storage = FileSystemStorage(location=str(root))
    with pytest.raises(UnsafeFilesystemPath):
        safe_write_fileobj_to_storage(
            storage,
            name="out/evil.txt",
            fileobj=BytesIO(b"evil"),
        )

    assert not (outside / "evil.txt").exists()


def test_fs_safe_write_refuses_intermediate_symlink_component(tmp_path):
    """Symlinks in intermediate path components must be refused."""

    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()

    os.symlink(str(outside), str(root / "a"))

    storage = FileSystemStorage(location=str(root))
    with pytest.raises(UnsafeFilesystemPath):
        safe_write_fileobj_to_storage(
            storage,
            name="a/b/evil.txt",
            fileobj=BytesIO(b"evil"),
        )

    assert not (outside / "b" / "evil.txt").exists()


def test_fs_safe_read_refuses_intermediate_symlink_component(tmp_path):
    """Reading through a pre-existing symlink component must be refused."""

    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()

    (outside / "b").mkdir()
    (outside / "b" / "secret.txt").write_bytes(b"secret")
    os.symlink(str(outside), str(root / "a"))

    storage = FileSystemStorage(location=str(root))
    with pytest.raises(UnsafeFilesystemPath):
        safe_open_storage_for_read(storage, name="a/b/secret.txt")


def test_fs_safe_requires_storage_path_method(tmp_path):
    """fs_safe helpers must not run against storages without a local path."""

    class NoPathStorage:
        def open(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("not used")

    with pytest.raises(NotImplementedError):
        safe_open_storage_for_read(NoPathStorage(), name="x.txt")


def test_fs_safe_fails_closed_without_openat_support(tmp_path, monkeypatch):
    """If openat/dir_fd support is not available, fs_safe must fail closed."""

    root = tmp_path / "root"
    root.mkdir()
    storage = FileSystemStorage(location=str(root))

    monkeypatch.setattr(fs_safe_mod.os, "supports_dir_fd", set(), raising=False)
    with pytest.raises(UnsupportedFilesystemSafety):
        safe_write_fileobj_to_storage(
            storage,
            name="a.txt",
            fileobj=BytesIO(b"ok"),
        )
