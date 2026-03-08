"""E2E-only authentication helpers.

This module is intentionally scoped to the `e2e` app to avoid keeping unused
authentication backends in the core app.
"""

from django.conf import settings
from django.contrib.auth.models import AnonymousUser

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed


class ServerToServerAuthentication(BaseAuthentication):
    """Authenticate requests using a server-to-server bearer token.

    Tokens are configured via `SERVER_TO_SERVER_API_TOKENS`.
    """

    def authenticate(self, request):
        tokens = list(getattr(settings, "SERVER_TO_SERVER_API_TOKENS", []) or [])
        if not tokens:
            raise AuthenticationFailed("Server-to-server auth is not configured.")

        raw = get_authorization_header(request).decode("utf-8").strip()
        if not raw.startswith("Bearer "):
            raise AuthenticationFailed("Missing bearer token.")

        token = raw.removeprefix("Bearer ").strip()
        if token not in tokens:
            raise AuthenticationFailed("Invalid bearer token.")

        return AnonymousUser(), token

    def authenticate_header(self, request):
        # Returning a value here ensures DRF returns 401 (not 403) on auth failure.
        return "Bearer"
