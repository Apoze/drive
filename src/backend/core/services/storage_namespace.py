"""Fence topology changes while permitting concurrent ordinary mount writes."""

from contextlib import contextmanager

from django.db import connection

from core.models import StorageBackend, StorageReservation
from core.services import storage_quota as quota


class StorageOperationBusy(quota.StorageWriteConflict):
    """A live worker holds the lock; retrying later is safe."""


@contextmanager
def advisory_guard(key, *, shared=False):
    """PostgreSQL releases the operation lock when its worker disconnects."""
    lock_id = int(quota.resource_key(key)[:16], 16) - 2**63
    suffix = "_shared" if shared else ""
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT pg_try_advisory_lock{suffix}(%s)", [lock_id])
        if not cursor.fetchone()[0]:
            raise StorageOperationBusy("A storage operation is already running.")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT pg_advisory_unlock{suffix}(%s)", [lock_id])


@contextmanager
def namespace_guard(backend, *, exclusive=False, recovery=False, allow_maintenance=False):
    """Session locks disappear on crash; a durable journal fences unfinished moves."""
    with advisory_guard(f"topology:{backend.namespace}", shared=not exclusive):
        if (
            not recovery
            and not allow_maintenance
            and StorageBackend.objects.filter(
                namespace=backend.namespace,
                maintenance=True,
            ).exists()
        ):
            raise quota.StorageWriteConflict(
                "This storage is temporarily read-only for maintenance."
            )
        if (
            not recovery
            and StorageReservation.objects.filter(
                state__in=["reserved", "writing", "publishing"],
                publication__namespace=str(backend.namespace),
                publication__kind__in=["tree_move", "reclassify", "delete"],
            ).exists()
        ):
            raise quota.StorageWriteConflict("A storage topology change needs recovery.")
        yield
