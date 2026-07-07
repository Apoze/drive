"""Services for exporting regular Drive folders as streaming ZIP archives."""

import logging
import re
from collections.abc import Iterable, Iterator

from django.core.files.storage import default_storage

from zipstream import ZipStream

from core import models
from core.utils.no_leak import safe_str_hash

logger = logging.getLogger(__name__)

DEFAULT_STORAGE_READ_CHUNK_SIZE = 64 * 1024
ARCHIVE_COMPONENT_FALLBACK = "item"
UNSAFE_ARCHIVE_COMPONENT_CHARS = re.compile(r"[\x00-\x1f\x7f/\\]+")

ExportEntry = tuple[str | None, str]


def sanitize_archive_component(value: str | None) -> str:
    """Return a safe single ZIP path component."""
    candidate = UNSAFE_ARCHIVE_COMPONENT_CHARS.sub("_", value or "").strip(" .")
    if not candidate or candidate in {".", ".."} or not candidate.strip("_"):
        return ARCHIVE_COMPONENT_FALLBACK
    return candidate


def iter_storage_chunks(
    file_key: str,
    chunk_size: int = DEFAULT_STORAGE_READ_CHUNK_SIZE,
) -> Iterator[bytes]:
    """Yield bytes from S3-compatible object storage without full-file buffering."""
    s3_client = default_storage.connection.meta.client
    bucket_name = default_storage.bucket_name

    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    except s3_client.exceptions.NoSuchKey:
        logger.warning(
            "Export: referenced object is missing from storage; key_hash=%s",
            safe_str_hash(file_key),
        )
        return

    yield from response["Body"].iter_chunks(chunk_size)


def export_descendants(folder: models.Item) -> Iterator[ExportEntry]:
    """
    Yield storage keys and sanitized ZIP paths for a regular folder subtree.

    Deleted descendants are skipped. Folders are emitted as directory entries
    and only files in the READY upload state are emitted as file entries.
    """
    descendants = folder.descendants().filter(ancestors_deleted_at__isnull=True).order_by("path")

    relative_paths = {str(folder.path): ""}
    for descendant in descendants:
        parent_key = str(descendant.path).rsplit(".", 1)[0]
        parent_relative = relative_paths.get(parent_key)
        if parent_relative is None:
            continue

        name = (
            descendant.filename
            if descendant.type == models.ItemTypeChoices.FILE
            else descendant.title
        )
        safe_name = sanitize_archive_component(name)
        relative = f"{parent_relative}/{safe_name}" if parent_relative else safe_name
        relative_paths[str(descendant.path)] = relative

        if descendant.type == models.ItemTypeChoices.FOLDER:
            yield None, f"{relative}/"
        elif descendant.upload_state == models.ItemUploadStateChoices.READY:
            yield descendant.file_key, relative


def build_zip_stream(descendants: Iterable[ExportEntry]) -> ZipStream:
    """Build a ZIP stream that lazily reads exported files from storage."""
    zip_stream = ZipStream(sized=False)
    for file_key, archive_path in descendants:
        if file_key is None:
            zip_stream.mkdir(archive_path)
        else:
            zip_stream.add(data=iter_storage_chunks(file_key), arcname=archive_path)
    return zip_stream
