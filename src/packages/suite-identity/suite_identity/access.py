"""Bounded access decisions for HTTP requests, editors and background jobs."""

import math
import time
from contextvars import ContextVar
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from rest_framework.exceptions import APIException

from .models import Account

request_accounts = ContextVar("suite_request_accounts", default=None)
request_proofs = ContextVar("suite_request_proofs", default=None)


class DirectoryUnavailable(APIException, PermissionDenied):
    """An expired positive decision cannot be used during a directory outage."""

    status_code = 503
    default_code = "suite_directory_unavailable"


def enabled():
    """Existing applications remain unchanged until migration is activated."""
    return getattr(settings, "SUITE_IDENTITY_ENABLED", False)


def require_access(user, *, policy=True):
    """Read current state, including for a long-lived worker's stale User object."""
    if not enabled():
        return None
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required")
    cache = request_accounts.get()
    account = cache.get(user.pk) if cache is not None else None
    if account is None:
        try:
            account = Account.objects.select_related("user").get(user_id=user.pk)
        except Account.DoesNotExist as exc:
            raise PermissionDenied("Account is not associated with the suite") from exc
        # Long-lived workers may carry a User with cached groups from an older operation.
        user.__dict__.pop("teams", None)
        if cache is not None:
            cache[user.pk] = account
    if not account.active or not account.user.is_active:
        raise PermissionDenied("Account is suspended")
    deadline = timezone.now() - timedelta(seconds=settings.SUITE_IDENTITY_MAX_STALE_SECONDS)
    if account.checked_at is None or account.checked_at < deadline:
        raise DirectoryUnavailable("Access verification temporarily unavailable")
    if policy:
        if account.policy_checked_at is None or account.policy_checked_at < deadline:
            raise DirectoryUnavailable("Application access verification temporarily unavailable")
        if not account.policy_allowed:
            raise PermissionDenied("Application access is not assigned")
    return account


def principal_id(user):
    """Use stable IDs in policy exchanges without changing legacy installations."""
    if not enabled():
        return user.sub
    return str(Account.objects.only("principal_id").get(user_id=user.pk).principal_id)


def private_url_ttl(user, requested):
    """Do not add a signed URL's lifetime to the remaining authorization lease."""
    account = require_access(user)
    if account is None:
        return requested
    verified_at = min(account.checked_at, account.policy_checked_at)
    remaining = (
        verified_at + timedelta(seconds=settings.SUITE_IDENTITY_MAX_STALE_SECONDS) - timezone.now()
    ).total_seconds()
    proof = (request_proofs.get() or {}).get(user.pk)
    if proof:
        remaining = min(remaining, proof["auth_until"] - time.time())
    if remaining < 1:
        raise DirectoryUnavailable("Access verification temporarily unavailable")
    return min(requested, int(remaining))


def remember_proof(user, proof):
    """Keep verified HTTP authentication available to delegated editor credentials."""
    proofs = request_proofs.get()
    if proofs is not None:
        proofs[user.pk] = proof


def delegation_proof(user):
    """Bind server-issued credentials to an epoch without extending browser proof."""
    if not enabled() or not user.is_authenticated:
        return None
    account = require_access(user)
    proof = (request_proofs.get() or {}).get(user.pk)
    if proof is not None:
        validate_delegation(user, proof)
        return dict(proof)
    # Internal conversion jobs have no browser session; their permissions are reread.
    return {
        "principal_id": str(account.principal_id),
        "session_version": account.session_version,
        "issuer": settings.SUITE_OIDC_ISSUER,
        "auth_until": time.time() + settings.SUITE_IDENTITY_AUTH_MAX_AGE,
    }


def validate_delegation(user, proof):
    """Reject old editor/stream credentials after revocation or an IdP cutover."""
    if not enabled() or not user.is_authenticated:
        return
    account = require_access(user)
    expiry = proof.get("auth_until") if isinstance(proof, dict) else None
    issuers = [settings.SUITE_OIDC_ISSUER]
    # Only authenticated private peers use delegation; browser sessions still
    # require this application's exact issuer in IdentitySessionMiddleware.
    issuers.extend(getattr(settings, "SUITE_DELEGATION_PEER_ISSUERS", []))
    if getattr(settings, "DOCS_DRIVE_ENABLED", False):
        peer_issuer = getattr(settings, "DOCUMENT_PEER_OIDC_ISSUER", "")
        if peer_issuer:
            # Private document exchanges can carry the peer application's
            # session proof through a round trip. Browser login still requires
            # this application's own issuer, checked by its OIDC backend.
            issuers.append(peer_issuer)
    if (
        isinstance(expiry, bool)
        or not isinstance(expiry, (int, float))
        or not math.isfinite(expiry)
        or expiry <= time.time()
        or proof.get("principal_id") != str(account.principal_id)
        or proof.get("session_version") != account.session_version
        or proof.get("issuer") not in issuers
    ):
        raise PermissionDenied("A new authentication is required")
