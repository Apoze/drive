"""Archive extraction limits.

These limits are meant to protect the backend from zip-bombs / path traversal
attacks and to keep extraction resource usage bounded.

All limits are configurable via environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    """Read an integer env var, returning `default` on missing/invalid."""

    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class ArchiveExtractionLimits:
    """Resource limits applied during server-side extraction."""

    max_files: int
    max_total_size: int
    max_file_size: int
    max_path_length: int
    max_depth: int
    max_compression_ratio: int


def get_archive_extraction_limits() -> ArchiveExtractionLimits:
    """Read archive extraction limits from environment variables."""

    return ArchiveExtractionLimits(
        max_files=_env_int("ARCHIVE_EXTRACT_MAX_FILES", 10_000),
        max_total_size=_env_int("ARCHIVE_EXTRACT_MAX_TOTAL_SIZE", 5 * 1024**3),  # 5 GiB
        max_file_size=_env_int("ARCHIVE_EXTRACT_MAX_FILE_SIZE", 1 * 1024**3),  # 1 GiB
        max_path_length=_env_int("ARCHIVE_EXTRACT_MAX_PATH_LENGTH", 512),
        max_depth=_env_int("ARCHIVE_EXTRACT_MAX_DEPTH", 32),
        max_compression_ratio=_env_int("ARCHIVE_EXTRACT_MAX_COMPRESSION_RATIO", 1000),
    )


DEFAULT_LIMITS = get_archive_extraction_limits()
