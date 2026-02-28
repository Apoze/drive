"""Local filesystem MountProvider (test/dev only).

This provider maps mount paths to a configured local directory inside the
container. It is intended for deterministic E2E runs where an SMB server is
not available.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from core.mounts.paths import MountPathNormalizationError, normalize_mount_path
from core.mounts.providers.base import MountEntry, MountProviderError


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


def _fs_path(*, root: Path, normalized_path: str) -> Path:
    try:
        mount_path = normalize_mount_path(normalized_path)
    except MountPathNormalizationError as exc:
        raise MountProviderError(
            failure_class="mount.path.invalid",
            next_action_hint="Verify the path is a valid mount path and retry.",
            public_message="Invalid mount path.",
            public_code="mount.path.invalid",
        ) from exc

    rel = mount_path.lstrip("/")
    target = (root / rel).resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    try:
        _ = target.relative_to(root_resolved)
    except ValueError as exc:
        raise MountProviderError(
            failure_class="mount.path.invalid",
            next_action_hint="Verify the path is within the mount root and retry.",
            public_message="Invalid mount path.",
            public_code="mount.path.invalid",
        ) from exc
    return target


def _entry_from_path(*, normalized_path: str, fs_path: Path) -> MountEntry:
    st = fs_path.stat()
    entry_type = "folder" if fs_path.is_dir() else "file"
    modified_at = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    size = None if entry_type == "folder" else int(st.st_size)
    name = fs_path.name if normalized_path != "/" else "/"
    return MountEntry(
        entry_type=entry_type,
        normalized_path=normalized_path,
        name=name,
        size=size,
        modified_at=modified_at,
    )


def stat(*, mount: dict, normalized_path: str) -> MountEntry:
    """Return metadata for a target path."""
    root = _load_root_dir(mount)
    target = _fs_path(root=root, normalized_path=normalized_path)
    if not target.exists():
        raise MountProviderError(
            failure_class="mount.path.not_found",
            next_action_hint="Verify the path exists in the mount and retry.",
            public_message="Mount path not found.",
            public_code="mount.path.not_found",
        )
    return _entry_from_path(normalized_path=normalize_mount_path(normalized_path), fs_path=target)


def list_children(*, mount: dict, normalized_path: str) -> list[MountEntry]:
    """List immediate child entries under a folder path."""
    root = _load_root_dir(mount)
    mount_path = normalize_mount_path(normalized_path)
    target = _fs_path(root=root, normalized_path=mount_path)

    if not target.exists():
        raise MountProviderError(
            failure_class="mount.path.not_found",
            next_action_hint="Verify the path exists in the mount and retry.",
            public_message="Mount path not found.",
            public_code="mount.path.not_found",
        )
    if not target.is_dir():
        return []

    entries: list[MountEntry] = []
    for child in sorted(target.iterdir(), key=lambda p: p.name):
        child_mount_path = normalize_mount_path(f"{mount_path.rstrip('/')}/{child.name}")
        entries.append(_entry_from_path(normalized_path=child_mount_path, fs_path=child))
    return entries


@contextmanager
def open_read(*, mount: dict, normalized_path: str) -> Iterator[Any]:
    """Open a mount file for reading (binary)."""
    root = _load_root_dir(mount)
    target = _fs_path(root=root, normalized_path=normalized_path)
    if not target.exists() or not target.is_file():
        raise MountProviderError(
            failure_class="mount.path.not_found",
            next_action_hint="Verify the file exists in the mount and retry.",
            public_message="Mount path not found.",
            public_code="mount.path.not_found",
        )
    with target.open("rb") as f:
        yield f


@contextmanager
def open_write(*, mount: dict, normalized_path: str) -> Iterator[Any]:
    """Open a mount file for writing (binary), creating parent dirs as needed."""
    root = _load_root_dir(mount)
    target = _fs_path(root=root, normalized_path=normalized_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as f:
        yield f


def mkdirs(*, mount: dict, normalized_path: str) -> None:
    """Create a directory (and parents) under the mount root."""
    root = _load_root_dir(mount)
    target = _fs_path(root=root, normalized_path=normalized_path)
    target.mkdir(parents=True, exist_ok=True)


def rename(
    *,
    mount: dict,
    src_normalized_path: str,
    dst_normalized_path: str,
) -> None:
    """Rename (move) a path within the mount root."""
    root = _load_root_dir(mount)
    src = _fs_path(root=root, normalized_path=src_normalized_path)
    dst = _fs_path(root=root, normalized_path=dst_normalized_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(src, dst)
    except FileNotFoundError as exc:
        raise MountProviderError(
            failure_class="mount.path.not_found",
            next_action_hint="Verify the source path exists and retry.",
            public_message="Mount path not found.",
            public_code="mount.path.not_found",
        ) from exc
    except OSError as exc:
        raise MountProviderError(
            failure_class="mount.localfs.rename_failed",
            next_action_hint="Verify the destination is writable and retry.",
            public_message="Mount operation failed.",
            public_code="mount.operation.failed",
        ) from exc


def remove(*, mount: dict, normalized_path: str) -> None:
    """Remove a file or an empty folder."""
    root = _load_root_dir(mount)
    target = _fs_path(root=root, normalized_path=normalized_path)
    try:
        if target.is_dir():
            target.rmdir()
        else:
            target.unlink()
    except FileNotFoundError as exc:
        raise MountProviderError(
            failure_class="mount.path.not_found",
            next_action_hint="Verify the path exists and retry.",
            public_message="Mount path not found.",
            public_code="mount.path.not_found",
        ) from exc
    except OSError as exc:
        raise MountProviderError(
            failure_class="mount.localfs.remove_failed",
            next_action_hint="Verify the path can be removed and retry.",
            public_message="Mount operation failed.",
            public_code="mount.operation.failed",
        ) from exc


def supports_range_reads(*, mount: dict) -> bool:
    """Local file handles support seeks/range-like reads."""
    _ = mount
    return True
