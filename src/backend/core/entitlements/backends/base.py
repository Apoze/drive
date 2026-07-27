"""Entitlements Backend base class."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


@dataclass(frozen=True)
class EntitlementDecision:
    """Structured entitlement decision used by backend enforcement paths."""

    allowed: bool
    public_message: str | None = None
    reason: str | None = None
    code: str | None = None
    expose_public_message: bool = False
    expose_reason: bool = False
    expose_code: bool = False

    @property
    def result(self) -> bool:
        """Compatibility alias for the public entitlement payload field."""
        return self.allowed

    def public_message_or(self, default: str) -> str:
        """Return the normalized public denial message or a caller-specific default."""
        return self.public_message or default

    def to_public_dict(self) -> dict[str, Any]:
        """Serialize to the existing public /entitlements/ response shape."""
        payload: dict[str, Any] = {"result": self.allowed}
        if self.expose_public_message and self.public_message is not None:
            payload["message"] = self.public_message
        if self.expose_reason:
            payload["reason"] = self.reason
        if self.expose_code:
            payload["code"] = self.code
        return payload


def _string_or_none(value: Any) -> str | None:
    """Return user-facing text only when the provider gave an explicit string."""
    return value if isinstance(value, str) else None


def normalize_entitlement_decision(decision: object) -> EntitlementDecision:
    """
    Normalize legacy entitlement backend outputs into a structured decision.

    Missing, malformed, or non-boolean ``result`` values fail closed. Existing
    Trusted ``message`` fields stay public messages. Provider reasons and codes
    are exposed only when they match the stable public allowlist.
    """
    if isinstance(decision, EntitlementDecision):
        return decision

    if not isinstance(decision, Mapping):
        return EntitlementDecision(allowed=False)

    message = _string_or_none(decision.get("message"))
    reason = normalize_public_entitlement_code(decision.get("reason"))
    code = normalize_public_entitlement_code(decision.get("code")) or reason

    return EntitlementDecision(
        allowed=decision.get("result") is True,
        public_message=message,
        reason=reason,
        code=code,
        expose_public_message="message" in decision,
        expose_reason="reason" in decision and reason is not None,
        expose_code="code" in decision and code is not None,
    )


class QuotaState(StrEnum):
    """State of a quota gauge returned by get_quota."""

    DEFAULT = "default"
    EXCEEDED_LOCKED = "exceeded_locked"
    ERROR = "error"


class QuotaReason(StrEnum):
    """Reasons explaining why the quota gauge is locked (get_quota output)."""

    ORGANIZATION_QUOTA_EXCEEDED = "organization_quota_exceeded"


class CanUploadReason(StrEnum):
    """Reasons explaining why a user cannot upload (can_upload output)."""

    NO_ORGANIZATION = "no_organization"
    NOT_ACTIVATED = "not_activated"
    USER_QUOTA_EXCEEDED = "user_quota_exceeded"
    USER_OVERRIDE_QUOTA_EXCEEDED = "user_override_quota_exceeded"
    ORGANIZATION_QUOTA_EXCEEDED = "organization_quota_exceeded"


class QuotaError(StrEnum):
    """Errors that can occur while computing a quota."""

    METRIC_ACCOUNT_NOT_FOUND = "metric_account_not_found"
    MAX_STORAGE_ACCOUNT_NOT_FOUND = "max_storage_account_not_found"


PUBLIC_ENTITLEMENT_CODES = frozenset(reason.value for reason in CanUploadReason)


def normalize_public_entitlement_code(value: object) -> str | None:
    """Return a stable public entitlement code, never arbitrary provider text."""
    return value if isinstance(value, str) and value in PUBLIC_ENTITLEMENT_CODES else None


class EntitlementsBackend(ABC):
    """Abstract base class for entitlements backends."""

    @abstractmethod
    def can_access(self, user):
        """
        Check if a user can access app.
        """

    @abstractmethod
    def can_upload(self, user):
        """
        Check if a user can upload a file.
        """

    def get_context(self, user):  # pylint: disable=unused-argument
        """Get context for a user."""
        return {}

    def get_quota(self, user):  # pylint: disable=unused-argument
        """Get quota for a user."""
        return {}

    def invalidate_cache(self, user_ids):  # noqa: B027
        """Invalidate any cached entitlements for these users. No-op by default."""
