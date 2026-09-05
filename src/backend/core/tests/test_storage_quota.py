"""Focused admission proof: concurrent writers share one durable budget."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections
from django.test import override_settings

import pytest

from core import factories
from core.models import StorageQuota
from core.services import storage_quota as quota
from core.services.storage_inventory import audit_accounting


@pytest.mark.django_db(transaction=True)
# pylint: disable-next=too-many-statements
def test_shared_budget_reservation_publication_and_external_growth():  # noqa: PLR0915
    """No double counting, over-admission, replay charge, or unsafe release."""
    actor = factories.UserFactory()
    scopes = ["organization:lab", f"user:{actor.pk}"]
    quota.apply_policy({key: {"limit_bytes": 100} for key in scopes}, revision="v1")
    keys = [quota.resource_key(f"nas-{number}") for number in (1, 2)]
    for key, size in zip(keys, (40, 50), strict=True):
        quota.observe_usage(key=key, size=size, scope_keys=scopes, organization="lab", version="v1")
    # A second view of the same content cannot create a second charge.
    quota.observe_usage(key=keys[0], size=40, scope_keys=scopes, organization="lab", version="v1")
    barrier = Barrier(2)

    def compete(key, size):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            return quota.admit(key=key, actor=actor, size=size)
        except quota.StorageQuotaExceeded:
            return None
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(compete, key, size) for key, size in zip(keys, (50, 60), strict=True)
        ]
        admitted = [operation for future in futures if (operation := future.result(timeout=10))]
    assert len(admitted) == 1
    operation = admitted[0]
    budget = StorageQuota.objects.get(key=scopes[0])
    assert (budget.used_bytes, budget.reserved_bytes) == (90, 10)
    with (
        override_settings(STORAGE_MAX_ACTIVE_WRITES_PER_USER=1),
        pytest.raises(quota.StorageWriteConflict, match="Too many active writes"),
    ):
        quota.admit(
            key=next(key for key in keys if key != operation.resource_key), actor=actor, size=0
        )
    size = operation.previous_size + 10
    with pytest.raises(quota.StorageWriteConflict):
        quota.begin_publication(operation.pk, observed_version="changed", size=size, publication={})
    quota.begin_publication(operation.pk, observed_version="v1", size=size, publication={})
    quota.observe_usage(
        key=operation.resource_key, size=0, scope_keys=scopes, organization="lab", version="missing"
    )
    budget.refresh_from_db()
    assert (budget.used_bytes, budget.reserved_bytes) == (90, 10)
    with pytest.raises(quota.StorageWriteConflict):
        quota.cancel(operation.pk)
    quota.commit(operation.pk, size=size, version="v2")
    quota.commit(operation.pk, size=size, version="v2")
    budget.refresh_from_db()
    assert (budget.used_bytes, budget.reserved_bytes) == (100, 0)
    # External writes are observed even above the configured ceiling.
    quota.observe_usage(
        key=operation.resource_key,
        size=size + 20,
        scope_keys=scopes,
        organization="lab",
        version="external",
    )
    with pytest.raises(quota.StorageQuotaExceeded):
        quota.admit(key=operation.resource_key, actor=actor, size=size + 21)
    shrinking = quota.admit(key=operation.resource_key, actor=actor, size=size)
    quota.cancel(shrinking.pk)
    quota.cancel(shrinking.pk)
    budget.refresh_from_db()
    assert (budget.used_bytes, budget.reserved_bytes) == (120, 0)
    quota.apply_policy(
        {scopes[0]: {"limit_bytes": 80}}, revision="latest", origin="st:lab", version=2
    )
    with pytest.raises(quota.StorageWriteConflict):
        quota.apply_policy(
            {scopes[0]: {"limit_bytes": 1000}}, revision="late-response", origin="st:lab", version=1
        )
    budget.refresh_from_db()
    assert budget.limit_bytes == 80
    assert audit_accounting()["counter_mismatches"] == 0
    StorageQuota.objects.filter(pk=budget.pk).update(used_bytes=121)
    assert audit_accounting()["counter_mismatches"] == 1
