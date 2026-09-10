"""The executable activation contract cannot silently exceed revocation deadlines."""

from django.test import override_settings

from suite_identity.checks import check_suite_settings


def test_activation_rejects_incomplete_or_overlong_configuration():
    endpoints = dict.fromkeys(
        (
            "SUITE_OIDC_ISSUER",
            "SUITE_DIRECTORY_URL",
            "SUITE_POLICY_URL",
            "SUITE_CATALOGUE_URL",
            "SUITE_LOGOUT_URL",
            "SUITE_IDENTITY_REQUEST_URL",
        ),
        "https://suite.invalid/",
    )
    with override_settings(
        **endpoints,
        SUITE_APP_ID="docs",
        SUITE_POLICY_SERVICE_ID="docs",
        SUITE_DIRECTORY_TOKEN_FILE="/run/read.key",
        SUITE_POLICY_TOKEN_FILE="/run/policy.key",
        SUITE_LOGOUT_TOKEN_FILE="/run/write.key",
        SUITE_ORGANIZATION_ID="a1c42131-f2b5-49d6-b432-48f886bb7903",
    ):
        assert check_suite_settings(None) == []
        with override_settings(SUITE_IDENTITY_MAX_STALE_SECONDS=91, SUITE_OIDC_ISSUER=""):
            assert {error.id for error in check_suite_settings(None)} == {
                "suite.E001",
                "suite.E002",
            }
