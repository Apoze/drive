"""Direct contract tests for resource-server permission gating."""

from __future__ import annotations

from types import SimpleNamespace

from django.test import override_settings

import pytest
from rest_framework.exceptions import NotAuthenticated

from core.external_api.permissions import ResourceServerClientPermission


class _FakeResourceServerAuthentication:
    pass


def _request(
    *,
    authenticator=None,
    is_authenticated=True,
    audience="allowed-client",
):
    return SimpleNamespace(
        successful_authenticator=authenticator,
        user=SimpleNamespace(is_authenticated=is_authenticated),
        resource_server_token_audience=audience,
    )


def _view(*, action="list", resource_server_actions=None):
    payload = {"action": action}
    if resource_server_actions is not None:
        payload["resource_server_actions"] = resource_server_actions
    return SimpleNamespace(**payload)


def test_resource_server_permission_rejects_wrong_authenticator(monkeypatch):
    """Only resource-server authenticators are accepted."""

    monkeypatch.setattr(
        "core.external_api.permissions.ResourceServerAuthentication",
        _FakeResourceServerAuthentication,
    )
    permission = ResourceServerClientPermission()
    request = _request(authenticator=object())

    with pytest.raises(NotAuthenticated):
        permission.has_permission(request, _view())


def test_resource_server_permission_rejects_unauthenticated_user(monkeypatch):
    """Authenticated resource-server requests still require an authenticated user."""

    monkeypatch.setattr(
        "core.external_api.permissions.ResourceServerAuthentication",
        _FakeResourceServerAuthentication,
    )
    permission = ResourceServerClientPermission()
    request = _request(
        authenticator=_FakeResourceServerAuthentication(),
        is_authenticated=False,
    )

    with pytest.raises(NotAuthenticated):
        permission.has_permission(request, _view())


def test_resource_server_permission_rejects_action_outside_allowlist(monkeypatch):
    """Actions outside the configured per-resource allowlist are denied."""

    monkeypatch.setattr(
        "core.external_api.permissions.ResourceServerAuthentication",
        _FakeResourceServerAuthentication,
    )
    permission = ResourceServerClientPermission()
    request = _request(authenticator=_FakeResourceServerAuthentication())

    allowed = permission.has_permission(
        request,
        _view(action="destroy", resource_server_actions=["list", "retrieve"]),
    )

    assert allowed is False


@override_settings(OIDC_RS_ALLOWED_AUDIENCES=["allowed-client"])
def test_resource_server_permission_accepts_allowlisted_audience(monkeypatch):
    """Allowlisted audiences are accepted once auth and action gates pass."""

    monkeypatch.setattr(
        "core.external_api.permissions.ResourceServerAuthentication",
        _FakeResourceServerAuthentication,
    )
    permission = ResourceServerClientPermission()
    request = _request(authenticator=_FakeResourceServerAuthentication())

    allowed = permission.has_permission(
        request,
        _view(action="list", resource_server_actions=["list"]),
    )

    assert allowed is True


@override_settings(OIDC_RS_ALLOWED_AUDIENCES=["allowed-client"])
def test_resource_server_permission_rejects_non_allowlisted_audience(monkeypatch):
    """Audiences outside the settings allowlist are denied deterministically."""

    monkeypatch.setattr(
        "core.external_api.permissions.ResourceServerAuthentication",
        _FakeResourceServerAuthentication,
    )
    permission = ResourceServerClientPermission()
    request = _request(
        authenticator=_FakeResourceServerAuthentication(),
        audience="forbidden-client",
    )

    allowed = permission.has_permission(
        request,
        _view(action="list", resource_server_actions=["list"]),
    )

    assert allowed is False
