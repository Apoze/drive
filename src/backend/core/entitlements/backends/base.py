"""Entitlements Backend base class."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
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
    ``message`` fields stay public messages; DeployCenter-style ``reason`` fields
    are also available as the normalized public message for enforcement callers.
    """
    if isinstance(decision, EntitlementDecision):
        return decision

    if not isinstance(decision, Mapping):
        return EntitlementDecision(allowed=False)

    message = _string_or_none(decision.get("message"))
    reason = _string_or_none(decision.get("reason"))
    code = _string_or_none(decision.get("code"))

    return EntitlementDecision(
        allowed=decision.get("result") is True,
        public_message=message or reason,
        reason=reason,
        code=code,
        expose_public_message="message" in decision,
        expose_reason="reason" in decision,
        expose_code="code" in decision,
    )


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
