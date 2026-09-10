"""Reject an incomplete activation or a configuration exceeding the access contract."""

from urllib.parse import urlsplit
from uuid import UUID

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security)
def check_suite_settings(app_configs, **kwargs):
    """No network calls and no secret values in startup diagnostics."""
    if not settings.SUITE_IDENTITY_ENABLED:
        return []
    errors = []
    for name, maximum in (
        ("SUITE_IDENTITY_MAX_STALE_SECONDS", 90),
        ("SUITE_IDENTITY_AUTH_MAX_AGE", 900),
    ):
        value = getattr(settings, name)
        if type(value) is not int or not 1 <= value <= maximum:
            errors.append(Error(f"{name} must be between 1 and {maximum}.", id="suite.E001"))
    for name in (
        "SUITE_OIDC_ISSUER",
        "SUITE_DIRECTORY_URL",
        "SUITE_POLICY_URL",
        "SUITE_CATALOGUE_URL",
        "SUITE_LOGOUT_URL",
        "SUITE_IDENTITY_REQUEST_URL",
    ):
        try:
            url = urlsplit(getattr(settings, name))
            valid = (
                url.scheme in {"http", "https"}
                and url.hostname
                and not (url.username or url.password or url.query or url.fragment)
            )
        except (TypeError, ValueError):
            valid = False
        if not valid:
            errors.append(Error(f"{name} must be an explicit HTTP(S) endpoint.", id="suite.E002"))
    for name in (
        "SUITE_APP_ID",
        "SUITE_POLICY_SERVICE_ID",
        "SUITE_DIRECTORY_TOKEN_FILE",
        "SUITE_POLICY_TOKEN_FILE",
        "SUITE_LOGOUT_TOKEN_FILE",
    ):
        if not getattr(settings, name, ""):
            errors.append(Error(f"{name} is required for activation.", id="suite.E003"))
    try:
        UUID(str(settings.SUITE_ORGANIZATION_ID))
    except (ValueError, TypeError):
        errors.append(Error("SUITE_ORGANIZATION_ID must be the ST UUID.", id="suite.E004"))
    if getattr(settings, "OIDC_ALLOW_UNSECURED_JWT", False):
        errors.append(Error("Suite OIDC requires signed tokens.", id="suite.E005"))
    return errors
