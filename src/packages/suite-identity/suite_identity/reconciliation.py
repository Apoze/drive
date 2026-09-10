"""Bounded reconciliation usable by both Celery and native process supervisors."""

import logging

from django.conf import settings
from django.db import connection

from .directory import SnapshotError, synchronize
from .policy import synchronize_policy

logger = logging.getLogger(__name__)


def synchronize_identity():
    """No overlapping imports; a missed run cannot renew an authorization lease."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(1937074548, 1)")
        if not cursor.fetchone()[0]:
            return
    try:
        for operation in (synchronize, synchronize_policy):
            if operation is synchronize_policy and not settings.SUITE_POLICY_URL:
                continue
            try:
                operation()
            except SnapshotError as exc:
                logger.warning("Suite reconciliation deferred: %s", str(exc))
            except Exception as exc:  # noqa: BLE001 - worker errors may contain credentials; log only the class.
                logger.error("Suite reconciliation failed (%s)", type(exc).__name__)
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(1937074548, 1)")
