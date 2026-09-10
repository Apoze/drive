"""Small database for shared-contract tests, independent of the running stacks."""

SECRET_KEY = "isolated-contract-tests-only"
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "suite_identity",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
SUITE_IDENTITY_ENABLED = True
SUITE_IDENTITY_MAX_STALE_SECONDS = 90
SUITE_IDENTITY_AUTH_MAX_AGE = 900
