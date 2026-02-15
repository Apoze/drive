"""Serializers for archive zip creation API."""

from __future__ import annotations

from rest_framework import serializers

# pylint: disable=abstract-method


class StartArchiveZipSerializer(serializers.Serializer):
    """Validate a request to start a zip creation job."""

    item_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    destination_folder_id = serializers.UUIDField()
    archive_name = serializers.CharField(max_length=255)

    def validate_archive_name(self, value: str) -> str:
        value = (value or "").strip()
        if not value.lower().endswith(".zip"):
            raise serializers.ValidationError("Archive name must end with .zip.")
        if "/" in value or "\\" in value:
            raise serializers.ValidationError("Archive name must not contain slashes.")
        return value


class ArchiveZipStatusSerializer(serializers.Serializer):
    """Serialize job status payload for polling UIs."""

    state = serializers.CharField()
    progress = serializers.DictField()
    errors = serializers.ListField(child=serializers.DictField(), required=False)
    result_item_id = serializers.UUIDField(required=False)

