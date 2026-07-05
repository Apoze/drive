"""Direct contract tests for resource-server authentication wrappers."""

from __future__ import annotations

from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated

from core.external_api.authentication import (
    DriveResourceServerAuthentication,
    UpstreamResourceServerAuthentication,
)


def test_drive_resource_server_authentication_sanitizes_not_authenticated(monkeypatch):
    """Missing-credentials errors are rewritten to a stable generic message."""

    def raise_not_authenticated(self, request):
        raise NotAuthenticated("upstream token details should not leak")

    monkeypatch.setattr(
        UpstreamResourceServerAuthentication,
        "authenticate",
        raise_not_authenticated,
    )

    auth = DriveResourceServerAuthentication()

    try:
        auth.authenticate(object())
    except NotAuthenticated as err:
        assert str(err.detail) == "Authentication credentials were not provided."
        assert "upstream token details" not in str(err.detail)
    else:
        raise AssertionError("NotAuthenticated was not raised")


def test_drive_resource_server_authentication_sanitizes_authentication_failed(monkeypatch):
    """Authentication failures are rewritten to a stable generic message."""

    def raise_authentication_failed(self, request):
        raise AuthenticationFailed("upstream introspection failure details should not leak")

    monkeypatch.setattr(
        UpstreamResourceServerAuthentication,
        "authenticate",
        raise_authentication_failed,
    )

    auth = DriveResourceServerAuthentication()

    try:
        auth.authenticate(object())
    except AuthenticationFailed as err:
        assert str(err.detail) == "Invalid authentication credentials."
        assert "upstream introspection failure" not in str(err.detail)
    else:
        raise AssertionError("AuthenticationFailed was not raised")
