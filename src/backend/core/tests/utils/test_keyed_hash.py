"""Direct tests for keyed hashing helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

import re

from core.utils.keyed_hash import hmac_sha256_16


def test_hmac_sha256_16_is_stable_for_same_salt_and_value():
    digest = hmac_sha256_16(salt="drive.test", value="alpha")

    assert digest == hmac_sha256_16(salt="drive.test", value="alpha")
    assert len(digest) == 16
    assert re.fullmatch(r"[0-9a-f]{16}", digest)


def test_hmac_sha256_16_changes_when_salt_changes():
    assert hmac_sha256_16(salt="drive.test.a", value="alpha") != hmac_sha256_16(
        salt="drive.test.b",
        value="alpha",
    )


def test_hmac_sha256_16_changes_when_value_changes():
    assert hmac_sha256_16(salt="drive.test", value="alpha") != hmac_sha256_16(
        salt="drive.test",
        value="beta",
    )
