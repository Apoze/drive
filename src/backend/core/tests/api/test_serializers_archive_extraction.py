"""Direct contract tests for archive extraction serializers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

from uuid import uuid4

from core.api.serializers_archive_extraction import (
    ArchiveExtractionStatusSerializer,
    StartArchiveExtractionSerializer,
)
from core.api.serializers_mount_archive_extraction import (
    StartMountArchiveExtractionSerializer,
)


def test_start_archive_extraction_serializer_accepts_mode_all_and_applies_defaults():
    serializer = StartArchiveExtractionSerializer(
        data={
            "item_id": str(uuid4()),
            "destination_folder_id": str(uuid4()),
            "mode": "all",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["collision_policy"] == "rename"
    assert serializer.validated_data["create_root_folder"] is False
    assert serializer.validated_data["selection_paths"] == []


def test_start_archive_extraction_serializer_requires_selection_paths_in_selection_mode():
    serializer = StartArchiveExtractionSerializer(
        data={
            "item_id": str(uuid4()),
            "destination_folder_id": str(uuid4()),
            "mode": "selection",
        }
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {"selection_paths": ["This field is required when mode=selection."]}


def test_start_mount_archive_extraction_serializer_accepts_mode_all_and_defaults_selection_paths():
    serializer = StartMountArchiveExtractionSerializer(
        data={
            "item_id": str(uuid4()),
            "mode": "all",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["selection_paths"] == []


def test_start_mount_archive_extraction_serializer_requires_selection_paths_in_selection_mode():
    serializer = StartMountArchiveExtractionSerializer(
        data={
            "item_id": str(uuid4()),
            "mode": "selection",
        }
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {"selection_paths": ["This field is required when mode=selection."]}


def test_archive_extraction_status_serializer_validates_polling_payload():
    serializer = ArchiveExtractionStatusSerializer(
        data={
            "state": "done",
            "progress": {
                "total": 3,
                "files_done": 3,
            },
            "errors": [
                {
                    "code": "archive.entry.skipped",
                    "message": "Skipped duplicate entry.",
                }
            ],
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["state"] == "done"
    assert serializer.validated_data["progress"]["total"] == 3
