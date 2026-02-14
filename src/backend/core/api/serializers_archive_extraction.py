"""Serializers for archive extraction API."""

from __future__ import annotations

from rest_framework import serializers


class StartArchiveExtractionSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    destination_folder_id = serializers.UUIDField()
    mode = serializers.ChoiceField(choices=["all", "selection"])
    selection_paths = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        default=list,
    )

    def validate(self, attrs):
        mode = attrs.get("mode")
        selection = attrs.get("selection_paths") or []
        if mode == "selection" and not selection:
            raise serializers.ValidationError(
                {"selection_paths": "This field is required when mode=selection."}
            )
        return attrs


class ArchiveExtractionStatusSerializer(serializers.Serializer):
    state = serializers.CharField()
    progress = serializers.DictField()
    errors = serializers.ListField(child=serializers.DictField(), required=False)

