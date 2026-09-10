"""Services for exporting regular Drive folders as streaming ZIP archives."""

import logging
import posixpath
import re
from collections.abc import Iterable, Iterator
from contextlib import closing

from django.core.files.storage import default_storage  # noqa: F401  # pylint: disable=unused-import

from zipstream import ZipStream

from core import models
from core.services.storage_connections import storage_for_key
from core.utils.no_leak import safe_str_hash

logger = logging.getLogger(__name__)

DEFAULT_STORAGE_READ_CHUNK_SIZE = 64 * 1024
ARCHIVE_COMPONENT_FALLBACK = "item"
UNSAFE_ARCHIVE_COMPONENT_CHARS = re.compile(r"[\x00-\x1f\x7f/\\]+")

ExportEntry = tuple[str | models.Item | None, str]


def sanitize_archive_component(value: str | None) -> str:
    """Return a safe single ZIP path component."""
    candidate = UNSAFE_ARCHIVE_COMPONENT_CHARS.sub("_", value or "").strip(" .")
    if not candidate or candidate in {".", ".."} or not candidate.strip("_"):
        return ARCHIVE_COMPONENT_FALLBACK
    return candidate


def iter_storage_chunks(
    file_key: str,
    chunk_size: int = DEFAULT_STORAGE_READ_CHUNK_SIZE,
    user=None,
    authorize=None,
) -> Iterator[bytes]:
    """Yield bytes from S3-compatible object storage without full-file buffering."""
    if authorize is not None:
        authorize()
    if user is not None:
        # pylint: disable=import-outside-toplevel,cyclic-import
        from rest_framework.exceptions import PermissionDenied  # noqa: PLC0415

        from core.services.storage_connections import item_for_key  # noqa: PLC0415

        if user.is_authenticated:
            user.refresh_from_db()
        item = item_for_key(file_key)
        if not item.get_abilities(user).get("retrieve") or item.effective_upload_state() != "ready":
            raise PermissionDenied()
    s3_client = storage_for_key(file_key).connection.meta.client
    bucket_name = storage_for_key(file_key).bucket_name

    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    except s3_client.exceptions.NoSuchKey:
        logger.warning(
            "Export: referenced object is missing from storage; key_hash=%s",
            safe_str_hash(file_key),
        )
        return

    with closing(response["Body"]) as body:
        yield from body.iter_chunks(chunk_size)


def export_descendants(folder: models.Item, user=None) -> Iterator[ExportEntry]:
    """
    Yield storage keys and sanitized ZIP paths for a regular folder subtree.

    Deleted descendants are skipped. Folders are emitted as directory entries
    and only files in the READY upload state are emitted as file entries.
    """
    from core.archive.zip_create import _unique_entry_path  # noqa: PLC0415

    descendants = folder.descendants().filter(ancestors_deleted_at__isnull=True).order_by("path")

    if user is not None:
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_access import bound_queryset  # noqa: PLC0415

        descendants = bound_queryset(descendants, user)
    relative_paths = {str(folder.path): ""}
    used = set()
    for descendant in descendants.iterator(chunk_size=100):
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
        relative = _unique_entry_path(relative, used)
        relative_paths[str(descendant.path)] = relative

        if descendant.type == models.ItemTypeChoices.FOLDER:
            yield None, f"{relative}/"
        elif descendant.type == "docs":
            yield descendant, _unique_entry_path(f"{relative}.pdf", used)
        elif descendant.upload_state == models.ItemUploadStateChoices.READY:
            yield descendant.file_key, relative


def capture_document_actor(item, user, document_context):
    """Capture request proof before streaming middleware releases its context."""
    from django.contrib.auth.models import AnonymousUser  # noqa: PLC0415

    from suite_identity.document_transport import actor_context, document_links  # noqa: PLC0415

    token = (
        document_links.set({str(item.docs_binding.document_id): document_context})
        if document_context
        else None
    )
    try:
        return actor_context(user or AnonymousUser())
    finally:
        if token is not None:
            document_links.reset(token)


def iter_document_pdf(item, actor, *, authorize=None):
    """Read a versioned PDF under the real caller or an explicitly supplied bearer."""
    from suite_identity.document_transport import pdf_stream  # noqa: PLC0415

    from core.archive.limits import get_archive_extraction_limits  # noqa: PLC0415

    if authorize is not None:
        authorize()
    binding = item.docs_binding
    with pdf_stream(
        {
            "document_id": str(binding.document_id),
            "revision": binding.revision,
            "version": item.storageusage.version,
        },
        actor=actor,
        limit=min(get_archive_extraction_limits().max_file_size, 128 * 1024**2),
    ) as source:
        if authorize is not None:
            authorize()
        yield from iter(lambda: source.read(DEFAULT_STORAGE_READ_CHUNK_SIZE), b"")


def build_zip_stream(
    descendants: Iterable[ExportEntry], user=None, authorize=None, document_context=None
) -> ZipStream:
    """Build a ZIP stream that lazily reads exported files from storage."""
    # pylint: disable=import-outside-toplevel,cyclic-import
    from rest_framework.exceptions import ValidationError  # noqa: PLC0415

    from core.archive.limits import get_archive_extraction_limits  # noqa: PLC0415

    limits = get_archive_extraction_limits()
    zip_stream = ZipStream(sized=False)
    for index, (file_key, archive_path) in enumerate(descendants):
        if index >= limits.max_files or len(archive_path) > limits.max_path_length:
            raise ValidationError("The archive exceeds its entry or path limit.")
        if file_key is None:
            zip_stream.mkdir(archive_path)
        elif isinstance(file_key, models.Item):
            zip_stream.add(
                data=iter_document_pdf(
                    file_key,
                    capture_document_actor(file_key, user, document_context),
                    authorize=authorize,
                ),
                arcname=archive_path,
            )
        else:
            zip_stream.add(
                data=iter_storage_chunks(file_key, user=user, authorize=authorize),
                arcname=archive_path,
            )
    return zip_stream


# The HTTP generator retains its bounded reader until completion or disconnect.
# pylint: disable-next=too-many-statements
def native_folder_export(folder, space, actor, authorize=None):  # noqa: PLR0915
    """Stream an authorized index subtree, with bounded ZIP metadata and native reads."""
    # pylint: disable=import-outside-toplevel,cyclic-import
    from urllib.parse import quote  # noqa: PLC0415

    from django.conf import settings  # noqa: PLC0415
    from django.http import StreamingHttpResponse  # noqa: PLC0415

    from rest_framework.exceptions import ValidationError  # noqa: PLC0415

    from core.archive.limits import get_archive_extraction_limits  # noqa: PLC0415
    from core.archive.zip_create import _unique_entry_path  # noqa: PLC0415
    from core.services.storage_quota import StorageWriteConflict  # noqa: PLC0415
    from core.services.storage_resources import mounted_queryset  # noqa: PLC0415
    from core.services.storage_transfer_location import resolve_location  # noqa: PLC0415

    if settings.DOCS_DRIVE_ENABLED and authorize is None:
        from core.services.storage_archive import folder_download  # noqa: PLC0415

        return folder_download(folder, actor, space_id=space.pk)
    limits = get_archive_extraction_limits()
    prefix = folder.path.rstrip("/") + "/"
    entries = mounted_queryset(space, actor).filter(path__startswith=prefix).order_by("path")
    if folder.kind != "folder" or entries.count() > limits.max_files:
        raise ValidationError("Select a folder within the archive entry limit.")

    def stream():
        archive = ZipStream(sized=False)
        used = set()
        paths = {folder.path.rstrip("/") or "/": ""}
        if authorize is not None:
            authorize()
        for index, entry in enumerate(entries.iterator(chunk_size=100)):
            if authorize is not None:
                authorize()
            if index >= limits.max_files:
                raise StorageWriteConflict("The folder grew beyond the archive entry limit.")
            actor.refresh_from_db()
            current_root = resolve_location(folder.pk, actor, space_id=space.pk)
            current = resolve_location(entry.pk, actor, space_id=space.pk)
            if current_root.reference.path != folder.path or current.reference.path != entry.path:
                raise StorageWriteConflict("The exported folder changed. Please retry.")
            parent = paths.get(entry.parent_path)
            if parent is None:
                continue
            path = _unique_entry_path(
                posixpath.join(parent, sanitize_archive_component(entry.name)), used
            )
            paths[entry.path] = path
            if len(path) > limits.max_path_length or path.count("/") >= limits.max_depth:
                raise StorageWriteConflict("An archive path exceeds the configured limits.")
            if entry.kind == "folder":
                archive.mkdir(path + "/")
                yield from archive.file()
                continue
            observed = current.observe()
            # StreamingHttpResponse closes this generator on disconnect.
            # pylint: disable-next=contextmanager-generator-missing-cleanup
            with current.open(observed) as source:

                def chunks(expected_size=observed["size"], source=source):
                    size = 0
                    for chunk in iter(lambda: source.read(DEFAULT_STORAGE_READ_CHUNK_SIZE), b""):
                        size += len(chunk)
                        if size > expected_size:
                            raise StorageWriteConflict("The source grew during export.")
                        yield chunk
                    if size != expected_size:
                        raise StorageWriteConflict("The source shrank during export.")

                archive.add(chunks(), path)
                yield from archive.file()
            if current.observe() != observed:
                raise StorageWriteConflict("A source changed during export. Please retry.")
        yield from archive.finalize()

    filename = quote(sanitize_archive_component(folder.name) + ".zip", safe="")
    return StreamingHttpResponse(
        stream(),
        content_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Cache-Control": "private, no-store",
        },
    )
