"""Direct contract tests for storage compute backend support surfaces."""
# pylint: disable=unused-argument

from __future__ import annotations

from core import factories, models
from core.storage import get_storage_compute_backend
from core.storage.creator_storage_compute_backend import CreatorStorageComputeBackend


class _FakeStorageBackend:
    instances = 0

    def __init__(self) -> None:
        type(self).instances += 1


class _SecondFakeStorageBackend:
    pass


def test_get_storage_compute_backend_is_a_singleton(settings):
    """The storage backend resolver instantiates only once per cache window."""

    get_storage_compute_backend.cache_clear()
    _FakeStorageBackend.instances = 0
    settings.STORAGE_COMPUTE_BACKEND = (
        "core.tests.storage.test_storage_compute_backend._FakeStorageBackend"
    )

    first = get_storage_compute_backend()
    second = get_storage_compute_backend()

    assert first is second
    assert isinstance(first, _FakeStorageBackend)
    assert _FakeStorageBackend.instances == 1


def test_get_storage_compute_backend_reloads_after_cache_clear(settings):
    """Cache clearing allows the configured backend class to change."""

    get_storage_compute_backend.cache_clear()
    settings.STORAGE_COMPUTE_BACKEND = (
        "core.tests.storage.test_storage_compute_backend._FakeStorageBackend"
    )
    first = get_storage_compute_backend()

    get_storage_compute_backend.cache_clear()
    settings.STORAGE_COMPUTE_BACKEND = (
        "core.tests.storage.test_storage_compute_backend._SecondFakeStorageBackend"
    )
    second = get_storage_compute_backend()

    assert isinstance(first, _FakeStorageBackend)
    assert isinstance(second, _SecondFakeStorageBackend)


def test_creator_storage_compute_backend_sums_sizes_for_creator(db):
    """Only the target creator's item sizes contribute to the quota."""

    user = factories.UserFactory()
    other_user = factories.UserFactory()
    factories.ItemFactory(creator=user, type=models.ItemTypeChoices.FILE, size=10)
    factories.ItemFactory(creator=user, type=models.ItemTypeChoices.FILE, size=15)
    factories.ItemFactory(creator=user, type=models.ItemTypeChoices.FILE, size=None)
    factories.ItemFactory(creator=other_user, type=models.ItemTypeChoices.FILE, size=99)

    backend = CreatorStorageComputeBackend()

    assert backend.compute_storage_used(models.User.objects.filter(pk=user.pk)) == 25


def test_creator_storage_compute_backend_returns_zero_without_items(db):
    """The quota backend returns zero when the creator has no matching items."""

    user = factories.UserFactory()

    backend = CreatorStorageComputeBackend()

    assert backend.compute_storage_used(models.User.objects.filter(pk=user.pk)) == 0
