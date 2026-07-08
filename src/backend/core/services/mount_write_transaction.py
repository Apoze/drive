"""Provider-neutral MountProvider temp-write and rename helpers."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterable
from dataclasses import dataclass

from core.mounts.providers.base import MountProviderError


class MountWriteTooLarge(Exception):
    """Raised when a mount write exceeds the caller-provided byte limit."""


class MountWriteTimeout(Exception):
    """Raised when a mount write exceeds the caller-provided time limit."""


@dataclass(frozen=True, slots=True)
class MountWriteLimits:
    """Optional limits for one mount temp write."""

    max_bytes: int | None = None
    max_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class MountWriteResult:
    """Result of one mount temp-write/final-rename operation."""

    temp_path: str
    final_path: str
    bytes_written: int


def iter_read_chunks(file_obj, *, chunk_size: int = 64 * 1024) -> Iterable[bytes]:
    """Yield chunks from a readable file-like object."""

    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        yield chunk


def cleanup_mount_temp(*, provider, mount: dict, temp_path: str) -> None:
    """Best-effort cleanup for temp paths; never masks the original failure."""

    with contextlib.suppress(MountProviderError, Exception):
        provider.remove(mount=mount, normalized_path=temp_path)


def remove_mount_temp_if_exists(*, provider, mount: dict, temp_path: str) -> None:
    """Remove a stale temp path, ignoring only the documented not-found case."""

    try:
        provider.remove(mount=mount, normalized_path=temp_path)
    except MountProviderError as exc:
        if exc.public_code != "mount.path.not_found":
            raise


def write_chunks_to_mount_temp(
    *,
    provider,
    mount: dict,
    temp_path: str,
    chunks: Iterable[bytes],
    limits: MountWriteLimits | None = None,
) -> int:
    """Stream chunks into a provider temp file and return bytes written."""

    effective_limits = limits or MountWriteLimits()
    started = time.monotonic()
    bytes_written = 0

    with provider.open_write(mount=mount, normalized_path=temp_path) as out_fp:
        for chunk in chunks:
            if not chunk:
                continue
            bytes_written += len(chunk)
            if (
                effective_limits.max_bytes is not None
                and bytes_written > effective_limits.max_bytes
            ):
                raise MountWriteTooLarge()
            if (
                effective_limits.max_seconds is not None
                and (time.monotonic() - started) > effective_limits.max_seconds
            ):
                raise MountWriteTimeout()
            out_fp.write(chunk)

    return bytes_written


def finalize_mount_temp(
    *,
    provider,
    mount: dict,
    temp_path: str,
    final_path: str,
    cleanup_on_error: bool = True,
) -> None:
    """Rename a temp path into its final destination, cleaning temp on failure."""

    try:
        provider.rename(
            mount=mount,
            src_normalized_path=temp_path,
            dst_normalized_path=final_path,
        )
    except Exception:
        if cleanup_on_error:
            cleanup_mount_temp(provider=provider, mount=mount, temp_path=temp_path)
        raise


def write_mount_stream_transaction(  # noqa: PLR0913  # pylint: disable=too-many-arguments
    *,
    provider,
    mount: dict,
    temp_path: str,
    final_path: str,
    chunks: Iterable[bytes],
    limits: MountWriteLimits | None = None,
    parent_path: str | None = None,
    remove_stale_temp: bool = True,
) -> MountWriteResult:
    """
    Write chunks to a temp path and finalize by rename.

    Callers own product policy, permissions, quota/timeout values, collision
    checks, and error-to-response mapping. This helper owns the repeated
    provider mechanics and rollback.
    """

    if remove_stale_temp:
        remove_mount_temp_if_exists(provider=provider, mount=mount, temp_path=temp_path)
    if parent_path is not None:
        provider.mkdirs(mount=mount, normalized_path=parent_path)

    try:
        bytes_written = write_chunks_to_mount_temp(
            provider=provider,
            mount=mount,
            temp_path=temp_path,
            chunks=chunks,
            limits=limits,
        )
        finalize_mount_temp(
            provider=provider,
            mount=mount,
            temp_path=temp_path,
            final_path=final_path,
            cleanup_on_error=False,
        )
    except Exception:
        cleanup_mount_temp(provider=provider, mount=mount, temp_path=temp_path)
        raise

    return MountWriteResult(
        temp_path=temp_path,
        final_path=final_path,
        bytes_written=bytes_written,
    )


def copy_mount_file_transaction(  # noqa: PLR0913  # pylint: disable=too-many-arguments
    *,
    provider,
    mount: dict,
    source_path: str,
    temp_path: str,
    final_path: str,
    chunk_size: int = 64 * 1024,
    remove_stale_temp: bool = True,
) -> MountWriteResult:
    """Copy one provider file through a temp path and final rename."""

    if remove_stale_temp:
        remove_mount_temp_if_exists(provider=provider, mount=mount, temp_path=temp_path)

    with provider.open_read(mount=mount, normalized_path=source_path) as src:
        return write_mount_stream_transaction(
            provider=provider,
            mount=mount,
            temp_path=temp_path,
            final_path=final_path,
            chunks=iter_read_chunks(src, chunk_size=chunk_size),
            remove_stale_temp=False,
        )
