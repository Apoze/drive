"""Resolve API identities with the same verified issuer and durable association."""

from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation

from mozilla_django_oidc.contrib.drf import OIDCAuthentication
from requests.exceptions import RequestException
from rest_framework.exceptions import APIException, AuthenticationFailed

from .access import DirectoryUnavailable, enabled, remember_proof, require_access
from .login import AuthenticationRequired
from .models import IdentityBinding
from .oidc import validate_claims, verified_email


class IdentityUnavailable(APIException):
    status_code = 503
    default_detail = "Access verification temporarily unavailable"
    default_code = "suite_directory_unavailable"


def resolve_api_identity(payload, client_id):
    try:
        validate_claims(
            payload,
            issuer=settings.SUITE_OIDC_ISSUER,
            client_id=client_id,
            max_age=settings.SUITE_IDENTITY_AUTH_MAX_AGE,
        )
    except (SuspiciousOperation, AuthenticationRequired):
        raise AuthenticationFailed("Invalid authentication credentials") from None
    try:
        identity = IdentityBinding.objects.select_related("user").get(
            issuer=payload["iss"], subject=payload["sub"], enabled=True
        )
    except IdentityBinding.DoesNotExist:
        raise AuthenticationFailed("Identity is not associated") from None
    try:
        account = require_access(identity.user)
    except DirectoryUnavailable:
        raise IdentityUnavailable() from None
    except PermissionDenied:
        raise AuthenticationFailed("Access is not assigned") from None
    if account.auth_not_before and payload["auth_time"] <= account.auth_not_before.timestamp():
        raise AuthenticationFailed("A new authentication is required")
    remember_proof(
        identity.user,
        {
            "principal_id": str(account.principal_id),
            "session_version": account.session_version,
            "issuer": payload["iss"],
            "verified_email": verified_email(payload),
            "auth_until": min(
                payload["exp"],
                payload["auth_time"] + settings.SUITE_IDENTITY_AUTH_MAX_AGE,
            ),
        },
    )
    return identity.user


class BearerAuthentication(OIDCAuthentication):
    """Signed bearer flow; opaque access tokens use the configured resource server."""

    def authenticate(self, request):
        if not enabled():
            return super().authenticate(request)
        token = self.get_access_token(request)
        if not token:
            return None
        try:
            payload = self.backend.verify_access_token(token)
            user = resolve_api_identity(payload, settings.OIDC_RP_CLIENT_ID)
        except (SuspiciousOperation, AuthenticationRequired, ValueError):
            raise AuthenticationFailed("Invalid authentication credentials") from None
        except RequestException:
            raise IdentityUnavailable() from None
        return user, token
