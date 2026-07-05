"""Direct contract tests for the mount secret resolver singleton wrapper."""

from __future__ import annotations

from core.services.secret_resolver import get_mount_secret_resolver


class _FakeSecretResolver:
    instances = 0

    def __init__(self, *, refresh_seconds: int) -> None:
        type(self).instances += 1
        self.refresh_seconds = refresh_seconds


def test_get_mount_secret_resolver_is_a_singleton(monkeypatch, settings):
    """The mount resolver wrapper caches the resolver instance."""

    get_mount_secret_resolver.cache_clear()
    _FakeSecretResolver.instances = 0
    settings.MOUNTS_SECRET_REFRESH_SECONDS = 12
    monkeypatch.setattr("core.services.secret_resolver.SecretResolver", _FakeSecretResolver)

    first = get_mount_secret_resolver()
    second = get_mount_secret_resolver()

    assert first is second
    assert isinstance(first, _FakeSecretResolver)
    assert first.refresh_seconds == 12
    assert _FakeSecretResolver.instances == 1


def test_get_mount_secret_resolver_clamps_negative_refresh_to_one(monkeypatch, settings):
    """Negative refresh values are coerced to the minimum bounded window."""

    get_mount_secret_resolver.cache_clear()
    settings.MOUNTS_SECRET_REFRESH_SECONDS = -7
    monkeypatch.setattr("core.services.secret_resolver.SecretResolver", _FakeSecretResolver)

    resolver = get_mount_secret_resolver()

    assert resolver.refresh_seconds == 1


def test_get_mount_secret_resolver_treats_zero_as_default_window(monkeypatch, settings):
    """A falsy zero keeps the documented default bounded window."""

    get_mount_secret_resolver.cache_clear()
    settings.MOUNTS_SECRET_REFRESH_SECONDS = 0
    monkeypatch.setattr("core.services.secret_resolver.SecretResolver", _FakeSecretResolver)

    resolver = get_mount_secret_resolver()

    assert resolver.refresh_seconds == 60
