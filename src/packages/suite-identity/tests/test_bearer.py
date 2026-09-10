"""Use real signed tokens to distinguish API authentication from browser nonce checks."""

import time

from django.core.exceptions import SuspiciousOperation

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from suite_identity.oidc import IdentityBackendMixin


def test_bearer_keeps_signature_and_audience_checks_without_browser_nonce(settings):
    """API verification cannot disable nonce checking in a subsequent browser login."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings.OIDC_RP_IDP_SIGN_KEY = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    settings.OIDC_RP_SIGN_ALGO = "RS256"
    settings.OIDC_RP_CLIENT_ID = "suite-docs"
    settings.OIDC_RP_CLIENT_SECRET = "unused-by-rsa-qualification"
    settings.OIDC_USE_NONCE = True
    settings.SUITE_OIDC_ISSUER = "https://identity.invalid"
    for name in (
        "OIDC_OP_AUTHORIZATION_ENDPOINT",
        "OIDC_OP_TOKEN_ENDPOINT",
        "OIDC_OP_USER_ENDPOINT",
    ):
        setattr(settings, name, "https://identity.invalid/unused")

    class Backend(IdentityBackendMixin, OIDCAuthenticationBackend):
        pass

    backend = Backend()
    now = int(time.time())
    payload = {
        "iss": settings.SUITE_OIDC_ISSUER,
        "sub": "opaque/person",
        "aud": "suite-docs",
        "iat": now,
        "auth_time": now,
        "exp": now + 60,
        "nonce": "browser-transaction",
        "scope": "openid profile",
    }
    token = jwt.encode(payload, key, algorithm="RS256")
    assert backend.verify_access_token(token)["sub"] == "opaque/person"
    with pytest.raises(SuspiciousOperation):
        backend.verify_token(token, nonce="wrong-browser-transaction")
    assert backend.verify_token(token, nonce="browser-transaction")["sub"] == "opaque/person"
    wrong_audience = jwt.encode(payload | {"aud": "other-app"}, key, algorithm="RS256")
    with pytest.raises(SuspiciousOperation):
        backend.verify_access_token(wrong_audience)
    without_scope = jwt.encode(
        {k: v for k, v in payload.items() if k != "scope"}, key, algorithm="RS256"
    )
    with pytest.raises(SuspiciousOperation):
        backend.verify_access_token(without_scope)
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(SuspiciousOperation):
        backend.verify_access_token(jwt.encode(payload, wrong_key, algorithm="RS256"))
