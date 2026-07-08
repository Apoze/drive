"""Tests for regular Drive file creation mechanics."""

# pylint: disable=missing-function-docstring

from types import SimpleNamespace
from unittest import mock

import pytest

from core import models
from core.services.file_creation import (
    FileCreationPayload,
    FileCreationStorageMode,
    FileCreationStorageWriteError,
    resolve_new_file_creation_payload,
    write_regular_file_creation_payload,
)


def test_resolve_new_file_creation_payload_uses_creating_placeholder_for_editnew(monkeypatch):
    monkeypatch.setattr(
        "core.services.file_creation.get_wopi_client_config_for_filename",
        lambda **_kwargs: {"urlsrc": "https://wopi.test/editnew"},
    )

    creation_payload = resolve_new_file_creation_payload("docx")

    assert creation_payload.mimetype == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert creation_payload.payload == b""
    assert creation_payload.upload_state == models.ItemUploadStateChoices.CREATING
    assert creation_payload.storage_mode == FileCreationStorageMode.DEFAULT_SAVE


def test_resolve_new_file_creation_payload_builds_ooxml_when_editnew_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        "core.services.file_creation.get_wopi_client_config_for_filename",
        lambda **_kwargs: None,
    )

    creation_payload = resolve_new_file_creation_payload("docx")

    assert creation_payload.mimetype == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert creation_payload.size > 0
    assert creation_payload.upload_state == models.ItemUploadStateChoices.READY
    assert creation_payload.storage_mode == FileCreationStorageMode.DEFAULT_SAVE


def test_write_regular_file_creation_payload_prefers_direct_s3_when_available():
    s3_client = mock.Mock()
    storage = SimpleNamespace(
        connection=SimpleNamespace(meta=SimpleNamespace(client=s3_client)),
        bucket_name="drive-media-storage",
        save=mock.Mock(),
    )
    creation_payload = FileCreationPayload(
        mimetype="text/plain",
        payload=b"hello",
        upload_state=models.ItemUploadStateChoices.READY,
        storage_mode=FileCreationStorageMode.DIRECT_S3_IF_AVAILABLE,
    )

    write_regular_file_creation_payload(
        storage_key="item/id/file.txt",
        creation_payload=creation_payload,
        storage=storage,
    )

    s3_client.put_object.assert_called_once_with(
        Bucket="drive-media-storage",
        Key="item/id/file.txt",
        Body=b"hello",
        ContentType="text/plain",
    )
    storage.save.assert_not_called()


def test_write_regular_file_creation_payload_falls_back_to_storage_save():
    storage = SimpleNamespace(save=mock.Mock())
    creation_payload = FileCreationPayload(
        mimetype="text/plain",
        payload=b"hello",
        upload_state=models.ItemUploadStateChoices.READY,
    )

    write_regular_file_creation_payload(
        storage_key="item/id/file.txt",
        creation_payload=creation_payload,
        storage=storage,
    )

    storage.save.assert_called_once()
    storage_key, saved_file = storage.save.call_args.args
    assert storage_key == "item/id/file.txt"
    assert saved_file.read() == b"hello"


def test_write_regular_file_creation_payload_wraps_storage_errors():
    storage = SimpleNamespace(save=mock.Mock(side_effect=OSError("unavailable")))
    creation_payload = FileCreationPayload(
        mimetype="text/plain",
        payload=b"hello",
        upload_state=models.ItemUploadStateChoices.READY,
    )

    with pytest.raises(FileCreationStorageWriteError):
        write_regular_file_creation_payload(
            storage_key="item/id/file.txt",
            creation_payload=creation_payload,
            storage=storage,
        )
