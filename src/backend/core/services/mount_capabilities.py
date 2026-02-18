"""Mount capability keys and normalization helpers (contract-level)."""

from __future__ import annotations

from typing import Any

MOUNT_CAPABILITY_KEYS: tuple[str, ...] = (
    "mount.upload",
    "mount.preview",
    "mount.wopi",
    "mount.share_link",
)

DEFAULT_MOUNT_CAPABILITIES: dict[str, bool] = {
    # Mounts are filesystem-like backends; by default we expose core actions
    # and allow operators to explicitly disable them via params.capabilities.
    "mount.upload": True,
    "mount.preview": True,
    "mount.wopi": True,
    # Sharing is more sensitive; keep it opt-in.
    "mount.share_link": False,
}


def normalize_mount_capabilities(raw: Any) -> dict[str, bool]:
    """
    Normalize a raw capabilities object into a contract-level capability map.

    - Keys are enforced to the documented constants.
    - Values must be booleans; anything else is treated as `False`.
    """

    src = raw if isinstance(raw, dict) else {}

    normalized: dict[str, bool] = dict(DEFAULT_MOUNT_CAPABILITIES)
    for key in MOUNT_CAPABILITY_KEYS:
        value = src.get(key, DEFAULT_MOUNT_CAPABILITIES.get(key, False))
        normalized[key] = value if isinstance(value, bool) else normalized[key]
    return normalized
