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
from core.mounts.paths import MountPathNormalizationError, normalize_mount_path
from core.mounts.providers.base import MountProviderError
from core.mounts.registry import get_mount_provider
from core.services.mount_security import (
    MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT_PUBLIC_MESSAGE,
    mounts_safe_for_archive_extract,
)
from core.utils.no_leak import safe_str_hash

logger = getLogger(__name__)


def mount_archive_job_cache_key(job_id: str) -> str:
    return f"mount_archive_extraction_job:{job_id}"


def set_mount_archive_extraction_job_status(
    job_id: str, payload: dict, ttl_seconds: int = 24 * 3600
) -> None:
    cache.set(mount_archive_job_cache_key(job_id), payload, timeout=ttl_seconds)


def get_mount_archive_extraction_job_status(job_id: str) -> dict:
    payload = cache.get(mount_archive_job_cache_key(job_id))
    return payload if isinstance(payload, dict) else {"state": "missing", "errors": []}


def start_mount_archive_extraction_job(
    *,
    job_id: str,
    archive_item_id: str,
    mount_id: str,
    destination_path: str,
    user_id: str,
    mode: str,
    selection_paths: list[str],
) -> None:
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


def extract_archive_to_mount(  # noqa: PLR0915
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

    if not mounts_safe_for_archive_extract():
        raise PermissionError(MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT_PUBLIC_MESSAGE)

    user = models.User.objects.get(pk=user_id)
    archive_item = models.Item.objects.get(pk=archive_item_id)

    if archive_item.type != models.ItemTypeChoices.FILE or not archive_item.filename:
        raise ValueError("Archive item must be a file.")
    if archive_item.effective_upload_state() != models.ItemUploadStateChoices.READY:
        raise ValueError("Item is not ready.")
    if archive_item.upload_state == models.ItemUploadStateChoices.SUSPICIOUS:
        raise PermissionError("Suspicious items cannot be extracted.")
    if not archive_item.get_abilities(user).get("retrieve", False):
        raise PermissionError("Not allowed.")

    if not _is_zip_filename(archive_item.filename):
        raise ValueError("Unsupported archive format for mount extraction.")

    max_archive_size = get_archive_extraction_max_archive_size()
    if archive_item.size is not None and int(archive_item.size) > int(max_archive_size):
        raise ValueError("Archive is too large to extract.")

    mount = _get_enabled_mount_or_404(mount_id)
    provider = get_mount_provider(str(mount.get("provider") or ""))

    required = ("stat", "open_write", "rename", "remove", "mkdirs")
    if not all(hasattr(provider, name) for name in required):
        raise ValueError("Extraction is not available for this mount.")

    try:
        dest_normalized = normalize_mount_path(destination_path)
    except MountPathNormalizationError as exc:
        raise ValueError("Invalid mount path.") from exc

    dest_entry = provider.stat(mount=mount, normalized_path=dest_normalized)
    if dest_entry.entry_type != "folder":
        raise ValueError("Destination must be a folder.")

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
        remote_fp_ctx = safe_open_storage_for_read(
            default_storage, name=archive_item.file_key
        )
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

                # Create parent directories (provider-defined semantics).
                provider.mkdirs(mount=mount, normalized_path=dest_folder)

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

                try:
                    with zf.open(info) as member_fp, provider.open_write(
                        mount=mount, normalized_path=tmp_path
                    ) as out_fp:
                        for chunk in iter(lambda: member_fp.read(1024 * 1024), b""):
                            out_fp.write(chunk)
                    provider.rename(
                        mount=mount,
                        src_normalized_path=tmp_path,
                        dst_normalized_path=dst_path,
                    )
                except Exception:
                    try:
                        provider.remove(mount=mount, normalized_path=tmp_path)
                    except Exception:  # noqa: BLE001
                        pass
                    raise

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

