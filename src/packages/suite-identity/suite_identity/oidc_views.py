"""Extend the native La Suite OIDC request view in Drive, People and Docs."""

from lasuite.oidc_login.views import OIDCAuthenticationRequestView

from .login import SuiteAuthenticationRequestMixin


class SuiteAuthenticationRequestView(
    SuiteAuthenticationRequestMixin, OIDCAuthenticationRequestView
):
    """Preserve native state persistence and silent SSO alongside explicit recovery."""
