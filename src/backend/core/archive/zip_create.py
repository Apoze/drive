"""Archive zip creation implementation (server-side)."""

from __future__ import annotations

import os
import posixpath
import tempfile
import zipfile
from logging import getLogger

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db import transaction

from core import models
from core.archive.extract import _put_fileobj_to_default_storage
from core.archive.fs_safe import (
    UnsafeFilesystemPath,
    UnsupportedFilesystemSafety,
    safe_open_storage_for_read,
)
from core.archive.limits import get_archive_extraction_limits

logger = getLogger(__name__)


def _archive_fs_strict() -> bool:
    return str(os.environ.get("ARCHIVE_FS_STRICT", "")).lower() in {"1", "true", "yes"}


def _source_storage_key_is_safe_to_read(*, storage, key: str, strict: bool) -> bool:
    """
    Return True if `key` can be read without following symlinks (for local-path storages).

    - For non-local storages (no `storage.path()`), return True (unchanged behavior).
    - For local storages, refuse symlink components. In strict mode, raise.
    """

    try:
        fp = safe_open_storage_for_read(storage, name=key)
    except NotImplementedError:
        return True
    except UnsupportedFilesystemSafety:
        # Fail closed even in non-strict mode: we cannot guarantee no-follow semantics.
        raise
    except UnsafeFilesystemPath:
        if strict:
            raise
        return False
    else:
        fp.close()
        return True


def archive_zip_job_cache_key(job_id: str) -> str:
    """Cache key for an archive zip job payload."""

    return f"archive_zip_job:{job_id}"


def set_archive_zip_job_status(
    job_id: str, payload: dict, ttl_seconds: int = 24 * 3600
):
    """Persist job status/progress payload in cache."""

    cache.set(archive_zip_job_cache_key(job_id), payload, timeout=ttl_seconds)


def _get_job_status(job_id: str) -> dict | None:
    """Return cached job payload, if present."""

    return cache.get(archive_zip_job_cache_key(job_id))


def start_archive_zip_job(
    *,
    job_id: str,
    source_item_ids: list[str],
    destination_folder_id: str,
    user_id: str,
    archive_name: str,
) -> str:
    """Create initial job cache entry."""

    set_archive_zip_job_status(
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
            "source_item_ids": source_item_ids,
            "destination_folder_id": destination_folder_id,
            "archive_name": archive_name,
            "user_id": user_id,
        },
    )
    return job_id


def get_archive_zip_job_status(job_id: str) -> dict:
    """Return cached job payload or an 'unknown' placeholder."""

    return _get_job_status(job_id) or {
        "state": "unknown",
        "progress": {"files_done": 0, "total": 0, "bytes_done": 0, "bytes_total": 0},
        "skipped_symlinks_count": 0,
        "skipped_unsafe_paths_count": 0,
        "errors": [],
    }


def _safe_component(name: str) -> str:
    """Sanitize a single path component for inclusion in a zip."""

    name = (name or "").strip()
    name = name.replace("/", "_").replace("\\", "_")
    return name or "_"


def _unique_entry_path(entry_path: str, used_paths: set[str]) -> str:
    """Ensure `entry_path` is unique within a zip archive."""

    if entry_path not in used_paths:
        used_paths.add(entry_path)
        return entry_path

    folder, name = posixpath.split(entry_path)
    stem, ext = os.path.splitext(name)
    counter = 1
    while True:
        candidate_name = f"{stem}_{counter:02d}{ext}"
        candidate = posixpath.join(folder, candidate_name) if folder else candidate_name
        if candidate not in used_paths:
            used_paths.add(candidate)
            return candidate
        counter += 1


def _iter_zip_entries_for_item(
    *, root: models.Item, user: models.User
) -> list[tuple[models.Item, str]]:
    """Return (file_item, archive_entry_path) for a selected root item."""

    if root.type == models.ItemTypeChoices.FILE:
        name = _safe_component(root.filename or root.title)
        return [(root, name)]

    if root.type != models.ItemTypeChoices.FOLDER:
        return []

    descendants = list(
        models.Item.objects.filter(path__descendants=root.path)
        .filter(
            deleted_at__isnull=True,
            hard_deleted_at__isnull=True,
            ancestors_deleted_at__isnull=True,
        )
        .only(
            "id",
            "path",
            "type",
            "title",
            "filename",
            "upload_state",
            "size",
            "mimetype",
        )
    )

    by_id: dict[str, models.Item] = {str(i.id): i for i in descendants}
    by_id[str(root.id)] = root

    base_parts = str(root.path).split(".")
    prefix = _safe_component(root.title)

    out: list[tuple[models.Item, str]] = []
    for item in descendants:
        if item.type != models.ItemTypeChoices.FILE:
            continue
        if not item.get_abilities(user).get("retrieve", False):
            continue
        parts = str(item.path).split(".")
        if parts[: len(base_parts)] != base_parts:
            continue
        rel_ids = parts[len(base_parts) :]
        rel_components: list[str] = []
        for seg_id in rel_ids:
            seg_item = by_id.get(seg_id)
            if not seg_item:
                raise ValueError("Could not resolve archive path component.")
            rel_components.append(_safe_component(seg_item.title))
        out.append((item, posixpath.join(prefix, *rel_components)))
    return out


def create_zip_from_items(  # noqa: PLR0912,PLR0915  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    *,
    job_id: str,
    source_item_ids: list[str],
    destination_folder_id: str,
    user_id: str,
    archive_name: str,
) -> dict:
    """Create a zip archive from the selected items into the destination folder."""

    user = models.User.objects.get(pk=user_id)
    limits = get_archive_extraction_limits()
    destination = models.Item.objects.get(pk=destination_folder_id)
    if destination.type != models.ItemTypeChoices.FOLDER:
        raise ValueError("Destination must be a folder.")

    sources = list(
        models.Item.objects.filter(id__in=source_item_ids)
        .filter(
            deleted_at__isnull=True,
            hard_deleted_at__isnull=True,
            ancestors_deleted_at__isnull=True,
        )
        .only(
            "id",
            "path",
            "type",
            "title",
            "filename",
            "upload_state",
            "size",
            "mimetype",
        )
    )
    if len(sources) != len(set(source_item_ids)):
        raise ValueError("Some source items are missing or not readable.")

    for item in sources:
        if not item.get_abilities(user).get("retrieve", False):
            raise ValueError("Not allowed to read one of the selected items.")
        if item.type == models.ItemTypeChoices.FILE:
            if item.effective_upload_state() != models.ItemUploadStateChoices.READY:
                raise ValueError("A selected file is not ready.")
            if item.upload_state == models.ItemUploadStateChoices.SUSPICIOUS:
                raise ValueError("Suspicious items cannot be compressed.")

    used_paths: set[str] = set()
    entries: list[tuple[models.Item, str]] = []
    for root in sources:
        for file_item, entry_path in _iter_zip_entries_for_item(root=root, user=user):
            if (
                file_item.effective_upload_state()
                != models.ItemUploadStateChoices.READY
            ):
                raise ValueError("A source file is not ready.")
            if file_item.upload_state == models.ItemUploadStateChoices.SUSPICIOUS:
                raise ValueError("Suspicious items cannot be compressed.")
            unique_entry_path = _unique_entry_path(entry_path, used_paths)
            if len(unique_entry_path) > limits.max_path_length:
                raise ValueError("Path too long.")
            if unique_entry_path.count("/") + 1 > limits.max_depth:
                raise ValueError("Path too deep.")
            entries.append((file_item, unique_entry_path))

    # If the storage is filesystem-backed, refuse/skip unsafe source paths (symlinks in components).
    safe_entries: list[tuple[models.Item, str]] = []
    skipped_unsafe_paths_count = 0
    for file_item, entry_path in entries:
        try:
            ok = _source_storage_key_is_safe_to_read(
                storage=default_storage,
                key=file_item.file_key,
                strict=_archive_fs_strict(),
            )
        except UnsafeFilesystemPath as exc:
            raise ValueError(str(exc)) from exc
        if not ok:
            skipped_unsafe_paths_count += 1
            continue
        safe_entries.append((file_item, entry_path))

    entries = safe_entries

    if len(entries) > limits.max_files:
        raise ValueError("Too many files.")

    def _effective_size(item: models.Item) -> int:
        if item.size is not None:
            return int(item.size)
        if not item.filename:
            raise ValueError("Source file has no filename.")
        return int(default_storage.size(item.file_key))

    total_bytes = 0
    for file_item, _ in entries:
        size = _effective_size(file_item)
        if size > limits.max_file_size:
            raise ValueError("File too large.")
        total_bytes += size
        if total_bytes > limits.max_total_size:
            raise ValueError("Archive too large to create.")

    set_archive_zip_job_status(
        job_id,
        {
            "state": "running",
            "progress": {
                "files_done": 0,
                "total": len(entries),
                "bytes_done": 0,
                "bytes_total": total_bytes,
            },
            "skipped_symlinks_count": 0,
            "skipped_unsafe_paths_count": skipped_unsafe_paths_count,
            "errors": [],
            "user_id": user_id,
        },
    )

    files_done = 0
    bytes_done = 0

    def _update_progress():
        set_archive_zip_job_status(
            job_id,
            {
                "state": "running",
                "progress": {
                    "files_done": files_done,
                    "total": len(entries),
                    "bytes_done": bytes_done,
                    "bytes_total": total_bytes,
                },
                "skipped_symlinks_count": 0,
                "skipped_unsafe_paths_count": skipped_unsafe_paths_count,
                "errors": [],
                "user_id": user_id,
            },
        )

    with tempfile.NamedTemporaryFile(prefix="drive-zip-", suffix=".zip") as tmp:
        with zipfile.ZipFile(
            tmp.name, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
        ) as zf:
            for file_item, entry_path in entries:
                try:
                    in_fp_ctx = safe_open_storage_for_read(
                        default_storage, name=file_item.file_key
                    )
                except NotImplementedError:
                    in_fp_ctx = default_storage.open(file_item.file_key, "rb")
                except UnsafeFilesystemPath as exc:
                    raise ValueError(str(exc)) from exc

                with in_fp_ctx as in_fp, zf.open(entry_path, mode="w") as out_fp:
                    bytes_this_file = 0
                    while True:
                        chunk = in_fp.read(1024 * 1024)
                        if not chunk:
                            break
                        out_fp.write(chunk)
                        bytes_this_file += len(chunk)
                        if bytes_this_file > limits.max_file_size:
                            raise ValueError("File too large.")
                        if bytes_done + bytes_this_file > limits.max_total_size:
                            raise ValueError("Archive too large to create.")

                files_done += 1
                bytes_done += bytes_this_file
                _update_progress()

        tmp.flush()

        with transaction.atomic():
            item = models.Item.objects.create_child(
                creator=user,
                parent=destination,
                type=models.ItemTypeChoices.FILE,
                title=archive_name,
                filename=archive_name,
                mimetype="application/zip",
                upload_state=models.ItemUploadStateChoices.PENDING,
            )
            if item.filename != item.title:
                item.filename = item.title
                item.save(update_fields=["filename", "updated_at"])

            with open(tmp.name, "rb") as fp:
                _put_fileobj_to_default_storage(
                    storage_key=item.file_key,
                    fileobj=fp,
                    mimetype="application/zip",
                )

            item.upload_state = models.ItemUploadStateChoices.READY
            item.size = int(os.path.getsize(tmp.name))
            item.save(update_fields=["upload_state", "size", "updated_at"])

    final = {
        "state": "done",
        "progress": {
            "files_done": files_done,
            "total": len(entries),
            "bytes_done": bytes_done,
            "bytes_total": total_bytes,
        },
        "skipped_symlinks_count": 0,
        "skipped_unsafe_paths_count": skipped_unsafe_paths_count,
        "errors": [],
        "user_id": user_id,
        "result_item_id": str(item.id),
    }
    set_archive_zip_job_status(job_id, final)
    logger.info(
        "archive_zip: done (job_id=%s destination_folder_id=%s files=%s bytes=%s)",
        job_id,
        destination_folder_id,
        files_done,
        bytes_done,
    )
    return final
