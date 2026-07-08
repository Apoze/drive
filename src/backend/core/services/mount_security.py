"""MountProvider security gates (policy-level)."""

from __future__ import annotations

import os

MOUNT_ARCHIVE_EXTRACT_UNSAFE_ERROR_CODE = "MOUNT_ARCHIVE_EXTRACT_UNSAFE"
MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT_PUBLIC_MESSAGE = (
    "Mount is not hardened for archive extraction (hardening required)"
)


def mounts_safe_for_archive_extract() -> bool:
    """
    Global safety gate for any "write many paths" operation to MountProvider backends.

    Mount extraction is refused unless MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT is explicitly true.
    """

    return str(os.environ.get("MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT", "")).lower() in {
        "1",
        "true",
        "yes",
    }
