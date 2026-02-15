"""
Tests for zip creation source safety (do not follow symlinks on local filesystems).
"""

import os

from django.core.files.storage import FileSystemStorage

import pytest

from core.archive.fs_safe import UnsafeFilesystemPath
from core.archive.zip_create import _source_storage_key_is_safe_to_read

pytestmark = pytest.mark.django_db


def test_zip_create_source_skips_symlink_parent_component(tmp_path):
    """
    A source path that traverses an existing symlink component must be rejected (default).
    """

    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()

    (outside / "b").mkdir()
    (outside / "b" / "secret.txt").write_bytes(b"secret")
    os.symlink(str(outside), str(root / "a"))

    storage = FileSystemStorage(location=str(root))
    assert (
        _source_storage_key_is_safe_to_read(
            storage=storage, key="a/b/secret.txt", strict=False
        )
        is False
    )


def test_zip_create_source_strict_fails_on_symlink_parent_component(tmp_path):
    """Strict mode should fail closed on symlink traversal attempts."""

    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()

    (outside / "b").mkdir()
    (outside / "b" / "secret.txt").write_bytes(b"secret")
    os.symlink(str(outside), str(root / "a"))

    storage = FileSystemStorage(location=str(root))
    with pytest.raises(UnsafeFilesystemPath):
        _source_storage_key_is_safe_to_read(
            storage=storage, key="a/b/secret.txt", strict=True
        )
