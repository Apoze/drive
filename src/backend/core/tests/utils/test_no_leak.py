"""Direct tests for no-leak hashing helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

import hashlib

from core.utils.no_leak import safe_str_hash, sha256_16


def test_sha256_16_returns_stable_truncated_digest():
    value = "sensitive/path/value"

    assert sha256_16(value) == hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    assert len(sha256_16(value)) == 16


def test_safe_str_hash_propagates_none_and_hashes_strings():
    assert safe_str_hash(None) is None
    assert safe_str_hash("alpha") == sha256_16("alpha")
