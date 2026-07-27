"""DeployCenter Entitlements Backend."""

import logging
from collections.abc import Mapping

from django.core.cache import cache

import requests

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
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


class DeployCenterEntitlementsBackend(EntitlementsBackend):
    """Entitlements backend that checks permissions via a DeployCenter service."""

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(  # noqa: PLR0913
        self,
        base_url,
        service_id,
        api_key,
        cache_timeout=10,
        oidc_claims=None,
        organization_claim="siret",
    ):
        self.base_url = base_url
        self.service_id = service_id
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
        if organization_value is None:
            return [user_entry]
        user_entry[self.organization_claim] = organization_value
        organization_users = User.objects.filter(
            is_active=True, **{f"claims__{self.organization_claim}": organization_value}
        )
        organization_entry = OrganizationUsageMetricSerializer(
            {
                "account_id_key": self.organization_claim,
                "account_id_value": organization_value,
                "users": organization_users,
            }
        ).data
        return [user_entry, organization_entry]

    def fetch_entitlements(self, user):
        """Fetch entitlements for a user from the DeployCenter service."""
        params = {
            "account_type": "user",
            "account_email": user.email,
            "service_id": self.service_id,
        }
        for claim in self.oidc_claims:
            value = user.claims.get(claim)
            if value is not None:
                params[claim] = value

        response = requests.post(
            self.base_url,
            params=params,
            json={"usage_metrics": self.build_usage_metrics(user)},
            headers={"X-Service-Auth": f"Bearer {self.api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

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
        return EntitlementDecision(
            allowed=values.get("can_access", False) is True
        )

    def get_quota(self, user):
        """Get quota for a user."""
        if not user.is_authenticated:
            return {}

        entitlements = _mapping(self.get_entitlements(user))
        values = _mapping(entitlements.get("entitlements"))
        can_upload = values.get("can_upload", False)
        can_upload_resolve_level = values.get("can_upload_resolve_level", False)
        can_upload_reason = normalize_public_entitlement_code(
            values.get("can_upload_reason")
        )

        # Means that the service is not enabled in the user's organization or
        # the user does not have organization.
        # Do not render the gauge.
        if not can_upload and can_upload_reason in [
            CanUploadReason.NO_ORGANIZATION,
            CanUploadReason.NOT_ACTIVATED,
        ]:
            return {}

        max_storage_organization = values.get("max_storage_organization", {})
        # Means that the user's organization has reached the quota.
        if (
            not can_upload
            and max_storage_organization
            and can_upload_resolve_level == "organization"
        ):
            return {
                "state": QuotaState.EXCEEDED_LOCKED,
                "reason": QuotaReason.ORGANIZATION_QUOTA_EXCEEDED,
            }

        metric_account = _mapping(_mapping(entitlements.get("metrics")).get("account"))
        max_storage_account = _non_negative_int(values.get("max_storage_account"))
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
