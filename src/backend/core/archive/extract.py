"""Archive extraction implementation (server-side)."""

from __future__ import annotations

import mimetypes
import os
import stat
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from logging import getLogger
from typing import Iterable, Literal

from django.core.cache import cache
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.db import transaction

from core import models
from core.archive.fs_safe import (
    UnsafeFilesystemPath,
    safe_open_storage_for_read,
    safe_write_fileobj_to_storage,
)
from core.archive.limits import get_archive_extraction_limits
from core.archive.security import UnsafeArchivePath, normalize_archive_path

logger = getLogger(__name__)

ArchiveMode = Literal["all", "selection"]
CollisionPolicy = Literal["rename", "skip", "overwrite"]


def _archive_fs_strict() -> bool:
    return str(os.environ.get("ARCHIVE_FS_STRICT", "")).lower() in {"1", "true", "yes"}


def archive_job_cache_key(job_id: str) -> str:
    """Cache key for an archive extraction job payload."""
    return f"archive_extraction_job:{job_id}"


def set_archive_extraction_job_status(
    job_id: str, payload: dict, ttl_seconds: int = 24 * 3600
) -> None:
    """Persist job status/progress payload in cache."""
    cache.set(archive_job_cache_key(job_id), payload, timeout=ttl_seconds)


def _get_job_status(job_id: str) -> dict | None:
    """Return cached job payload, if present."""
    return cache.get(archive_job_cache_key(job_id))


def _put_fileobj_to_default_storage(
    *, storage_key: str, fileobj, mimetype: str | None
) -> None:
    """Upload a file-like object to the configured default storage."""
    s3_client = getattr(getattr(default_storage, "connection", None), "meta", None)
    s3_client = getattr(s3_client, "client", None)
    bucket_name = getattr(default_storage, "bucket_name", None)
    if s3_client and bucket_name:
        s3_client.upload_fileobj(
            fileobj,
            bucket_name,
            storage_key,
            ExtraArgs={"ContentType": mimetype or "application/octet-stream"},
        )
        return

    # Local-path storage: enforce no-follow semantics to avoid symlink traversal on FS mounts.
    try:
        safe_write_fileobj_to_storage(
            default_storage, name=storage_key, fileobj=fileobj
        )
        return
    except NotImplementedError:
        pass
    except UnsafeFilesystemPath as exc:
        raise ValueError(str(exc)) from exc

    # Fallback: the default storage will stream `fileobj` when possible.
    default_storage.save(storage_key, File(fileobj))


def _is_tar_filename(filename: str) -> bool:
    """Return True if the filename looks like a tar (optionally compressed)."""
    lower = filename.lower()
    return (
        lower.endswith(".tar")
        or lower.endswith(".tar.gz")
        or lower.endswith(".tgz")
        or lower.endswith(".tar.bz2")
        or lower.endswith(".tbz")
        or lower.endswith(".tar.xz")
        or lower.endswith(".txz")
    )


def _is_zip_filename(filename: str) -> bool:
    """Return True if the filename looks like a zip."""
    return filename.lower().endswith(".zip")


def is_supported_archive_for_server_extraction(item: models.Item) -> bool:
    """Return True if this item can be extracted server-side."""
    if item.type != models.ItemTypeChoices.FILE or not item.filename:
        return False
    return _is_zip_filename(item.filename) or _is_tar_filename(item.filename)


@dataclass(frozen=True)
class ExtractionPlan:
    """Plan describing selected paths and expected totals for extraction."""

    paths: list[str]
    total_files: int
    total_bytes: int


def _selection_matchers(selection_paths: list[str]) -> tuple[set[str], list[str]]:
    """Prepare selection matchers for exact files and directory prefixes."""
    normalized_exact = set()
    normalized_prefixes: list[str] = []
    for p in selection_paths:
        is_dir = p.replace("\\", "/").endswith("/")
        n = normalize_archive_path(p).normalized
        if is_dir:
            normalized_prefixes.append(f"{n}/")
        else:
            normalized_exact.add(n)
    return normalized_exact, normalized_prefixes


def _filter_paths(
    paths: Iterable[str], *, mode: ArchiveMode, selection_paths: list[str]
) -> list[str]:
    """Filter raw archive paths based on the extraction mode."""
    if mode == "all":
        return list(paths)
    exact, prefixes = _selection_matchers(selection_paths)
    out = []
    for p in paths:
        try:
            n = normalize_archive_path(p).normalized
        except UnsafeArchivePath:
            continue
        if n in exact or any(n.startswith(prefix) for prefix in prefixes):
            out.append(p)
    return out


def _plan_zip(zf: zipfile.ZipFile, *, mode: ArchiveMode, selection_paths: list[str]):
    """Build a validated extraction plan for zip files."""
    limits = get_archive_extraction_limits()
    if _archive_fs_strict() and any(_zipinfo_is_symlink(i) for i in zf.infolist()):
        raise ValueError("Symlink entries are not allowed.")
    all_paths = [
        info.filename
        for info in zf.infolist()
        if not info.is_dir() and not _zipinfo_is_symlink(info)
    ]
    selected = _filter_paths(all_paths, mode=mode, selection_paths=selection_paths)

    total_files = 0
    total_bytes = 0
    normalized_paths: list[str] = []

    for raw in selected:
        n = normalize_archive_path(raw)
        if len(n.normalized) > limits.max_path_length:
            raise ValueError("Path too long.")
        if n.depth > limits.max_depth:
            raise ValueError("Path too deep.")
        info = zf.getinfo(raw)
        if _zipinfo_is_symlink(info):
            continue
        size = int(info.file_size or 0)
        if size > limits.max_file_size:
            raise ValueError("File too large.")
        if size > 0:
            compressed = int(getattr(info, "compress_size", 0) or 0)
            if compressed > 0 and (size / compressed) > limits.max_compression_ratio:
                raise ValueError("Suspicious compression ratio.")
        total_files += 1
        total_bytes += size
        normalized_paths.append(n.normalized)

    if total_files > limits.max_files:
        raise ValueError("Too many files.")
    if total_bytes > limits.max_total_size:
        raise ValueError("Archive too large to extract.")

    return ExtractionPlan(
        paths=normalized_paths, total_files=total_files, total_bytes=total_bytes
    )


def _plan_tar(tf: tarfile.TarFile, *, mode: ArchiveMode, selection_paths: list[str]):
    """Build a validated extraction plan for tar files."""
    limits = get_archive_extraction_limits()
    members = [m for m in tf.getmembers() if m.isfile()]
    all_paths = [m.name for m in members]
    selected = set(_filter_paths(all_paths, mode=mode, selection_paths=selection_paths))

    total_files = 0
    total_bytes = 0
    normalized_paths: list[str] = []
    for m in members:
        if m.name not in selected:
            continue
        n = normalize_archive_path(m.name)
        if len(n.normalized) > limits.max_path_length:
            raise ValueError("Path too long.")
        if n.depth > limits.max_depth:
            raise ValueError("Path too deep.")
        size = int(m.size or 0)
        if size > limits.max_file_size:
            raise ValueError("File too large.")
        total_files += 1
        total_bytes += size
        normalized_paths.append(n.normalized)

    if total_files > limits.max_files:
        raise ValueError("Too many files.")
    if total_bytes > limits.max_total_size:
        raise ValueError("Archive too large to extract.")

    return ExtractionPlan(
        paths=normalized_paths, total_files=total_files, total_bytes=total_bytes
    )


def _get_or_create_folder_child(
    *, parent: models.Item, creator: models.User, title: str, cache_map: dict
) -> models.Item:
    """Return a folder child (existing or newly created), cached per parent/title."""
    cache_key = (str(parent.id), title)
    if cache_key in cache_map:
        return cache_map[cache_key]

    existing = (
        models.Item.objects.children(parent.path)
        .filter(
            type=models.ItemTypeChoices.FOLDER,
            title=title,
            deleted_at__isnull=True,
            hard_deleted_at__isnull=True,
            ancestors_deleted_at__isnull=True,
        )
        .first()
    )
    if existing:
        cache_map[cache_key] = existing
        return existing

    folder = models.Item.objects.create_child(
        creator=creator,
        parent=parent,
        type=models.ItemTypeChoices.FOLDER,
        title=title,
    )
    cache_map[cache_key] = folder
    return folder


def _guess_mimetype(filename: str) -> str:
    """Guess mimetype from filename, falling back to octet-stream."""
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _zipinfo_is_symlink(info: zipfile.ZipInfo) -> bool:
    """
    Best-effort detection of symlink entries in zip files.

    Zip has no first-class type flag; on Unix, external attributes carry the mode.
    """

    mode = (int(getattr(info, "external_attr", 0)) >> 16) & 0o170000
    return mode == stat.S_IFLNK


def _get_existing_child(*, parent: models.Item, title: str) -> models.Item | None:
    """Return a non-deleted direct child with the given title, if any."""

    return (
        models.Item.objects.children(parent.path)
        .filter(
            title=title,
            deleted_at__isnull=True,
            hard_deleted_at__isnull=True,
            ancestors_deleted_at__isnull=True,
        )
        .first()
    )


def _default_root_folder_title(archive_item: models.Item) -> str:
    """Derive a safe root folder title from the archive filename/title."""

    raw = archive_item.title or archive_item.filename or "archive.zip"
    raw = str(raw).strip().replace("/", "_").replace("\\", "_")
    lower = raw.lower()
    if lower.endswith(".zip"):
        base = raw[: -len(".zip")]
    else:
        base, _ = os.path.splitext(raw)
    base = (base or "archive").strip()
    # Keep room for potential suffixes added by unique-title logic.
    return base[:240]


def extract_archive_to_drive(  # noqa: PLR0912,PLR0913,PLR0915
    *,
    job_id: str,
    archive_item_id: str,
    destination_folder_id: str,
    user_id: str,
    mode: ArchiveMode,
    selection_paths: list[str],
    collision_policy: CollisionPolicy = "rename",
    create_root_folder: bool = False,
) -> dict:
    """
    Extract an archive item into a destination folder.

    Security:
    - zip-slip/path traversal prevention via strict path normalization
    - bounded resource usage via limits (files count, sizes, depth, path length)
    - ignores symlinks/special files
    """
    # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements
    user = models.User.objects.get(pk=user_id)
    archive_item = models.Item.objects.get(pk=archive_item_id)
    destination = models.Item.objects.get(pk=destination_folder_id)

    if destination.type != models.ItemTypeChoices.FOLDER:
        raise ValueError("Destination must be a folder.")
    if archive_item.type != models.ItemTypeChoices.FILE or not archive_item.filename:
        raise ValueError("Archive item must be a file.")
    if not is_supported_archive_for_server_extraction(archive_item):
        raise ValueError("Unsupported archive format for server extraction.")

    if create_root_folder:
        title = _default_root_folder_title(archive_item)
        destination = models.Item.objects.create_child(
            creator=user,
            parent=destination,
            type=models.ItemTypeChoices.FOLDER,
            title=title,
        )

    set_archive_extraction_job_status(
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
        },
    )

    # Download archive to local disk (no full RAM usage).
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
            prefix="drive-archive-", suffix=os.path.splitext(archive_item.filename)[1]
        ) as local_fp,
    ):
        for chunk in iter(lambda: remote_fp.read(1024 * 1024), b""):
            local_fp.write(chunk)
        local_fp.flush()

        folder_cache: dict = {}
        files_done = 0
        bytes_done = 0
        skipped_symlinks_count = 0
        skipped_unsafe_paths_count = 0

        def update_progress(total_files: int, total_bytes: int):
            set_archive_extraction_job_status(
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
                },
            )

        if _is_zip_filename(archive_item.filename):
            with zipfile.ZipFile(local_fp.name) as zf:
                plan = _plan_zip(zf, mode=mode, selection_paths=selection_paths)
                update_progress(plan.total_files, plan.total_bytes)

                normalized_set = set(plan.paths)
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

                    parent_folder = destination
                    npath = normalize_archive_path(normalized)
                    skip_entry = False
                    for part in npath.parent_parts:
                        existing = _get_existing_child(parent=parent_folder, title=part)
                        if existing and existing.type != models.ItemTypeChoices.FOLDER:
                            if collision_policy == "rename":
                                parent_folder = _get_or_create_folder_child(
                                    parent=parent_folder,
                                    creator=user,
                                    title=part,
                                    cache_map=folder_cache,
                                )
                                continue
                            if collision_policy == "skip":
                                skip_entry = True
                                break
                            raise ValueError("Cannot overwrite a file with a folder.")
                        parent_folder = _get_or_create_folder_child(
                            parent=parent_folder,
                            creator=user,
                            title=part,
                            cache_map=folder_cache,
                        )
                    if skip_entry:
                        files_done += 1
                        bytes_done += int(info.file_size or 0)
                        update_progress(plan.total_files, plan.total_bytes)
                        continue

                    filename = npath.name
                    mimetype = _guess_mimetype(filename)

                    existing = _get_existing_child(parent=parent_folder, title=filename)
                    if existing:
                        if existing.type != models.ItemTypeChoices.FILE:
                            if collision_policy == "skip":
                                files_done += 1
                                bytes_done += int(info.file_size or 0)
                                update_progress(plan.total_files, plan.total_bytes)
                                continue
                            if collision_policy == "rename":
                                existing = None
                            else:
                                raise ValueError(
                                    "Cannot overwrite a folder with a file."
                                )

                    if existing and collision_policy == "skip":
                        files_done += 1
                        bytes_done += int(info.file_size or 0)
                        update_progress(plan.total_files, plan.total_bytes)
                        continue

                    if existing and collision_policy == "overwrite":
                        if not existing.filename:
                            raise ValueError("Existing file has no filename.")
                        with transaction.atomic(), zf.open(info) as member_fp:
                            _put_fileobj_to_default_storage(
                                storage_key=existing.file_key,
                                fileobj=member_fp,
                                mimetype=mimetype,
                            )
                            existing.upload_state = models.ItemUploadStateChoices.READY
                            existing.mimetype = mimetype
                            existing.size = int(info.file_size or 0)
                            existing.save(
                                update_fields=[
                                    "upload_state",
                                    "mimetype",
                                    "size",
                                    "updated_at",
                                ]
                            )
                        files_done += 1
                        bytes_done += int(info.file_size or 0)
                        update_progress(plan.total_files, plan.total_bytes)
                        continue

                    with transaction.atomic():
                        item = models.Item.objects.create_child(
                            creator=user,
                            parent=parent_folder,
                            type=models.ItemTypeChoices.FILE,
                            title=filename,
                            filename=filename,
                            mimetype=mimetype,
                        )

                        if item.filename != item.title:
                            item.filename = item.title
                            item.save(update_fields=["filename", "updated_at"])

                        with zf.open(info) as member_fp:
                            _put_fileobj_to_default_storage(
                                storage_key=item.file_key,
                                fileobj=member_fp,
                                mimetype=mimetype,
                            )

                        item.upload_state = models.ItemUploadStateChoices.READY
                        item.size = int(info.file_size or 0)
                        item.save(update_fields=["upload_state", "size"])

                    files_done += 1
                    bytes_done += int(info.file_size or 0)
                    update_progress(plan.total_files, plan.total_bytes)

        else:
            with tarfile.open(local_fp.name, mode="r:*") as tf:
                plan = _plan_tar(tf, mode=mode, selection_paths=selection_paths)
                update_progress(plan.total_files, plan.total_bytes)

                normalized_set = set(plan.paths)
                for member in tf.getmembers():
                    if not member.isfile():
                        continue
                    try:
                        normalized = normalize_archive_path(member.name).normalized
                    except UnsafeArchivePath:
                        skipped_unsafe_paths_count += 1
                        continue
                    if normalized not in normalized_set:
                        continue

                    parent_folder = destination
                    npath = normalize_archive_path(normalized)
                    skip_entry = False
                    for part in npath.parent_parts:
                        existing = _get_existing_child(parent=parent_folder, title=part)
                        if existing and existing.type != models.ItemTypeChoices.FOLDER:
                            if collision_policy == "rename":
                                parent_folder = _get_or_create_folder_child(
                                    parent=parent_folder,
                                    creator=user,
                                    title=part,
                                    cache_map=folder_cache,
                                )
                                continue
                            if collision_policy == "skip":
                                skip_entry = True
                                break
                            raise ValueError("Cannot overwrite a file with a folder.")
                        parent_folder = _get_or_create_folder_child(
                            parent=parent_folder,
                            creator=user,
                            title=part,
                            cache_map=folder_cache,
                        )
                    if skip_entry:
                        files_done += 1
                        bytes_done += int(member.size or 0)
                        update_progress(plan.total_files, plan.total_bytes)
                        continue

                    filename = npath.name
                    mimetype = _guess_mimetype(filename)

                    member_fp = tf.extractfile(member)
                    if member_fp is None:
                        raise ValueError("Could not read archive entry.")

                    existing = _get_existing_child(parent=parent_folder, title=filename)
                    if existing:
                        if existing.type != models.ItemTypeChoices.FILE:
                            if collision_policy == "skip":
                                with member_fp:
                                    pass
                                files_done += 1
                                bytes_done += int(member.size or 0)
                                update_progress(plan.total_files, plan.total_bytes)
                                continue
                            if collision_policy == "rename":
                                existing = None
                            else:
                                with member_fp:
                                    pass
                                raise ValueError(
                                    "Cannot overwrite a folder with a file."
                                )

                    if existing and collision_policy == "skip":
                        with member_fp:
                            pass
                        files_done += 1
                        bytes_done += int(member.size or 0)
                        update_progress(plan.total_files, plan.total_bytes)
                        continue

                    if existing and collision_policy == "overwrite":
                        if not existing.filename:
                            with member_fp:
                                pass
                            raise ValueError("Existing file has no filename.")
                        with transaction.atomic(), member_fp:
                            _put_fileobj_to_default_storage(
                                storage_key=existing.file_key,
                                fileobj=member_fp,
                                mimetype=mimetype,
                            )
                            existing.upload_state = models.ItemUploadStateChoices.READY
                            existing.mimetype = mimetype
                            existing.size = int(member.size or 0)
                            existing.save(
                                update_fields=[
                                    "upload_state",
                                    "mimetype",
                                    "size",
                                    "updated_at",
                                ]
                            )
                        files_done += 1
                        bytes_done += int(member.size or 0)
                        update_progress(plan.total_files, plan.total_bytes)
                        continue

                    with transaction.atomic():
                        item = models.Item.objects.create_child(
                            creator=user,
                            parent=parent_folder,
                            type=models.ItemTypeChoices.FILE,
                            title=filename,
                            filename=filename,
                            mimetype=mimetype,
                        )
                        if item.filename != item.title:
                            item.filename = item.title
                            item.save(update_fields=["filename", "updated_at"])

                        with member_fp:
                            _put_fileobj_to_default_storage(
                                storage_key=item.file_key,
                                fileobj=member_fp,
                                mimetype=mimetype,
                            )

                        item.upload_state = models.ItemUploadStateChoices.READY
                        item.size = int(member.size or 0)
                        item.save(update_fields=["upload_state", "size"])

                    files_done += 1
                    bytes_done += int(member.size or 0)
                    update_progress(plan.total_files, plan.total_bytes)

    final = {
        "state": "done",
        "progress": {
            "files_done": files_done,
            "total": plan.total_files if "plan" in locals() else files_done,
            "bytes_done": bytes_done,
            "bytes_total": plan.total_bytes if "plan" in locals() else bytes_done,
        },
        "skipped_symlinks_count": skipped_symlinks_count,
        "skipped_unsafe_paths_count": skipped_unsafe_paths_count,
        "errors": [],
        "user_id": user_id,
    }
    set_archive_extraction_job_status(job_id, final)
    logger.info(
        "archive_extract: done (job_id=%s archive_item_id=%s destination_folder_id=%s "
        "files=%s bytes=%s)",
        job_id,
        archive_item_id,
        destination_folder_id,
        files_done,
        bytes_done,
    )
    return final


def start_archive_extraction_job(  # noqa: PLR0913  # pylint: disable=too-many-arguments
    *,
    job_id: str,
    archive_item_id: str,
    destination_folder_id: str,
    user_id: str,
    mode: ArchiveMode,
    selection_paths: list[str],
    collision_policy: CollisionPolicy = "rename",
    create_root_folder: bool = False,
) -> str:
    """
    Create initial job cache entry.

    Celery tasks will update the cache for progress reporting.
    """
    set_archive_extraction_job_status(
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
            "archive_item_id": archive_item_id,
            "destination_folder_id": destination_folder_id,
            "user_id": user_id,
            "mode": mode,
            "selection_paths": selection_paths,
            "collision_policy": collision_policy,
            "create_root_folder": create_root_folder,
        },
    )
    return job_id


def get_archive_extraction_job_status(job_id: str) -> dict:
    """Return cached job payload or an 'unknown' placeholder."""
    return _get_job_status(job_id) or {
        "state": "unknown",
        "progress": {"files_done": 0, "total": 0, "bytes_done": 0, "bytes_total": 0},
        "skipped_symlinks_count": 0,
        "skipped_unsafe_paths_count": 0,
        "errors": [],
    }
