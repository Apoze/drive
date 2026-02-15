"""Serializers for archive extraction API."""

from __future__ import annotations

from rest_framework import serializers

# pylint: disable=abstract-method


class StartArchiveExtractionSerializer(serializers.Serializer):
    """Validate a request to start an archive extraction job."""

    item_id = serializers.UUIDField()
    destination_folder_id = serializers.UUIDField()
    mode = serializers.ChoiceField(choices=["all", "selection"])
    collision_policy = serializers.ChoiceField(
        choices=["rename", "skip", "overwrite"],
        required=False,
        default="rename",
    )
    create_root_folder = serializers.BooleanField(required=False, default=False)
    selection_paths = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        default=list,
    )

    def validate(self, attrs):
        """Enforce that `selection_paths` is provided when mode is `selection`."""

        mode = attrs.get("mode")
        selection = attrs.get("selection_paths") or []
        if mode == "selection" and not selection:
            raise serializers.ValidationError(
                {"selection_paths": "This field is required when mode=selection."}
            )
        return attrs


class ArchiveExtractionStatusSerializer(serializers.Serializer):
    """Serialize job status payload for polling UIs."""

    state = serializers.CharField()
    progress = serializers.DictField()
    errors = serializers.ListField(child=serializers.DictField(), required=False)
