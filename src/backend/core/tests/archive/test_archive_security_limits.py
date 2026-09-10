"""Direct tests for archive security and limits helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

import tarfile
import zipfile
from io import BytesIO

import pytest

from core.archive.extract import _plan_tar, _plan_zip
from core.archive.limits import (
    ArchiveExtractionLimits,
    get_archive_extraction_limits,
    get_archive_extraction_max_archive_size,
)
from core.archive.security import UnsafeArchivePath, normalize_archive_path
from core.services.storage_extract import _plan, _validate_zip_directory
from core.services.storage_quota import StorageWriteConflict


def test_normalize_archive_path_normalizes_and_exposes_parts():
    normalized = normalize_archive_path("./folder\\child/file.txt")

    assert normalized.raw == "./folder\\child/file.txt"
    assert normalized.normalized == "folder/child/file.txt"
    assert normalized.parts == ("folder", "child", "file.txt")
    assert normalized.depth == 3
    assert normalized.name == "file.txt"
    assert normalized.parent_parts == ("folder", "child")


@pytest.mark.parametrize("raw", ["", "/etc/passwd", "../secret.txt", "././"])
def test_normalize_archive_path_rejects_unsafe_inputs(raw):
    with pytest.raises(UnsafeArchivePath):
        normalize_archive_path(raw)


def test_get_archive_extraction_limits_uses_defaults_when_env_missing(monkeypatch):
    for name in (
        "ARCHIVE_EXTRACT_MAX_FILES",
        "ARCHIVE_EXTRACT_MAX_TOTAL_SIZE",
        "ARCHIVE_EXTRACT_MAX_FILE_SIZE",
        "ARCHIVE_EXTRACT_MAX_PATH_LENGTH",
        "ARCHIVE_EXTRACT_MAX_DEPTH",
        "ARCHIVE_EXTRACT_MAX_COMPRESSION_RATIO",
    ):
        monkeypatch.delenv(name, raising=False)

    assert get_archive_extraction_limits() == ArchiveExtractionLimits(
        max_files=10_000,
        max_total_size=5 * 1024**3,
        max_file_size=1 * 1024**3,
        max_path_length=512,
        max_depth=32,
        max_compression_ratio=1000,
    )


def test_get_archive_extraction_limits_and_max_archive_size_support_overrides(monkeypatch):
    monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_FILES", "12")
    monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_TOTAL_SIZE", "345")
    monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_FILE_SIZE", "67")
    monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_PATH_LENGTH", "89")
    monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_DEPTH", "7")
    monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_COMPRESSION_RATIO", "9")
    monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_ARCHIVE_SIZE", "456")

    assert get_archive_extraction_limits() == ArchiveExtractionLimits(
        max_files=12,
        max_total_size=345,
        max_file_size=67,
        max_path_length=89,
        max_depth=7,
        max_compression_ratio=9,
    )
    assert get_archive_extraction_max_archive_size() == 456


def test_plan_zip_filters_and_normalizes_selection():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("folder/a.txt", b"a")
        archive.writestr("folder/sub/b.txt", b"bb")
        archive.writestr("elsewhere.txt", b"x")

    with zipfile.ZipFile(BytesIO(buffer.getvalue())) as archive:
        plan = _plan_zip(
            archive,
            mode="selection",
            selection_paths=["folder/", "folder/a.txt"],
        )

    assert plan.paths == ["folder/a.txt", "folder/sub/b.txt"]
    assert plan.total_files == 2
    assert plan.total_bytes == 3


def test_plan_tar_filters_and_normalizes_selection():
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        data = b"hello"
        info = tarfile.TarInfo("root/hello.txt")
        info.size = len(data)
        archive.addfile(info, BytesIO(data))

        data = b"world!"
        info = tarfile.TarInfo("root/nested/world.txt")
        info.size = len(data)
        archive.addfile(info, BytesIO(data))

    with tarfile.open(fileobj=BytesIO(buffer.getvalue()), mode="r:gz") as archive:
        plan = _plan_tar(archive, mode="selection", selection_paths=["root/nested/"])

    assert plan.paths == ["root/nested/world.txt"]
    assert plan.total_files == 1
    assert plan.total_bytes == 6


def test_unified_extraction_validates_paths_links_collisions_and_tar(monkeypatch):
    """No directory is published before every member passes the common manifest gate."""
    for names in [["../escape"], [".drive-txn-hidden/file"], ["a", "a/b"], ["a/b", "a"]]:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name in names:
                archive.writestr(name, b"x")
        with zipfile.ZipFile(buffer) as archive, pytest.raises((ValueError, StorageWriteConflict)):
            _plan(archive)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        archive.writestr(info, b"target")
    with zipfile.ZipFile(buffer) as archive, pytest.raises((ValueError, StorageWriteConflict)):
        _plan(archive)
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        root = tarfile.TarInfo(".")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        info = tarfile.TarInfo("folder/document.txt")
        info.size = 3
        archive.addfile(info, BytesIO(b"abc"))
    buffer.seek(0)
    with tarfile.open(fileobj=buffer, mode="r:*") as archive:
        assert _plan(archive) == {
            "folder/document.txt": ("file", "folder/document.txt", 3),
            "folder": ("folder", "", 0),
        }
        monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_FILE_SIZE", "2")
        with pytest.raises(StorageWriteConflict, match="TAR data"):
            _plan(archive)


def test_unified_extraction_selection_keeps_only_selected_members_and_empty_folders():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("folder/a.txt", b"a")
        archive.writestr("folder/b.txt", b"b")
        archive.mkdir("empty/")
        archive.mkdir("folder/")
    with zipfile.ZipFile(buffer) as archive:
        assert set(_plan(archive, ["folder/a.txt"])) == {"folder", "folder/a.txt"}
        assert set(_plan(archive, ["folder/"])) == {"folder", "folder/a.txt", "folder/b.txt"}
        assert set(_plan(archive, ["empty/"])) == {"empty"}


def test_unified_zip_footer_limits_metadata_before_zipfile_allocates(monkeypatch):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.txt", b"a")
    _validate_zip_directory(buffer)
    monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_FILES", "0")
    with pytest.raises(StorageWriteConflict, match="metadata limit"):
        _validate_zip_directory(buffer)
