"""Archive extraction security helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


class UnsafeArchivePath(ValueError):
    """Raised when an archive entry path is unsafe (zip-slip/path traversal)."""


@dataclass(frozen=True)
class NormalizedArchivePath:
    """A validated, normalized path for an archive entry."""

    raw: str
    normalized: str
    parts: tuple[str, ...]

    @property
    def depth(self) -> int:
        """Number of path components."""
        return len(self.parts)

    @property
    def name(self) -> str:
        """Basename of the entry."""
        return self.parts[-1] if self.parts else ""

    @property
    def parent_parts(self) -> tuple[str, ...]:
        """All directory components (without the basename)."""
        return self.parts[:-1]


def normalize_archive_path(path: str) -> NormalizedArchivePath:
    """
    Normalize and validate an entry path from an archive.

    - Convert backslashes to slashes
    - Reject absolute paths
    - Reject any `..` traversal
    - Strip leading `./`
    """
    if not isinstance(path, str) or not path:
        raise UnsafeArchivePath("Empty path.")

    raw = path
    path = path.replace("\\", "/")
    # Some zips contain leading "./"
    while path.startswith("./"):
        path = path[2:]

    posix = PurePosixPath(path)
    if posix.is_absolute():
        raise UnsafeArchivePath("Absolute paths are not allowed.")

    parts: list[str] = []
    for part in posix.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise UnsafeArchivePath("Path traversal is not allowed.")
        parts.append(part)

    if not parts:
        raise UnsafeArchivePath("Invalid path.")

    normalized = "/".join(parts)
    return NormalizedArchivePath(raw=raw, normalized=normalized, parts=tuple(parts))
