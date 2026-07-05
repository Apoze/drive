"""Direct contract tests for public share-link tokens."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

from uuid import uuid4

import pytest

from core.utils.share_links import compute_item_share_token, validate_item_share_token


def test_compute_item_share_token_is_deterministic_and_round_trips():
    item_id = uuid4()

    token_a = compute_item_share_token(item_id)
    token_b = compute_item_share_token(item_id)

    assert token_a == token_b
    assert validate_item_share_token(token_a) == item_id


@pytest.mark.parametrize(
    "token",
    [
        "",
        "not-a-token",
        "not-a-uuid.1234",
        "12345678-1234-5678-1234-567812345678",
        "12345678-1234-5678-1234-567812345678.bad",
    ],
)
def test_validate_item_share_token_returns_none_for_empty_or_malformed_token(token):
    assert validate_item_share_token(token) is None


def test_validate_item_share_token_returns_none_for_tampered_signature():
    item_id = uuid4()
    token = compute_item_share_token(item_id)
    tampered = f"{token[:-1]}{'0' if token[-1] != '0' else '1'}"

    assert validate_item_share_token(tampered) is None
