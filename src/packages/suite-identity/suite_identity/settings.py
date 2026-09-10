"""Configuration shared by the existing django-configurations projects."""

from configurations import Configuration, values


class SuiteSettings(Configuration):
    """Opt-in rollout, with the same bounded defaults in every consumer."""

    SUITE_IDENTITY_ENABLED = values.BooleanValue(False, environ_prefix=None)
    SUITE_APP_ID = values.Value("", environ_prefix=None)
    SUITE_OIDC_ISSUER = values.Value("", environ_prefix=None)
    SUITE_DELEGATION_PEER_ISSUERS = values.ListValue([], environ_prefix=None)
    SUITE_ORGANIZATION_ID = values.Value("", environ_prefix=None)
    SUITE_DIRECTORY_URL = values.Value("", environ_prefix=None)
    SUITE_DIRECTORY_TOKEN_FILE = values.Value("", environ_prefix=None)
    SUITE_POLICY_URL = values.Value("", environ_prefix=None)
    SUITE_POLICY_TOKEN_FILE = values.Value("", environ_prefix=None)
    SUITE_POLICY_SERVICE_ID = values.Value("", environ_prefix=None)
    SUITE_CATALOGUE_URL = values.Value("", environ_prefix=None)
    SUITE_LOGOUT_URL = values.Value("", environ_prefix=None)
    SUITE_LOGOUT_TOKEN_FILE = values.Value("", environ_prefix=None)
    SUITE_IDENTITY_REQUEST_URL = values.Value("", environ_prefix=None)
    OIDC_RS_BACKEND_CLASS = values.Value(
        "suite_identity.resource_server.SuiteResourceServerBackend", environ_prefix=None
    )
    CSRF_COOKIE_NAME = values.Value("csrftoken", environ_prefix=None)
    OIDC_USE_PKCE = values.BooleanValue(True, environ_prefix=None)
    OIDC_STORE_ACCESS_TOKEN = values.BooleanValue(False, environ_prefix=None)
    OIDC_TIMEOUT = values.PositiveIntegerValue(5, environ_prefix=None)
    SUITE_IDENTITY_MAX_STALE_SECONDS = values.PositiveIntegerValue(90, environ_prefix=None)
    SUITE_IDENTITY_AUTH_MAX_AGE = values.PositiveIntegerValue(900, environ_prefix=None)
    DOCUMENT_PEER_API_URL = values.Value("", environ_prefix=None)
    DOCUMENT_PEER_OIDC_ISSUER = values.Value("", environ_prefix=None)
    DOCUMENT_INBOUND_READ_KEY_FILE = values.Value("", environ_prefix=None)
    DOCUMENT_INBOUND_MUTATION_KEY_FILE = values.Value("", environ_prefix=None)
    DOCUMENT_OUTBOUND_READ_KEY_FILE = values.Value("", environ_prefix=None)
    DOCUMENT_OUTBOUND_MUTATION_KEY_FILE = values.Value("", environ_prefix=None)

    @property
    def CELERY_BEAT_SCHEDULE(self):
        if self.SUITE_DIRECTORY_URL and self.SUITE_ORGANIZATION_ID:
            return {
                "suite-identity-reconciliation": {
                    "task": "suite_identity.synchronize",
                    "schedule": 30.0,
                    "options": {"expires": 30},
                },
            }
        return {}
