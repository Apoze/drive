"""Direct contract tests for custom DRF fields."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

from core.api.fields import JSONField


def test_json_field_to_representation_returns_value_as_is():
    field = JSONField()
    payload = {"hello": ["world"], "count": 2}

    assert field.to_representation(payload) == payload


def test_json_field_to_internal_value_serializes_python_value_to_json_string():
    field = JSONField()

    assert field.to_internal_value({"hello": "world", "count": 2}) == (
        '{"hello": "world", "count": 2}'
    )


def test_json_field_to_internal_value_preserves_none():
    field = JSONField()

    assert field.to_internal_value(None) is None
