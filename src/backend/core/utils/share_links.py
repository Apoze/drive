"""Share link token helpers (deterministic, no DB writes).

Share tokens are deterministic and unforgeable (HMAC) so we can:
- expose stable share URLs without storing per-item tokens
- validate share access without leaking item existence/metadata
"""

from __future__ import annotations

from uuid import UUID

from django.utils.crypto import constant_time_compare, salted_hmac

_SIG_HEX_LEN = 32  # 128-bit truncated signature (hex)
_HMAC_SALT = "drive.share_link.v1"


def compute_item_share_token(item_id: UUID, nonce: UUID | None = None) -> str:
    """Compute a stable share token for an item UUID."""
    item_id_str = f"{item_id}.{nonce}" if nonce else str(item_id)
    sig = salted_hmac(_HMAC_SALT, item_id_str).hexdigest()[:_SIG_HEX_LEN]
    return f"{item_id_str}.{sig}"


def validate_item_share_token(token: str) -> UUID | None:
    """Validate a share token and return the embedded item UUID (or None)."""
    if not token:
        return None

    try:
        signed, sig = token.rsplit(".", 1)
        parts = signed.split(".")
        if len(parts) not in {1, 2}:
            return None
        item_id = UUID(parts[0])
        if len(parts) == 2:
            UUID(parts[1])
    except ValueError:
        return None

    expected = salted_hmac(_HMAC_SALT, signed).hexdigest()[:_SIG_HEX_LEN]
    if not constant_time_compare(sig, expected):
        return None

    return item_id


def current_item_share_token(item, token):
    """Reject a once-valid token after an explicit sharing revocation."""
    return constant_time_compare(
        token or "", compute_item_share_token(item.pk, item.share_link_nonce)
    )
