"""Archive extraction implementation to MountProvider-backed destinations."""

from __future__ import annotations

import os
import posixpath
import tempfile
import uuid
import zipfile
from logging import getLogger

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage

from core import models
from core.archive.extract import _is_zip_filename, _plan_zip, _zipinfo_is_symlink
from core.archive.fs_safe import UnsafeFilesystemPath, safe_open_storage_for_read
from core.archive.limits import get_archive_extraction_max_archive_size
from core.archive.security import UnsafeArchivePath, normalize_archive_path
from core.mounts.paths import normalize_mount_path
from core.mounts.providers.base import MountProviderError
from core.services.mount_archive_extraction import (
    MountArchiveExtractionPreflightError,
    ensure_mount_archive_extract_hardening,
    resolve_mount_archive_destination,
    validate_mount_archive_source_item,
)
from core.services.mount_write_transaction import (
    iter_read_chunks,
    write_mount_stream_transaction,
)
from core.utils.no_leak import safe_str_hash

logger = getLogger(__name__)


def mount_archive_job_cache_key(job_id: str) -> str:
    """Return cache key for a mount archive extraction job."""
    return f"mount_archive_extraction_job:{job_id}"


def set_mount_archive_extraction_job_status(
    job_id: str, payload: dict, ttl_seconds: int = 24 * 3600
) -> None:
    """Persist mount archive extraction status payload in cache."""
    cache.set(mount_archive_job_cache_key(job_id), payload, timeout=ttl_seconds)


def get_mount_archive_extraction_job_status(job_id: str) -> dict:
    """Return the current cached status payload for a job."""
    payload = cache.get(mount_archive_job_cache_key(job_id))
    return payload if isinstance(payload, dict) else {"state": "missing", "errors": []}


def start_mount_archive_extraction_job(  # noqa: PLR0913  # pylint: disable=too-many-arguments
    *,
    job_id: str,
    archive_item_id: str,
    mount_id: str,
    destination_path: str,
    user_id: str,
    mode: str,
    selection_paths: list[str],
) -> None:
    """Initialize the status payload for a new mount archive extraction job."""
    set_mount_archive_extraction_job_status(
        job_id,
        {
            "state": "queued",
            "progress": {
                "files_done": 0,
                "total": 0,
                "bytes_done": 0,
                "bytes_total": 0,
            },
            "skipped_symlinks_count": 0,
            "skipped_unsafe_paths_count": 0,
            "errors": [],
            "user_id": user_id,
            "mount_id": mount_id,
            "destination_path": destination_path,
            "archive_item_id": archive_item_id,
            "mode": mode,
            "selection_paths": selection_paths,
        },
    )


def _get_enabled_mount_or_404(mount_id: str) -> dict:
    mounts = list(getattr(settings, "MOUNTS_REGISTRY", []) or [])
    for mount in mounts:
        if not bool(mount.get("enabled", True)):
            continue
        if str(mount.get("mount_id") or "") == mount_id:
            return mount
    raise KeyError("mount.not_found")


def extract_archive_to_mount(  # noqa: PLR0912,PLR0913,PLR0915  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements
    *,
    job_id: str,
    archive_item_id: str,
    mount_id: str,
    destination_path: str,
    user_id: str,
    mode: str,
    selection_paths: list[str],
) -> dict:
    """
    Extract an archive item (S3-backed) into a MountProvider destination folder.

    Security:
    - Fail-closed global gate `MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT`
    - zip-slip/path traversal prevention via strict path normalization
    - bounded resource usage via existing extraction limits
    """

    try:
        ensure_mount_archive_extract_hardening()
    except MountArchiveExtractionPreflightError as exc:
        raise PermissionError(exc.public_message) from exc

    user = models.User.objects.get(pk=user_id)
    archive_item = models.Item.objects.get(pk=archive_item_id)

    try:
        validate_mount_archive_source_item(user=user, archive_item=archive_item)
    except MountArchiveExtractionPreflightError as exc:
        if exc.error_kind == "permission_denied":
            raise PermissionError(exc.public_message) from exc
        raise ValueError(exc.public_message) from exc

    if not _is_zip_filename(archive_item.filename):
        raise ValueError("Unsupported archive format for mount extraction.")

    max_archive_size = get_archive_extraction_max_archive_size()
    if archive_item.size is not None and int(archive_item.size) > int(max_archive_size):
        raise ValueError("Archive is too large to extract.")

    mount = _get_enabled_mount_or_404(mount_id)
    try:
        destination = resolve_mount_archive_destination(
            mount=mount,
            destination_path=destination_path,
        )
    except MountArchiveExtractionPreflightError as exc:
        if exc.public_code == "mount.path.not_a_folder":
            raise ValueError("Destination must be a folder.") from exc
        raise ValueError(exc.public_message) from exc
    provider = destination.provider
    dest_normalized = destination.normalized_destination_path

    set_mount_archive_extraction_job_status(
        job_id,
        {
            "state": "running",
            "progress": {
                "files_done": 0,
                "total": 0,
                "bytes_done": 0,
                "bytes_total": 0,
            },
            "skipped_symlinks_count": 0,
            "skipped_unsafe_paths_count": 0,
            "errors": [],
            "user_id": user_id,
            "mount_id": mount_id,
        },
    )

    try:
        remote_fp_ctx = safe_open_storage_for_read(default_storage, name=archive_item.file_key)
    except NotImplementedError:
        remote_fp_ctx = default_storage.open(archive_item.file_key, "rb")
    except UnsafeFilesystemPath as exc:
        raise ValueError(str(exc)) from exc

    with (
        remote_fp_ctx as remote_fp,
        tempfile.NamedTemporaryFile(
            prefix="drive-mount-archive-",
            suffix=os.path.splitext(archive_item.filename)[1],
        ) as local_fp,
    ):
        for chunk in iter(lambda: remote_fp.read(1024 * 1024), b""):
            local_fp.write(chunk)
        local_fp.flush()

        files_done = 0
        bytes_done = 0
        skipped_symlinks_count = 0
        skipped_unsafe_paths_count = 0

        def update_progress(*, total_files: int, total_bytes: int) -> None:
            set_mount_archive_extraction_job_status(
                job_id,
                {
                    "state": "running",
                    "progress": {
                        "files_done": files_done,
                        "total": total_files,
                        "bytes_done": bytes_done,
                        "bytes_total": total_bytes,
                    },
                    "skipped_symlinks_count": skipped_symlinks_count,
                    "skipped_unsafe_paths_count": skipped_unsafe_paths_count,
                    "errors": [],
                    "user_id": user_id,
                    "mount_id": mount_id,
                },
            )

        with zipfile.ZipFile(local_fp.name) as zf:
            plan = _plan_zip(zf, mode=mode, selection_paths=selection_paths)
            normalized_set = set(plan.paths)
            update_progress(total_files=plan.total_files, total_bytes=plan.total_bytes)

            for info in zf.infolist():
                if info.is_dir():
                    continue
                if _zipinfo_is_symlink(info):
                    skipped_symlinks_count += 1
                    continue

                try:
                    normalized = normalize_archive_path(info.filename).normalized
                except UnsafeArchivePath:
                    skipped_unsafe_paths_count += 1
                    continue

                if normalized not in normalized_set:
                    continue

                npath = normalize_archive_path(normalized)
                rel_parent = "/".join(npath.parent_parts)
                dest_folder = (
                    dest_normalized
                    if not rel_parent
                    else normalize_mount_path(posixpath.join(dest_normalized, rel_parent))
                )

                filename = npath.name
                dst_path = normalize_mount_path(posixpath.join(dest_folder, filename))
                tmp_path = normalize_mount_path(
                    posixpath.join(
                        dest_folder,
                        f".drive-extract-{safe_str_hash(dst_path) or uuid.uuid4().hex}.tmp",
                    )
                )

                existing = None
                try:
                    existing = provider.stat(mount=mount, normalized_path=dst_path)
                except MountProviderError as exc:
                    if exc.public_code != "mount.path.not_found":
                        raise

                if existing is not None:
                    if existing.entry_type != "file":
                        raise ValueError("Cannot overwrite a folder with a file.")
                    # Safe default: refuse on collision (explicit behavior can be added later).
                    raise ValueError("Target already exists.")

                with zf.open(info) as member_fp:
                    write_mount_stream_transaction(
                        provider=provider,
                        mount=mount,
                        temp_path=tmp_path,
                        final_path=dst_path,
                        chunks=iter_read_chunks(member_fp, chunk_size=1024 * 1024),
                        parent_path=dest_folder,
                    )

                files_done += 1
                bytes_done += int(info.file_size or 0)
                update_progress(total_files=plan.total_files, total_bytes=plan.total_bytes)

    final = {
        "state": "done",
        "progress": {
            "files_done": files_done,
            "total": plan.total_files,
            "bytes_done": bytes_done,
            "bytes_total": plan.total_bytes,
        },
        "skipped_symlinks_count": skipped_symlinks_count,
        "skipped_unsafe_paths_count": skipped_unsafe_paths_count,
        "errors": [],
        "user_id": user_id,
        "mount_id": mount_id,
    }
    set_mount_archive_extraction_job_status(job_id, final)
    logger.info("mount_archive_extract: done (job_id=%s mount_id=%s)", job_id, mount_id)
    return final
