"""Singleton secret resolver(s) for runtime secret resolution (mount providers)."""

from __future__ import annotations

import hashlib
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ValidationError

from core.models import StorageBackend
from core.utils.secret_resolver import ResolvedSecret, SecretResolutionError, SecretResolver


class StorageSecretResolver(SecretResolver):
    """Extend the existing refs-only contract with encrypted connection secrets."""

    def resolve(self, *, secret_path, secret_ref):
        if not secret_path and secret_ref and secret_ref.startswith("storage:"):
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_connections import decrypt_credentials  # noqa: PLC0415

            try:
                backend = StorageBackend.objects.get(pk=secret_ref.removeprefix("storage:"))
                value = decrypt_credentials(backend)["password"]
                return ResolvedSecret(
                    value=value,
                    version_sha256_16=hashlib.sha256(value.encode()).hexdigest()[:16],
                    source="vault",
                )
            except (StorageBackend.DoesNotExist, ValidationError, KeyError, ValueError):
                raise SecretResolutionError(
                    failure_class="config.secret.unavailable",
                    next_action_hint="Verify the connection credential vault.",
                    safe_evidence={},
                ) from None
        return super().resolve(secret_path=secret_path, secret_ref=secret_ref)


@lru_cache(maxsize=1)
def get_mount_secret_resolver() -> SecretResolver:
    """Return the singleton resolver for mount/provider runtime secrets."""

    refresh_seconds = int(getattr(settings, "MOUNTS_SECRET_REFRESH_SECONDS", 60) or 60)
    refresh_seconds = max(refresh_seconds, 1)
    return StorageSecretResolver(refresh_seconds=refresh_seconds)
