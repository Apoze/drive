"""Application registration."""

from django.apps import AppConfig


class SuiteIdentityConfig(AppConfig):
    """Keep identity associations separate from application-owned user records."""

    name = "suite_identity"
    verbose_name = "Identité de la suite"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """Record proof after login, without coupling to any callback implementation."""
        from django.contrib.auth.signals import user_logged_in  # noqa: PLC0415

        # Import receivers only after Django has populated the app registry.
        from . import checks  # noqa: F401, PLC0415
        from .middleware import remember_authentication  # noqa: PLC0415

        user_logged_in.connect(
            remember_authentication, dispatch_uid="suite_identity.login", weak=False
        )
