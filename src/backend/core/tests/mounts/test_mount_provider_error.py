"""Regression tests for mount provider exceptions."""

import contextlib

import pytest

from core.mounts.providers.base import MountProviderError

pytestmark = pytest.mark.django_db


def test_mount_provider_error_is_safe_with_contextlib_suppress():
    """The exception must keep normal traceback behavior under Python 3.13."""
    with contextlib.suppress(MountProviderError):
        raise MountProviderError(
            failure_class="mount.session.init_failed",
            next_action_hint="retry",
            public_message="Connection/session initialization failed.",
            public_code="mount.session.init_failed",
        )


@contextlib.contextmanager
def _raise_mount_provider_error_in_exit():
    yield
    raise MountProviderError(
        failure_class="mount.session.init_failed",
        next_action_hint="retry",
        public_message="Connection/session initialization failed.",
        public_code="mount.session.init_failed",
    )


def test_mount_provider_error_is_safe_with_generator_contextmanager():
    """The exception must allow traceback reassignment inside contextlib."""
    with pytest.raises(MountProviderError):
        with _raise_mount_provider_error_in_exit():
            pass
