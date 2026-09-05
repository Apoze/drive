"""Local filesystem MountProvider (test/dev only).

This provider maps mount paths to a configured local directory inside the
container. It is intended for deterministic E2E runs where an SMB server is
not available.
"""

from __future__ import annotations

import ctypes
import errno
import os
import stat as statlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from core.mounts.paths import normalize_mount_path
from core.mounts.providers.base import (
    MountBrowserStreamCapabilities,
    MountEntry,
    MountProviderError,
)


def _config_error(*, failure_class: str, next_action_hint: str) -> MountProviderError:
    return MountProviderError(
        failure_class=failure_class,
        next_action_hint=next_action_hint,
        public_message="Mount provider configuration is invalid.",
        public_code="mount.provider.invalid_config",
    )


def _load_root_dir(mount: dict[str, Any]) -> Path:
    params = mount.get("params") if isinstance(mount.get("params"), dict) else {}
    root_dir = params.get("root_dir")
    if not isinstance(root_dir, str) or not root_dir.strip():
        raise _config_error(
            failure_class="mount.localfs.config.root_dir_missing",
            next_action_hint="Set mounts[*].params.root_dir to an absolute directory path.",
        )
    root = Path(root_dir.strip())
    if not root.is_absolute():
        raise _config_error(
            failure_class="mount.localfs.config.root_dir_invalid",
            next_action_hint="Set mounts[*].params.root_dir to an absolute directory path.",
        )
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _config_error(
            failure_class="mount.localfs.config.root_dir_unwritable",
            next_action_hint=(
                "Ensure mounts[*].params.root_dir is writable by the backend process."
            ),
        ) from exc
    return root


def _operation_error(exc):
    code = "mount.path.not_found" if exc.errno == errno.ENOENT else "mount.operation.failed"
    if exc.errno in {errno.ELOOP, errno.ENOTDIR, errno.EACCES}:
        code = "mount.access.denied"
    elif exc.errno == errno.ENOTEMPTY:
        code = "mount.path.not_empty"
    return MountProviderError(
        failure_class=code,
        next_action_hint="Verify storage access and retry.",
        public_message="Mount operation failed.",
        public_code=code,
    )


@contextmanager
def _directory(*, mount, normalized_path, create=False):
    """Walk with directory handles: external symlink swaps cannot redirect IO."""
    path = normalize_mount_path(normalized_path)
    fd = None
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open(_load_root_dir(mount), flags)
        for part in path.strip("/").split("/") if path != "/" else []:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child_fd
        yield fd
    except OSError as exc:
        raise _operation_error(exc) from None
    finally:
        if fd is not None:
            os.close(fd)


@contextmanager
def _parent(*, mount, normalized_path, create=False):
    path = normalize_mount_path(normalized_path)
    parent, _, name = path.rpartition("/")
    with _directory(mount=mount, normalized_path=parent or "/", create=create) as fd:
        yield fd, name or "."


def _entry(*, path, st):
    if not (statlib.S_ISREG(st.st_mode) or statlib.S_ISDIR(st.st_mode)):
        raise MountProviderError(
            failure_class="mount.access.denied",
            next_action_hint="Use a regular file or folder.",
            public_message="Storage path is not accessible.",
            public_code="mount.access.denied",
        )
    is_dir = statlib.S_ISDIR(st.st_mode)
    return MountEntry(
        entry_type="folder" if is_dir else "file",
        normalized_path=path,
        name=path.rsplit("/", 1)[-1] or "/",
        size=None if is_dir else st.st_size,
        modified_at=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
        object_identity=f"{st.st_dev:x}:{st.st_ino:x}",
    )


def stat(*, mount: dict, normalized_path: str) -> MountEntry:
    """Read metadata without following symbolic links."""
    with _parent(mount=mount, normalized_path=normalized_path) as (fd, name):
        return _entry(
            path=normalize_mount_path(normalized_path),
            st=os.stat(name, dir_fd=fd, follow_symlinks=False),
        )


def iter_children(*, mount: dict, normalized_path: str):
    """Stream directory metadata without resolving children through symlinks."""
    path = normalize_mount_path(normalized_path)
    with _directory(mount=mount, normalized_path=path) as fd, os.scandir(fd) as entries:
        for child in entries:
            if child.is_symlink():
                continue
            yield _entry(
                path=normalize_mount_path(f"{path}/{child.name}"),
                st=child.stat(follow_symlinks=False),
            )


def list_children(*, mount: dict, normalized_path: str) -> list[MountEntry]:
    """Return the existing browse contract; inventory uses the streaming iterator."""
    return sorted(
        iter_children(mount=mount, normalized_path=normalized_path),
        key=lambda entry: (entry.entry_type != "folder", entry.name.casefold()),
    )


@contextmanager
def open_read(*, mount: dict, normalized_path: str) -> Iterator[Any]:
    """Stream from a regular file pinned by its handle."""
    with _parent(mount=mount, normalized_path=normalized_path) as (fd, name):
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(file_fd, "rb") as stream:
            _entry(path=normalized_path, st=os.fstat(stream.fileno()))
            yield stream


@contextmanager
def open_write(*, mount: dict, normalized_path: str) -> Iterator[Any]:
    """Open a regular file without traversing symbolic links, including parents."""
    with _parent(mount=mount, normalized_path=normalized_path, create=True) as (fd, name):
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
        if mount.get("_deny_reparse"):
            flags |= os.O_EXCL
        file_fd = os.open(name, flags, mode=0o600, dir_fd=fd)
        with os.fdopen(file_fd, "wb") as stream:
            metadata = os.fstat(stream.fileno())
            if not statlib.S_ISREG(metadata.st_mode):
                raise _operation_error(OSError(errno.EACCES, "Not a regular file"))
            os.ftruncate(stream.fileno(), 0)
            yield stream


def mkdirs(*, mount: dict, normalized_path: str) -> None:
    """Create parents using the same confined directory traversal as reads."""
    with _directory(mount=mount, normalized_path=normalized_path, create=True):
        pass


def rename(*, mount: dict, src_normalized_path: str, dst_normalized_path: str) -> None:
    """Rename between pinned parent directories on the same filesystem."""
    with _parent(mount=mount, normalized_path=src_normalized_path) as (src_fd, src):
        with _parent(mount=mount, normalized_path=dst_normalized_path, create=True) as (
            dst_fd,
            dst,
        ):
            os.replace(src, dst, src_dir_fd=src_fd, dst_dir_fd=dst_fd)


def remove(*, mount: dict, normalized_path: str) -> None:
    """Remove a file or empty directory without following links."""
    with _parent(mount=mount, normalized_path=normalized_path) as (fd, name):
        st = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if statlib.S_ISDIR(st.st_mode):
            os.rmdir(name, dir_fd=fd)
        else:
            os.unlink(name, dir_fd=fd)


def rename_no_replace(*, mount, src_normalized_path, dst_normalized_path):
    """Publish only if the destination remains unoccupied (Linux renameat2)."""
    rename_at = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if rename_at is None:
        raise _operation_error(OSError(errno.ENOTSUP, "Protected rename is unavailable"))
    rename_at.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename_at.restype = ctypes.c_int
    with _parent(mount=mount, normalized_path=src_normalized_path) as (src_fd, src):
        with _parent(mount=mount, normalized_path=dst_normalized_path) as (dst_fd, dst):
            if rename_at(src_fd, os.fsencode(src), dst_fd, os.fsencode(dst), 1) != 0:
                raise OSError(ctypes.get_errno(), "Protected rename failed")


# Provider capability uses the common signature, independent of configuration.
# pylint: disable-next=unused-argument
def supports_virtual_roots(*, mount: dict) -> bool:
    """Directory-relative operations reject reparse/symlink traversal."""
    return True


def capacity(*, mount: dict) -> dict:
    """Report physical availability separately from logical application limits."""
    with _directory(mount=mount, normalized_path="/") as fd:
        usage = os.fstatvfs(fd)
        return {
            "total_bytes": usage.f_blocks * usage.f_frsize,
            "caller_available_bytes": usage.f_bavail * usage.f_frsize,
            "actual_available_bytes": usage.f_bfree * usage.f_frsize,
        }


def supports_range_reads(*, mount: dict) -> bool:
    """Local file handles support seeks/range-like reads."""
    _ = mount
    return True


def get_browser_stream_capabilities(*, mount: dict) -> MountBrowserStreamCapabilities:
    """Expose browser-stream capabilities for the localfs provider."""

    _ = mount
    return MountBrowserStreamCapabilities(
        browser_stream_mode="proxy",
        supports_random_access=True,
        supports_head_metadata=True,
        supports_stable_version=True,
    )
