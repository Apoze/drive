"""Direct contract tests for conditional core URL routing."""

from __future__ import annotations

from django.test import override_settings
from django.urls import Resolver404, resolve

from core.tests.utils.urls import reload_urls


def _path_exists(path: str) -> bool:
    try:
        resolve(path)
    except Resolver404:
        return False
    return True


def test_core_urls_keep_main_api_routes_available():
    """Core API and config routes remain present regardless of external settings."""

    reload_urls()

    assert _path_exists("/api/v1.0/items/") is True
    assert _path_exists("/api/v1.0/config/") is True


@override_settings(OIDC_RESOURCE_SERVER_ENABLED=False, METRICS_ENABLED=False)
def test_core_urls_hide_external_api_and_metrics_when_disabled():
    """External API and metrics routes stay absent when the features are disabled."""

    reload_urls()

    assert _path_exists("/external_api/v1.0/items/") is False
    assert _path_exists("/external_api/v1.0/metrics/usage/") is False

    reload_urls()


@override_settings(
    OIDC_RESOURCE_SERVER_ENABLED=True,
    EXTERNAL_API={
        "items": {"enabled": False, "actions": []},
        "item_access": {"enabled": True, "actions": ["list"]},
        "item_invitation": {"enabled": True, "actions": ["list"]},
        "users": {"enabled": True, "actions": ["get_me"]},
    },
    METRICS_ENABLED=False,
)
def test_core_urls_expose_only_enabled_external_resources():
    """Items and nested routes stay hidden until the parent `items` resource is enabled."""

    reload_urls()

    assert _path_exists("/external_api/v1.0/users/me/") is True
    assert _path_exists("/external_api/v1.0/items/") is False
    assert _path_exists("/external_api/v1.0/items/abc/accesses/") is False
    assert _path_exists("/external_api/v1.0/items/abc/invitations/") is False

    reload_urls()


@override_settings(
    OIDC_RESOURCE_SERVER_ENABLED=True,
    EXTERNAL_API={
        "items": {"enabled": True, "actions": ["list"]},
        "item_access": {"enabled": True, "actions": ["list"]},
        "item_invitation": {"enabled": True, "actions": ["list"]},
        "users": {"enabled": True, "actions": ["get_me"]},
    },
    METRICS_ENABLED=True,
)
def test_core_urls_expose_nested_external_items_and_metrics_when_enabled():
    """Items nested routes and metrics appear only when their gates are enabled."""

    reload_urls()

    assert _path_exists("/external_api/v1.0/items/") is True
    assert _path_exists("/external_api/v1.0/items/abc/accesses/") is True
    assert _path_exists("/external_api/v1.0/items/abc/invitations/") is True
    assert _path_exists("/external_api/v1.0/metrics/usage/") is True

    reload_urls()
