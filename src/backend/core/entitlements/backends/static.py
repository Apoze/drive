"""Static Entitlements Backend."""

from core.entitlements.backends.base import EntitlementsBackend, normalize_entitlement_decision


class StaticEntitlementsBackend(EntitlementsBackend):
    """Entitlements backend that returns the static values passed to its constructor."""

    def __init__(self, entitlements=None):
        self.entitlements = entitlements or {
            "can_upload": {"result": True},
            "can_access": {"result": True},
        }

    def can_access(self, user):
        return normalize_entitlement_decision(self.entitlements["can_access"])

    def can_upload(self, user):
        return normalize_entitlement_decision(self.entitlements["can_upload"])
