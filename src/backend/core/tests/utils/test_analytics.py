"""Direct tests for PostHog helper glue."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from unittest import mock

from django.test import override_settings

import pytest

from core import factories, models
from core.utils.analytics import posthog_capture

pytestmark = pytest.mark.django_db


@override_settings(POSTHOG_KEY="")
def test_posthog_capture_is_noop_without_posthog_key():
    user = factories.UserFactory(email="alice@example.com")

    with mock.patch("core.utils.analytics.posthog.capture") as mock_capture:
        posthog_capture("drive.event", user, {"scope": "test"})

    mock_capture.assert_not_called()


@override_settings(POSTHOG_KEY="test-key")
def test_posthog_capture_enriches_item_and_preserves_original_properties():
    user = factories.UserFactory(email="alice@example.com")
    item = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FILE,
        title="Report",
        filename="report.txt",
        size=42,
        mimetype="text/plain",
    )
    properties = {"scope": "test"}

    with mock.patch("core.utils.analytics.posthog.capture") as mock_capture:
        posthog_capture("drive.event", user, properties, item=item)

    mock_capture.assert_called_once_with(
        "drive.event",
        distinct_id="alice@example.com",
        properties={
            "scope": "test",
            "item_id": item.id,
            "item_title": "Report",
            "item_size": 42,
            "item_mimetype": "text/plain",
            "item_type": models.ItemTypeChoices.FILE,
        },
    )
    assert properties == {"scope": "test"}


@override_settings(POSTHOG_KEY="test-key")
def test_posthog_capture_uses_none_distinct_id_for_anonymous_user():
    with mock.patch("core.utils.analytics.posthog.capture") as mock_capture:
        posthog_capture("drive.event", None, {"scope": "anon"})

    mock_capture.assert_called_once_with(
        "drive.event",
        distinct_id=None,
        properties={"scope": "anon"},
    )
