"""Keep native introspection/scopes; replace legacy subject-only user lookup."""

from django.conf import settings
from django.core.exceptions import SuspiciousOperation

from lasuite.oidc_resource_server.backend import ResourceServerBackend
from requests.exceptions import RequestException
from rest_framework.exceptions import AuthenticationFailed

from .access import enabled
from .api_authentication import IdentityUnavailable, resolve_api_identity


class SuiteResourceServerBackend(ResourceServerBackend):
    """Preserve native scope checks and normalize safe API failure responses."""

    def get_user_info_with_introspection(self, access_token):
        """Do not expose authorization-server response bodies in API errors."""
        try:
            return super().get_user_info_with_introspection(access_token)
        except SuspiciousOperation:
            raise AuthenticationFailed("Invalid authentication credentials") from None
        except RequestException:
            raise IdentityUnavailable() from None

    def get_user(self, access_token, id_token, payload):
        if not enabled():
            return super().get_user(access_token, id_token, payload)
        if payload.get("active") is not True:
            raise SuspiciousOperation("Inactive resource server token")
        return resolve_api_identity(payload, settings.OIDC_RS_CLIENT_ID)
