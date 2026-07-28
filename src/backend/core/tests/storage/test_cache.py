"""Tests for the per-user usage cache helpers."""

from unittest import mock

from django.core.cache import cache

import pytest

from core import factories, models
from core.storage.cache import (
    get_storage_used_cache_key,
    invalidate_storage_used_cache,
)

pytestmark = pytest.mark.django_db


def test_invalidate_storage_used_cache_invalidates_entitlements():
    """The entitlements backend cache should be invalidated for the filtered user ids."""
    with mock.patch("core.entitlements.get_entitlements_backend") as mock_get_backend:
        invalidate_storage_used_cache(["user-1", None, "user-2"])

    mock_get_backend.return_value.invalidate_cache.assert_called_once_with(["user-1", "user-2"])


def test_invalidate_storage_used_cache_without_user_ids():
    """Nothing should be invalidated when no valid user id is given."""
    with mock.patch("core.entitlements.get_entitlements_backend") as mock_get_backend:
        invalidate_storage_used_cache([None])

    mock_get_backend.assert_not_called()


def test_item_save_invalidates_previous_and_new_creator_once(
    django_capture_on_commit_callbacks,
):
    """An ownership change must invalidate both regular Item usage caches."""
    previous_creator = factories.UserFactory()
    new_creator = factories.UserFactory()
    item = factories.ItemFactory(
        type=models.ItemTypeChoices.FILE,
        creator=previous_creator,
        size=10,
    )

    with (
        mock.patch("core.models.invalidate_storage_used_cache") as mock_invalidate,
        django_capture_on_commit_callbacks(execute=True),
    ):
        item.creator = new_creator
        item.save(update_fields=["creator"])

    mock_invalidate.assert_called_once_with([previous_creator.id, new_creator.id])


def test_item_save_updates_both_real_usage_caches(django_capture_on_commit_callbacks):
    """The local cache helper drops both creator entries after reassignment."""
    previous_creator = factories.UserFactory()
    new_creator = factories.UserFactory()
    item = factories.ItemFactory(
        type=models.ItemTypeChoices.FILE,
        creator=previous_creator,
        size=10,
    )
    previous_key = get_storage_used_cache_key(previous_creator.id)
    new_key = get_storage_used_cache_key(new_creator.id)
    cache.set(previous_key, 10)
    cache.set(new_key, 0)

    with django_capture_on_commit_callbacks(execute=True):
        item.creator = new_creator
        item.save(update_fields=["creator"])

    assert cache.get(previous_key) is None
    assert cache.get(new_key) is None
