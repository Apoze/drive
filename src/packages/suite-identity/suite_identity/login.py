"""OIDC recovery keeps the native signed flow and never guesses an account."""

from urllib.parse import urlencode

from django.conf import settings

from .access import enabled
from .http import read_credential, read_json


class AuthenticationRequired(Exception):
    """The verified authentication is older than the current revocation epoch."""


class AssociationPending(Exception):
    """A verified external login still needs an explicit People association."""


class IdentityServiceUnavailable(Exception):
    """A temporary outage must survive Django's generic permission-denied handling."""


class AccessNotAssigned(Exception):
    """A verified, associated person has no access to this application."""


class SuiteAuthenticationRequestMixin:
    """Use standard max_age and prompt, including providers without logout."""

    def get_extra_params(self, request):
        """A deliberate retry can force authentication without breaking normal SSO."""
        params = dict(super().get_extra_params(request) or {})
        if enabled():
            params["max_age"] = settings.SUITE_IDENTITY_AUTH_MAX_AGE
            if request.GET.get("reauthenticate") == "1":
                request.session.pop("silent", None)
                params.update(prompt="login", max_age=0)
        return params


def record_association_request(payload):
    """Only called after signature, issuer, audience, nonce and UserInfo checks."""
    token = read_credential(settings.SUITE_LOGOUT_TOKEN_FILE)
    result = read_json(
        settings.SUITE_IDENTITY_REQUEST_URL,
        data=urlencode({"issuer": payload["iss"], "subject": payload["sub"]}).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        limit=4096,
    )
    if not isinstance(result, dict) or result.get("status") != "pending":
        raise ValueError("Association request was not recorded")
