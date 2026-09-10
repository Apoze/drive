"""Refresh policy independently; a People read must never renew ST permission."""

import json
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .directory import SnapshotError
from .http import read_credential, read_json
from .models import Account


def fetch_policy(principals, *, endpoint=None):
    token = read_credential(settings.SUITE_POLICY_TOKEN_FILE)
    url = (
        (endpoint or settings.SUITE_POLICY_URL)
        + "?"
        + urlencode({"service_id": settings.SUITE_POLICY_SERVICE_ID})
    )
    data = json.dumps(
        {
            "organization_id": settings.SUITE_ORGANIZATION_ID,
            "principals": principals,
        }
    ).encode()
    headers = {
        "X-Service-Auth": "Bearer " + token,
        "Content-Type": "application/json",
    }
    try:
        return read_json(url, data=data, headers=headers, limit=1024 * 1024)
    except (HTTPError, URLError, OSError, ValueError):
        raise SnapshotError("policy_unavailable") from None


def synchronize_policy(fetch=fetch_policy):
    """Bounded batches, with freshness capped by ST's own People verification."""
    last_id = None
    count = 0
    while True:
        query = Account.objects.filter(organization_id=settings.SUITE_ORGANIZATION_ID).order_by(
            "principal_id"
        )
        if last_id:
            query = query.filter(principal_id__gt=last_id)
        principals = [str(p) for p in query.values_list("principal_id", flat=True)[:200]]
        if not principals:
            return count
        started = timezone.now()
        page = fetch(principals)
        if not isinstance(page, dict) or (
            page.get("version") != 1
            or page.get("organization_id") != str(UUID(settings.SUITE_ORGANIZATION_ID))
            or page.get("service_id") != str(settings.SUITE_POLICY_SERVICE_ID)
            or not isinstance(page.get("results"), list)
            or len(page["results"]) != len(principals)
        ):
            raise SnapshotError("invalid_policy")
        seen = set()
        with transaction.atomic():
            for result in page["results"]:
                principal = result.get("principal_id")
                allowed, lease = result.get("allowed"), result.get("lease_seconds")
                if (
                    principal not in principals
                    or principal in seen
                    or type(allowed) is not bool
                    or type(lease) is not int
                    or not 0 <= lease <= settings.SUITE_IDENTITY_MAX_STALE_SECONDS
                ):
                    raise SnapshotError("invalid_policy_decision")
                seen.add(principal)
                checked_at = started - timedelta(
                    seconds=settings.SUITE_IDENTITY_MAX_STALE_SECONDS - lease
                )
                account = Account.objects.select_for_update().get(principal_id=principal)
                if account.policy_observed_at is None or started >= account.policy_observed_at:
                    account.policy_allowed, account.policy_checked_at = (
                        allowed,
                        checked_at,
                    )
                    account.policy_observed_at = started
                    account.save(
                        update_fields=[
                            "policy_allowed",
                            "policy_checked_at",
                            "policy_observed_at",
                        ]
                    )
        last_id = principals[-1]
        count += len(principals)
