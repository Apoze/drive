"""Tests for the item_exports service."""

from unittest import mock

import pytest

from core import factories, models
from core.services.item_exports import (
    export_descendants,
    iter_storage_chunks,
    sanitize_archive_component,
)

pytestmark = pytest.mark.django_db


class _FakeStreamingBody:
    def __init__(self, payload: bytes):
        self.payload = payload

    def iter_chunks(self, chunk_size: int):
        """Yield the stored payload in chunks."""
        for index in range(0, len(self.payload), chunk_size):
            yield self.payload[index : index + chunk_size]


def test_services_item_exports_iter_storage_chunks_returns_full_content():
    """Concatenated chunks rebuild the original payload."""
    payload = b"abcdefghij" * 10

    with mock.patch("core.services.item_exports.default_storage") as storage:
        storage.bucket_name = "bucket"
        storage.connection.meta.client.get_object.return_value = {
            "Body": _FakeStreamingBody(payload),
        }

        assert b"".join(iter_storage_chunks("object-key", chunk_size=8)) == payload

    storage.connection.meta.client.get_object.assert_called_once_with(
        Bucket="bucket",
        Key="object-key",
    )


def test_services_item_exports_iter_storage_chunks_respects_chunk_size():
    """A small chunk_size yields several chunks bounded by that size."""
    payload = b"abcdefghij" * 10

    with mock.patch("core.services.item_exports.default_storage") as storage:
        storage.bucket_name = "bucket"
        storage.connection.meta.client.get_object.return_value = {
            "Body": _FakeStreamingBody(payload),
        }

        chunks = list(iter_storage_chunks("object-key", chunk_size=8))

    assert len(chunks) > 1
    assert all(len(chunk) <= 8 for chunk in chunks)
    assert b"".join(chunks) == payload


def test_services_item_exports_iter_storage_chunks_missing_object(caplog):
    """A key missing from object storage yields no chunks and logs no raw key."""

    class _NoSuchKey(Exception):
        pass

    with mock.patch("core.services.item_exports.default_storage") as storage:
        storage.bucket_name = "bucket"
        storage.connection.meta.client.exceptions.NoSuchKey = _NoSuchKey
        storage.connection.meta.client.get_object.side_effect = _NoSuchKey()

        chunks = list(iter_storage_chunks("private/path/file.txt"))

    assert not chunks
    assert "private/path/file.txt" not in caplog.text
    assert "key_hash=" in caplog.text


@pytest.mark.parametrize(
    ("raw", "sanitized"),
    [
        ("safe name.txt", "safe name.txt"),
        ("../unsafe\\name\x00.txt", "_unsafe_name_.txt"),
        ("..", "item"),
        ("\x00/\\", "item"),
    ],
)
def test_services_item_exports_sanitize_archive_component(raw, sanitized):
    """ZIP path components are normalized deterministically."""
    assert sanitize_archive_component(raw) == sanitized


def test_services_item_exports_export_descendants_yields_file_key_and_relative_archive_path():
    """A single ready file is emitted as one (file_key, archive_path) tuple."""
    folder = factories.ItemFactory(type=models.ItemTypeChoices.FOLDER)
    file_item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="hello.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
    )

    descendants = list(export_descendants(folder))

    assert descendants == [(file_item.file_key, "hello.txt")]


def test_services_item_exports_export_descendants_builds_hierarchical_archive_path():
    """Files nested in subfolders carry their folder path in archive_path."""
    root = factories.ItemFactory(type=models.ItemTypeChoices.FOLDER)
    sub = factories.ItemFactory(parent=root, type=models.ItemTypeChoices.FOLDER, title="sub")
    top_file = factories.ItemFactory(
        parent=root,
        type=models.ItemTypeChoices.FILE,
        filename="top.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
    )
    nested_file = factories.ItemFactory(
        parent=sub,
        type=models.ItemTypeChoices.FILE,
        filename="nested.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
    )

    by_archive_path = {
        archive_path: file_key for file_key, archive_path in export_descendants(root)
    }

    assert by_archive_path == {
        "top.txt": top_file.file_key,
        "sub/": None,
        "sub/nested.txt": nested_file.file_key,
    }


@pytest.mark.parametrize(
    "upload_state",
    [
        state
        for state in models.ItemUploadStateChoices.values
        if state != models.ItemUploadStateChoices.READY
    ],
)
def test_services_item_exports_export_descendants_skips_non_ready_files(upload_state):
    """Only files in the READY upload state are yielded."""
    folder = factories.ItemFactory(type=models.ItemTypeChoices.FOLDER)
    factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="busy.txt",
        upload_state=upload_state,
    )
    ready = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="ready.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
    )

    descendants = list(export_descendants(folder))

    assert [file_key for file_key, _ in descendants] == [ready.file_key]


def test_services_item_exports_export_descendants_skips_soft_deleted_descendants():
    """Descendants under a soft-deleted ancestor are excluded."""
    folder = factories.ItemFactory(type=models.ItemTypeChoices.FOLDER)
    factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="keep.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
    )
    deleted_sub = factories.ItemFactory(parent=folder, type=models.ItemTypeChoices.FOLDER)
    factories.ItemFactory(
        parent=deleted_sub,
        type=models.ItemTypeChoices.FILE,
        filename="drop.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
    )
    deleted_sub.soft_delete()

    descendants = list(export_descendants(folder))

    assert [archive_path for _, archive_path in descendants] == ["keep.txt"]
