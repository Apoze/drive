"""Tests for the purge_deleted_items management command."""

from datetime import timedelta
from io import BytesIO, StringIO
from random import randint
from unittest.mock import patch

from django.core.files.storage import default_storage
from django.core.management import call_command
from django.utils import timezone

import pytest

from core import factories, models

pytestmark = pytest.mark.django_db


def _file_item(**kwargs):
    """Create a file item with a stored object."""
    item = factories.ItemFactory(type=models.ItemTypeChoices.FILE, **kwargs)
    default_storage.save(item.file_key, BytesIO(b"data"))
    return item


def _folder_with_file_child():
    """Create a folder containing one stored file child."""
    parent = factories.ItemFactory(type=models.ItemTypeChoices.FOLDER)
    child = _file_item(parent=parent)
    return parent, child


def _assert_items_exist(*items):
    assert all(models.Item.objects.filter(id=item.id).exists() for item in items)


def _assert_items_deleted(*items):
    assert not any(models.Item.objects.filter(id=item.id).exists() for item in items)


def _assert_storage_exists(*items):
    assert all(default_storage.exists(item.file_key) for item in items)


def _assert_storage_deleted(*items):
    assert not any(default_storage.exists(item.file_key) for item in items)


def test_purge_deleted_items_no_deleted_items(django_assert_num_queries):
    """Nothing happens when there are no purgeable items."""
    with django_assert_num_queries(1):
        call_command("purge_deleted_items")


def test_purge_deleted_items_success(settings):
    """Ensure the command queues hard-deleted and expired soft-deleted items."""
    out = StringIO()

    settings.TRASHBIN_CUTOFF_DAYS = cutoff = randint(0, 50)
    settings.PURGE_GRACE_DAYS = grace = randint(0, 20)

    now = timezone.now()
    purge_now = now - timedelta(days=cutoff + grace)

    not_deleted_file = _file_item()
    not_deleted_parent, not_deleted_child = _folder_with_file_child()

    with patch("django.utils.timezone.now", return_value=now):
        not_purgeable_file = _file_item()
        not_purgeable_file.soft_delete()

        not_purgeable_parent, not_purgeable_child = _folder_with_file_child()
        not_purgeable_parent.soft_delete()

    with patch("django.utils.timezone.now", return_value=purge_now):
        purgeable_file = _file_item()
        purgeable_file.soft_delete()

        purgeable_parent, purgeable_child = _folder_with_file_child()
        purgeable_parent.soft_delete()

    hard_deleted_file = _file_item()
    hard_deleted_file.soft_delete()
    hard_deleted_file.hard_delete()

    hard_deleted_parent, hard_deleted_child = _folder_with_file_child()
    hard_deleted_parent.soft_delete()
    hard_deleted_parent.hard_delete()

    call_command("purge_deleted_items", stdout=out)

    assert "Purged 5 deleted item(s)." in out.getvalue()

    _assert_items_exist(
        not_deleted_file,
        not_deleted_parent,
        not_deleted_child,
        not_purgeable_file,
        not_purgeable_parent,
        not_purgeable_child,
    )
    _assert_items_deleted(
        purgeable_file,
        purgeable_parent,
        purgeable_child,
        hard_deleted_file,
        hard_deleted_parent,
        hard_deleted_child,
    )
    _assert_storage_exists(
        not_deleted_file,
        not_deleted_child,
        not_purgeable_file,
        not_purgeable_child,
    )
    _assert_storage_deleted(
        purgeable_file,
        purgeable_child,
        hard_deleted_file,
        hard_deleted_child,
    )
