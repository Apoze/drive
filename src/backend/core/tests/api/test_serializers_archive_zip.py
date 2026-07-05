"""Direct contract tests for archive zip serializers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

from uuid import uuid4

from core.api.serializers_archive_zip import (
    ArchiveZipStatusSerializer,
    StartArchiveZipSerializer,
)


def test_start_archive_zip_serializer_accepts_valid_payload_and_trims_archive_name():
    serializer = StartArchiveZipSerializer(
        data={
            "item_ids": [str(uuid4()), str(uuid4())],
            "destination_folder_id": str(uuid4()),
            "archive_name": "  My export.ZIP  ",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["archive_name"] == "My export.ZIP"


def test_start_archive_zip_serializer_requires_zip_suffix():
    serializer = StartArchiveZipSerializer(
        data={
            "item_ids": [str(uuid4())],
            "destination_folder_id": str(uuid4()),
            "archive_name": "archive.tar",
        }
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {"archive_name": ["Archive name must end with .zip."]}


def test_start_archive_zip_serializer_rejects_slashes():
    serializer = StartArchiveZipSerializer(
        data={
            "item_ids": [str(uuid4())],
            "destination_folder_id": str(uuid4()),
            "archive_name": "folder/export.zip",
        }
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {"archive_name": ["Archive name must not contain slashes."]}


def test_archive_zip_status_serializer_validates_polling_payload():
    result_item_id = uuid4()
    serializer = ArchiveZipStatusSerializer(
        data={
            "state": "done",
            "progress": {
                "total": 2,
                "files_done": 2,
            },
            "errors": [],
            "result_item_id": str(result_item_id),
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["result_item_id"] == result_item_id
