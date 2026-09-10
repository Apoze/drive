"""Reuse the applications' signed OIDC flow with strict, durable account lookup."""

import math
import time

from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db import transaction

from .access import DirectoryUnavailable, enabled, require_access
from .login import (
    AccessNotAssigned,
    AssociationPending,
    AuthenticationRequired,
    IdentityServiceUnavailable,
    record_association_request,
)
from .models import IdentityBinding


def verified_email(claims):
    """Only an IdP-verified address can identify an invitation recipient."""
    email = claims.get("email")
    return (
        email.casefold()
        if claims.get("email_verified") is True
        and isinstance(email, str)
        and 0 < len(email) <= 254
        else ""
    )


def validate_claims(payload, *, issuer, client_id, max_age, now=None):
    """Validate registered issuer/audience and times after signature verification."""
    now = time.time() if now is None else now
    if not isinstance(payload, dict) or payload.get("iss") != issuer:
        raise SuspiciousOperation("Invalid identity issuer")
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject or len(subject) > 255:
        raise SuspiciousOperation("Invalid identity subject")
    audience = payload.get("aud")
    audience = [audience] if isinstance(audience, str) else audience
    if (
        not isinstance(audience, list)
        or not all(isinstance(value, str) and value for value in audience)
        or client_id not in audience
    ):
        raise SuspiciousOperation("Invalid identity audience")
    if (len(audience) > 1 or "azp" in payload) and payload.get("azp") != client_id:
        raise SuspiciousOperation("Invalid authorized party")
    for name in ("exp", "iat", "auth_time"):
        value = payload.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise SuspiciousOperation("Missing or invalid identity timestamp")
    if payload["exp"] <= now or payload["iat"] > now + 5:
        raise SuspiciousOperation("Expired or future identity token")
    if "nbf" in payload:
        value = payload["nbf"]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value > now + 5
        ):
            raise SuspiciousOperation("Identity token not yet valid")
    if payload["auth_time"] > now + 5 or now - payload["auth_time"] > max_age:
        raise AuthenticationRequired("A new authentication is required")


class IdentityBackendMixin:
    """Shared by Drive, ST, People and Docs; no provider-specific business logic."""

    def get_settings(self, attribute, *args):
        """Keep API verification local to this backend instance, never global settings."""
        if enabled() and attribute == "OIDC_ALLOW_UNSECURED_JWT":
            return False
        if attribute == "OIDC_USE_NONCE" and getattr(self, "suite_verifying_access_token", False):
            # A bearer request has no browser authorization transaction nonce.
            return False
        return super().get_settings(attribute, *args)

    def verify_access_token(self, token):
        """Verify signature and claims without borrowing an ID-token nonce context."""
        self.suite_verifying_access_token = True
        try:
            payload = self.verify_token(token, nonce=None)
        finally:
            self.suite_verifying_access_token = False
        if not isinstance(payload.get("scope"), str) or not payload["scope"].strip():
            raise SuspiciousOperation("An OAuth access token with scopes is required")
        return payload

    def verify_token(self, token, **kwargs):
        """The existing library verifies signature and nonce before strict claims."""
        payload = super().verify_token(token, **kwargs)
        if enabled() and not getattr(self, "_suite_userinfo", False):
            validate_claims(
                payload,
                issuer=settings.SUITE_OIDC_ISSUER,
                client_id=self.OIDC_RP_CLIENT_ID,
                max_age=settings.SUITE_IDENTITY_AUTH_MAX_AGE,
            )
        return payload

    def get_or_create_user(self, access_token, id_token, payload):
        """Mapped identities only; changing an email never merges accounts."""
        if not enabled():
            return super().get_or_create_user(access_token, id_token, payload)
        validate_claims(
            payload,
            issuer=settings.SUITE_OIDC_ISSUER,
            client_id=self.OIDC_RP_CLIENT_ID,
            max_age=settings.SUITE_IDENTITY_AUTH_MAX_AGE,
        )
        self._suite_userinfo = True
        try:
            user_info = self.get_userinfo(access_token, id_token, payload)
        finally:
            self._suite_userinfo = False
        if not isinstance(user_info, dict) or user_info.get("sub") != payload["sub"]:
            raise SuspiciousOperation("UserInfo identity does not match the ID token")
        with transaction.atomic():
            try:
                identity = IdentityBinding.objects.select_related("user").get(
                    issuer=payload["iss"],
                    subject=payload["sub"],
                    enabled=True,
                )
            except IdentityBinding.DoesNotExist as exc:
                try:
                    record_association_request(payload)
                except (OSError, ValueError) as failure:
                    raise IdentityServiceUnavailable() from failure
                raise AssociationPending() from exc
            user = identity.user
            try:
                account = require_access(user)
            except DirectoryUnavailable as exc:
                raise IdentityServiceUnavailable() from exc
            except PermissionDenied as exc:
                raise AccessNotAssigned() from exc
            if (
                account.auth_not_before
                and payload["auth_time"] <= account.auth_not_before.timestamp()
            ):
                raise AuthenticationRequired("Authentication predates session revocation")
            # Profile attributes carry no membership, organization or admin privileges.
            updates = {}
            if isinstance(user_info.get("email"), str) and len(user_info["email"]) <= 254:
                updates["email"] = user_info["email"]
            name = user_info.get("name")
            if isinstance(name, str):
                field = "full_name" if hasattr(user, "full_name") else "name"
                updates[field] = name[:100]
            if updates and self.suite_profile_updates_allowed(user):
                type(user).objects.filter(pk=user.pk).update(**updates)
                for field, value in updates.items():
                    setattr(user, field, value)
        self.request.suite_authenticated = {
            "principal_id": str(account.principal_id),
            "session_version": account.session_version,
            "auth_until": payload["auth_time"] + settings.SUITE_IDENTITY_AUTH_MAX_AGE,
            "issuer": payload["iss"],
            "verified_email": verified_email(user_info),
        }
        return user

    def raise_token_response_error(self, response):
        """Token endpoint bodies may contain credentials; never put them in errors."""
        if enabled() and response.status_code != 200:
            raise SuspiciousOperation("Identity provider token exchange failed")
        return super().raise_token_response_error(response)

    def suite_profile_updates_allowed(self, user):
        """Applications with externally governed profiles can retain their authority."""
        return True
