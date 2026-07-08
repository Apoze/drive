"""Entitlements backend utilities."""

from core.entitlements.backends.base import (
    EntitlementDecision,
    normalize_entitlement_decision,
)
from core.entitlements.factory import get_entitlements_backend


class EntitlementsUnavailableError(Exception):
    """Raised when the entitlements service is unavailable."""


__all__ = [
    "EntitlementDecision",
    "EntitlementsUnavailableError",
    "get_entitlements_backend",
    "normalize_entitlement_decision",
]
