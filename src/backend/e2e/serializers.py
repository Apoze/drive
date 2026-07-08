"""Serializers for E2E tests."""

from django.conf import settings

from rest_framework import serializers


# Suppress the warning about not implementing `create` and `update` methods
# since we don't use a model and only rely on the serializer for validation
# pylint: disable=abstract-method
class E2EAuthSerializer(serializers.Serializer):
    """Serializer for E2E authentication."""

    email = serializers.EmailField(required=True)


class E2EBootstrapSessionSerializer(serializers.Serializer):
    """Request contract for `bootstrap-session`."""

    run_id = serializers.CharField(required=True, max_length=128)
    worker_id = serializers.CharField(required=True, max_length=128)
    actor_key = serializers.CharField(required=True, max_length=64)
    email = serializers.EmailField(required=False)
    full_name = serializers.CharField(required=False, max_length=100)
    short_name = serializers.CharField(required=False, max_length=100)
    language = serializers.ChoiceField(
        choices=[language[0] for language in settings.LANGUAGES],
        required=False,
        allow_null=True,
    )


class E2EBootstrapScenarioSerializer(serializers.Serializer):
    """Request contract for `bootstrap-scenario`."""

    kind = serializers.ChoiceField(
        choices=[
            "isolated_workspace_root",
            "paired_share",
            "search_dataset",
            "preview_fixture_set",
            "legacy_conversion_fixture",
            "mount_subtree",
        ]
    )
    run_id = serializers.CharField(required=True, max_length=128)
    worker_id = serializers.CharField(required=True, max_length=128)
    actor_key = serializers.CharField(required=True, max_length=64)
    scenario_id = serializers.CharField(required=True, max_length=128)
    secondary_actor_key = serializers.CharField(
        required=False,
        max_length=64,
        default="secondary",
    )
    mount_id = serializers.CharField(required=False, max_length=64)


class E2ECleanupScopeSerializer(serializers.Serializer):
    """Request contract for `cleanup-scope`."""

    run_id = serializers.CharField(required=True, max_length=128)
    worker_id = serializers.CharField(required=False, max_length=128)
    actor_key = serializers.CharField(required=False, max_length=64)
    scenario_id = serializers.CharField(required=False, max_length=128)
    mount_id = serializers.CharField(required=False, max_length=64)

    def validate(self, attrs):
        """Enforce an explicit hierarchy for run / worker / scenario cleanup."""
        worker_id = attrs.get("worker_id")
        actor_key = attrs.get("actor_key")
        scenario_id = attrs.get("scenario_id")

        if actor_key and not worker_id:
            raise serializers.ValidationError(
                {"worker_id": "This field is required when actor_key is provided."}
            )

        if scenario_id and not worker_id:
            raise serializers.ValidationError(
                {"worker_id": "This field is required when scenario_id is provided."}
            )

        if scenario_id and not actor_key:
            raise serializers.ValidationError(
                {"actor_key": "This field is required when scenario_id is provided."}
            )

        return attrs
