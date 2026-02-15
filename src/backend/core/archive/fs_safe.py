"""Filesystem-safe helpers for storage backends exposing local paths.

These helpers enforce "no-follow" semantics for symlinks in path components to
mitigate path traversal via pre-existing symlinks on the destination filesystem
(e.g. mounted SMB).

Important:
- This module is designed for Linux/POSIX backends where `openat(2)` semantics
  are available via Python's `os.open(..., dir_fd=...)`, and where `O_NOFOLLOW`
  can be relied upon to fail on symlinks.
- We intentionally fail closed if the required OS features are not available.
  A best-effort lstat/realpath walk is TOCTOU-prone and is not used here.
  See: https://lwn.net/Articles/899543/
"""

from __future__ import annotations

import os
import shutil
import stat
from dataclasses import dataclass
from typing import IO


class UnsafeFilesystemPath(ValueError):
    """Raised when a storage path is unsafe on a local filesystem."""


class UnsupportedFilesystemSafety(UnsafeFilesystemPath):
    """Raised when the runtime cannot guarantee safe no-follow filesystem IO."""


def _require_nofollow_support() -> None:
    """
    Ensure we can enforce "no-follow" semantics for each path component.

    We require:
    - os.open supports dir_fd (openat)
    - os.mkdir supports dir_fd (mkdirat) for safe intermediate directory creation
    - O_NOFOLLOW is available (refuse symlink components)
    """

    supports_dir_fd = getattr(os, "supports_dir_fd", None)
    if supports_dir_fd is None or os.open not in supports_dir_fd:
        raise UnsupportedFilesystemSafety(
            "openat() support is required for safe filesystem IO."
        )
    if os.mkdir not in supports_dir_fd:
        raise UnsupportedFilesystemSafety(
            "mkdirat() support is required for safe filesystem IO."
        )
    if not hasattr(os, "O_NOFOLLOW"):
        raise UnsupportedFilesystemSafety(
            "O_NOFOLLOW is required for safe filesystem IO."
        )


def _normalize_rel_parts(path: str) -> list[str]:
    if not isinstance(path, str) or not path:
        raise UnsafeFilesystemPath("Empty path.")

    path = path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]

    if path.startswith("/"):
        raise UnsafeFilesystemPath("Absolute paths are not allowed.")

    parts: list[str] = []
    for part in path.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise UnsafeFilesystemPath("Path traversal is not allowed.")
        parts.append(part)

    if not parts:
        raise UnsafeFilesystemPath("Invalid path.")
    return parts


@dataclass(frozen=True)
class LocalStorageTarget:
    root: str
    rel_parts: tuple[str, ...]

    @property
    def rel_path(self) -> str:
        return os.path.join(*self.rel_parts) if self.rel_parts else ""


def _get_storage_root_and_rel_parts(storage, name: str) -> LocalStorageTarget:
    path_fn = getattr(storage, "path", None)
    if path_fn is None:
        raise NotImplementedError("Storage does not expose a local filesystem path.")
    try:
        root = path_fn("")
        abs_path = path_fn(name)
    except Exception as exc:  # noqa: BLE001
        raise NotImplementedError(
            "Storage does not expose a local filesystem path."
        ) from exc

    root_norm = os.path.abspath(root)
    abs_norm = os.path.abspath(abs_path)

    try:
        common = os.path.commonpath([root_norm, abs_norm])
    except ValueError as exc:
        raise UnsafeFilesystemPath("Invalid storage path.") from exc
    if common != root_norm:
        raise UnsafeFilesystemPath("Storage path escapes root.")

    rel = os.path.relpath(abs_norm, root_norm)
    rel_parts = _normalize_rel_parts(rel)
    return LocalStorageTarget(root=root_norm, rel_parts=tuple(rel_parts))


def _open_dir_nofollow(parent_fd: int, name: str) -> int:
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(name, flags, dir_fd=parent_fd)
    if not hasattr(os, "O_DIRECTORY"):
        try:
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                raise NotADirectoryError(name)
        except Exception:
            os.close(fd)
            raise
    return fd


def _ensure_dir_nofollow(parent_fd: int, name: str) -> int:
    """Ensure a directory exists and open it without following symlinks."""
    try:
        return _open_dir_nofollow(parent_fd, name)
    except FileNotFoundError:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
        return _open_dir_nofollow(parent_fd, name)


def _open_file_write_nofollow(parent_fd: int, name: str) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    return os.open(name, flags, 0o600, dir_fd=parent_fd)


def _open_file_read_nofollow(parent_fd: int, name: str) -> int:
    flags = os.O_RDONLY | os.O_NOFOLLOW
    return os.open(name, flags, dir_fd=parent_fd)


def safe_write_fileobj_to_storage(storage, *, name: str, fileobj, chunk_size: int = 1024 * 1024) -> None:
    """Write a file-like object to a local-path storage without following symlinks."""

    target = _get_storage_root_and_rel_parts(storage, name)
    _require_nofollow_support()
    rel_parts = list(target.rel_parts)
    if not rel_parts:
        raise UnsafeFilesystemPath("Invalid target path.")

    root_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        root_flags |= os.O_DIRECTORY
    root_fd = os.open(target.root, root_flags)
    current_fd = root_fd
    try:
        for part in rel_parts[:-1]:
            next_fd = _ensure_dir_nofollow(current_fd, part)
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd

        fd = _open_file_write_nofollow(current_fd, rel_parts[-1])
        try:
            with os.fdopen(fd, "wb") as out_fp:
                shutil.copyfileobj(fileobj, out_fp, length=chunk_size)
        finally:
            # fd is closed by fdopen context manager
            pass
    except OSError as exc:  # noqa: BLE001
        raise UnsafeFilesystemPath("Refused unsafe filesystem write.") from exc
    finally:
        try:
            if current_fd != root_fd:
                os.close(current_fd)
        except OSError:
            pass
        try:
            os.close(root_fd)
        except OSError:
            pass


def safe_open_storage_for_read(storage, *, name: str) -> IO[bytes]:
    """Open a stored file for reading without following symlinks (local-path storages only)."""

    target = _get_storage_root_and_rel_parts(storage, name)
    _require_nofollow_support()
    rel_parts = list(target.rel_parts)
    if not rel_parts:
        raise UnsafeFilesystemPath("Invalid source path.")

    root_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        root_flags |= os.O_DIRECTORY
    root_fd = os.open(target.root, root_flags)
    current_fd = root_fd
    try:
        for part in rel_parts[:-1]:
            next_fd = _open_dir_nofollow(current_fd, part)
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd

        fd = _open_file_read_nofollow(current_fd, rel_parts[-1])
        return os.fdopen(fd, "rb")
    except OSError as exc:  # noqa: BLE001
        raise UnsafeFilesystemPath("Refused unsafe filesystem read.") from exc
    finally:
        try:
            if current_fd != root_fd:
                os.close(current_fd)
        finally:
            try:
                os.close(root_fd)
            except OSError:
                pass


def probe_storage_path_is_safe_file(storage, *, name: str) -> bool:
    """Return True if `name` can be opened for read without following symlinks."""

    try:
        fp = safe_open_storage_for_read(storage, name=name)
    except (UnsafeFilesystemPath, NotImplementedError):
        return False
    try:
        return True
    finally:
        try:
            fp.close()
        except OSError:
            pass
