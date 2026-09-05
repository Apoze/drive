"""DeployCenter Entitlements Backend."""

import logging
from collections.abc import Mapping
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

import requests
from rest_framework.exceptions import PermissionDenied

from core.api.serializers import (
    OrganizationUsageMetricSerializer,
    UserUsageMetricSerializer,
)
from core.entitlements.backends.base import (
    CanUploadReason,
    EntitlementDecision,
    EntitlementsBackend,
    QuotaError,
    QuotaReason,
    QuotaState,
    normalize_public_entitlement_code,
)
from core.models import User

logger = logging.getLogger(__name__)

ENTITLEMENTS_CACHE_KEY_PREFIX = "entitlements:user:"


def _mapping(value):
    """Return provider data only when it is a mapping."""
    return value if isinstance(value, Mapping) else {}


def _non_negative_int(value):
    """Accept quota numbers, excluding booleans and malformed provider data."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    return int(value)


class DeployCenterEntitlementsBackend(EntitlementsBackend):
    """Entitlements backend that checks permissions via a DeployCenter service."""

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(  # noqa: PLR0913
        self,
        base_url,
        service_id,
        api_key=None,
        cache_timeout=10,
        oidc_claims=None,
        organization_claim="siret",
        api_key_file=None,
    ):
        self.base_url = base_url
        self.service_id = service_id
        if api_key_file:
            if api_key:
                raise ValueError("Configure one service key source.")
            with Path(api_key_file).open(encoding="utf-8") as source:
                api_key = source.read(4097).strip()
        if not isinstance(api_key, str) or not api_key or len(api_key) > 4096:
            raise ValueError("A valid DeployCenter service key is required.")
        self.api_key = api_key
        self.cache_timeout = cache_timeout
        self.oidc_claims = oidc_claims or []
        self.organization_claim = organization_claim

    def build_usage_metrics(self, user):
        """Build the usage metric entries pushed to the DeployCenter service."""
        serialized_user = UserUsageMetricSerializer(user).data
        user_entry = {
            "account": serialized_user["account"],
            "metrics": serialized_user["metrics"],
        }
        organization_value = user.claims.get(self.organization_claim)
        if (
            organization_value is None
            and self.organization_claim == "organization_id"
            and settings.STORAGE_ORGANIZATION_ID != "local"
        ):
            organization_value = settings.STORAGE_ORGANIZATION_ID
        if organization_value is None:
            return [user_entry]
        user_entry[self.organization_claim] = organization_value
        organization_users = User.objects.filter(
            **{f"claims__{self.organization_claim}": organization_value}
        )
        organization_entry = OrganizationUsageMetricSerializer(
            {
                "account_id_key": self.organization_claim,
                "account_id_value": organization_value,
                "users": organization_users,
            }
        ).data
        entries = [user_entry, organization_entry]
        if settings.STORAGE_GOVERNANCE_ENABLED:
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_inventory import resource_metrics  # noqa: PLC0415

            entries.extend(
                {**entry, self.organization_claim: organization_value}
                for entry in resource_metrics(str(organization_value), user)
            )
        return entries

    def fetch_entitlements(self, user, *, policy_applied=None):
        """Fetch entitlements for a user from the DeployCenter service."""
        params = {
            "account_type": "user",
            "account_id": user.sub,
            "account_email": user.email,
            "service_id": self.service_id,
        }
        for claim in self.oidc_claims:
            value = user.claims.get(claim)
            if value is not None:
                params[claim] = value

        organization_value = user.claims.get(self.organization_claim)
        if (
            organization_value is None
            and self.organization_claim == "organization_id"
            and settings.STORAGE_ORGANIZATION_ID != "local"
        ):
            organization_value = settings.STORAGE_ORGANIZATION_ID
        if organization_value is not None:
            params[self.organization_claim] = organization_value

        response = requests.post(
            self.base_url,
            params=params,
            json={
                "usage_metrics": self.build_usage_metrics(user),
                **({"policy_applied": policy_applied} if policy_applied else {}),
            },
            headers={"X-Service-Auth": f"Bearer {self.api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def acknowledge_policy(self, user, revision):
        """Idempotently report the revision actually committed to Drive's counters."""
        key = f"storage-policy-ack:{self.service_id}:{user.pk}:{revision}"
        if cache.get(key):
            return
        self.fetch_entitlements(
            user, policy_applied={"revision": revision, "applied_at": timezone.now().isoformat()}
        )
        cache.set(key, True, timeout=300)

    def get_entitlements(self, user):
        """Get entitlements for a user, cached."""
        cache_key = f"{ENTITLEMENTS_CACHE_KEY_PREFIX}{user.id}"
        entitlements = cache.get(cache_key)
        if entitlements:
            return entitlements
        try:
            entitlements = self.fetch_entitlements(user)
        except requests.RequestException:
            logger.exception("Failed to fetch entitlements for user %s", user.id)
            raise
        cache.set(cache_key, entitlements, timeout=self.cache_timeout)
        return entitlements

    def invalidate_cache(self, user_ids):
        """Drop cached entitlements so the next read refetches from DeployCenter."""
        cache.delete_many([f"{ENTITLEMENTS_CACHE_KEY_PREFIX}{user_id}" for user_id in user_ids])

    def get_storage_policy(self, user):
        """Return versioned limits for local atomic admission, independently of usage."""
        payload = _mapping(self.get_entitlements(user))
        values = _mapping(payload.get("entitlements"))
        policy = _mapping(values.get("storage_policy"))
        if values.get("can_access") is not True:
            raise PermissionDenied("This storage service is not enabled for the account.")
        if not policy or not isinstance(policy.get("revision"), str):
            raise ValueError("DeployCenter did not return an applicable storage policy.")
        version = policy.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("DeployCenter did not return an ordered policy version.")
        result = {
            "revision": policy["revision"],
            "version": version,
            "resources": policy.get("resources", []),
        }
        for scope in ("account", "organization"):
            source = _mapping(policy.get(scope))
            if "limit_bytes" not in source or not isinstance(source.get("growth_blocked"), bool):
                raise ValueError("DeployCenter returned an invalid storage policy.")
            limit = source["limit_bytes"]
            if limit is not None and (
                isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 2**53 - 1
            ):
                raise ValueError("DeployCenter returned an invalid byte limit.")
            result[scope] = {"limit_bytes": limit, "growth_blocked": source["growth_blocked"]}
        return result

    def get_context(self, user):
        """Get context for a user."""
        attributes_whitelist = ["organization", "operator", "potentialOperators"]
        entitlements = _mapping(self.get_entitlements(user))
        context = {}
        for attribute in attributes_whitelist:
            context[attribute] = entitlements.get(attribute)
        return context

    def can_upload(self, user):
        """Check if a user can upload a file."""
        entitlements = _mapping(self.get_entitlements(user))
        values = _mapping(entitlements.get("entitlements"))
        result = values.get("can_upload", False)
        reason = values.get("can_upload_reason")
        resolve_level = values.get("can_upload_resolve_level")

        actual_reason = normalize_public_entitlement_code(reason)
        if not actual_reason and result is not True:
            if resolve_level == "user":
                actual_reason = CanUploadReason.USER_QUOTA_EXCEEDED
            elif resolve_level == "user_override":
                actual_reason = CanUploadReason.USER_OVERRIDE_QUOTA_EXCEEDED
            elif resolve_level == "organization":
                actual_reason = CanUploadReason.ORGANIZATION_QUOTA_EXCEEDED

        return EntitlementDecision(
            allowed=result is True,
            reason=actual_reason,
            code=actual_reason,
            expose_reason=True,
        )

    def can_access(self, user):
        """Check if a user can access the app."""
        entitlements = _mapping(self.get_entitlements(user))
        values = _mapping(entitlements.get("entitlements"))
        return EntitlementDecision(allowed=values.get("can_access", False) is True)

    def get_quota(self, user):
        """Get quota for a user."""
        if not user.is_authenticated:
            return {}

        entitlements = _mapping(self.get_entitlements(user))
        values = _mapping(entitlements.get("entitlements"))
        can_upload = values.get("can_upload", False)
        can_upload_resolve_level = values.get("can_upload_resolve_level", False)
        can_upload_reason = normalize_public_entitlement_code(values.get("can_upload_reason"))

        # Means that the service is not enabled in the user's organization or
        # the user does not have organization.
        # Do not render the gauge.
        if not can_upload and can_upload_reason in [
            CanUploadReason.NO_ORGANIZATION,
            CanUploadReason.NOT_ACTIVATED,
        ]:
            return {}

        # Means that the user's organization has reached the quota.
        if not can_upload and can_upload_resolve_level == "organization":
            return {
                "state": QuotaState.EXCEEDED_LOCKED,
                "reason": QuotaReason.ORGANIZATION_QUOTA_EXCEEDED,
            }

        metric_account = _mapping(_mapping(entitlements.get("metrics")).get("account"))
        max_storage_account = _non_negative_int(
            values.get("max_storage_account_override", values.get("max_storage_account"))
        )
        storage_used = _non_negative_int(metric_account.get("storage_used"))

        if storage_used is None:
            return {
                "state": QuotaState.ERROR,
                "error": QuotaError.METRIC_ACCOUNT_NOT_FOUND,
            }

        if max_storage_account is None:
            return {
                "state": QuotaState.ERROR,
                "error": QuotaError.MAX_STORAGE_ACCOUNT_NOT_FOUND,
            }

        return {
            "state": QuotaState.DEFAULT,
            "usage": storage_used,
            "limit": max_storage_account,
        }
