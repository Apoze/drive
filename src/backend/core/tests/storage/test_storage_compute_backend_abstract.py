"""Direct contract tests for the storage compute backend abstract base class."""
# pylint: disable=abstract-class-instantiated

from __future__ import annotations

import pytest

from core.storage.storage_compute_backend import StorageComputeBackend


class _ConcreteStorageComputeBackend(StorageComputeBackend):
    def compute_storage_used(self, users):
        return 123


def test_storage_compute_backend_is_abstract():
    """The abstract base class cannot be instantiated directly."""

    with pytest.raises(TypeError):
        StorageComputeBackend()


def test_storage_compute_backend_allows_minimal_concrete_subclass():
    """A minimal concrete subclass satisfies the documented contract."""

    backend = _ConcreteStorageComputeBackend()

    assert backend.compute_storage_used("users") == 123
