"""Serializers for mount archive extraction API."""

from __future__ import annotations

from rest_framework import serializers

# pylint: disable=abstract-method


class StartMountArchiveExtractionSerializer(serializers.Serializer):
    """Validate a request to start a mount archive extraction job."""

    item_id = serializers.UUIDField()
    mode = serializers.ChoiceField(choices=["all", "selection"])
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
