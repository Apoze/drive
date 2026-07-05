"""Direct contract tests for the SDK relay support service."""
# pylint: disable=protected-access

from __future__ import annotations

from django.core.cache import cache

from core.services.sdk_relay import SDKRelayManager


def test_sdk_relay_manager_builds_stable_cache_keys():
    """SDK relay cache keys follow the public service contract."""

    manager = SDKRelayManager()

    assert manager._get_cache_key("abc123") == "sdk_relay:abc123"


def test_sdk_relay_manager_registers_gets_and_deletes_events(settings):
    """Events are stored, returned once, then deleted after the read."""

    settings.SDK_RELAY_CACHE_TIMEOUT = 123
    cache.clear()
    manager = SDKRelayManager()
    event = {"type": "picked", "payload": {"id": "42"}}

    manager.register_event("token-1", event)

    assert manager.get_event("token-1") == event
    assert manager.get_event("token-1") == {}


def test_sdk_relay_manager_returns_empty_payload_when_event_is_missing():
    """Missing relay entries return the stable empty payload."""

    cache.clear()
    manager = SDKRelayManager()

    assert manager.get_event("missing-token") == {}
