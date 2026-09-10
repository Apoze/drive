"""Build bounded archive snapshots and publish them through the existing copy journal."""

import posixpath
import uuid
import zipfile
from contextlib import contextmanager
from tempfile import SpooledTemporaryFile

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from core.archive.limits import (
    get_archive_extraction_limits,
    get_archive_extraction_max_archive_size,
)
from core.archive.zip_create import _unique_entry_path
from core.models import DocsBinding, Item, StorageCopyEntry, StorageMoveJob
from core.services.item_exports import sanitize_archive_component
from core.services.storage_access import bound_queryset
from core.services.storage_copy_job import validate_copy_name
from core.services.storage_move_job import dispatch_move
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_resources import mounted_queryset
from core.services.storage_transfer_impact import transfer_impact
from core.services.storage_transfer_location import resolve_location
from wopi.conversion.backends.onlyoffice import SizedFile


def enqueue_archive(*, actor, sources, destination, name):
    """An archive is a new resource; its sources and their sharing remain untouched."""
    name = validate_copy_name(name)
    if not name.lower().endswith(".zip"):
        raise StorageWriteConflict("Choose a .zip archive name.")
    transfer_impact(sources, destination, actor, "copy")
    proof = None
    if settings.DOCS_DRIVE_ENABLED:
        from suite_identity.document_transport import actor_context  # noqa: PLC0415

        proof = actor_context(actor)
    job = StorageMoveJob.objects.create(
        actor=actor,
        kind="file_copy",
        space=sources[0].space,
        source_path=str(sources[0].reference.pk),
        destination_path=str(destination.reference.pk),
        source_identity=str(sources[0].reference.pk),
        payload={
            "title": name,
            "name": name,
            "destination_title": destination.name,
            "source": sources[0].descriptor(),
            "destination": destination.descriptor(),
            "archive_sources": [source.descriptor() for source in sources],
            "copy_item": str(uuid.uuid4()),
            "observation": {"mimetype": "application/zip"},
            "actor": proof,
        },
    )
    transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


def _resolve(descriptor, actor):
    current = resolve_location(descriptor["id"], actor, space_id=descriptor["space"])
    if current.descriptor() != descriptor:
        raise StorageWriteConflict("An archive source changed location. Start a new request.")
    return current


def _members(source, actor, limit):
    """Read only a bounded, authorized metadata subtree."""
    if source.kind == "file":
        yield source.reference
        return
    if source.backend.family == "s3" or source.kind == "docs":
        rows = bound_queryset(
            Item.objects.filter(
                path__descendants=source.reference.path,
                deleted_at__isnull=True,
                hard_deleted_at__isnull=True,
                ancestors_deleted_at__isnull=True,
            ),
            actor,
        ).select_related("storage_backend", "storage_space", "docs_binding__mounted_parent")
    else:
        rows = mounted_queryset(source.space, actor).filter(
            path__startswith=source.reference.path.rstrip("/") + "/"
        )
        yield source.reference
    if rows.count() > limit:
        raise StorageWriteConflict("Too many archive entries.")
    for row in rows.order_by("path").iterator(chunk_size=100):
        if isinstance(row, Item) and not row.get_abilities(actor).get("retrieve"):
            continue
        yield row
    if source.backend.family == "mount" and source.kind == "folder" and settings.DOCS_DRIVE_ENABLED:
        anchors = DocsBinding.objects.filter(
            Q(mounted_parent_id=source.reference.pk) | Q(mounted_parent__in=rows.values("pk")),
            item__path__ancestors=OuterRef("path"),
        )
        documents = (
            Item.objects.alias(anchored=Exists(anchors))
            .filter(
                anchored=True,
                type="docs",
                ancestors_deleted_at__isnull=True,
                hard_deleted_at__isnull=True,
            )
            .select_related("docs_binding__mounted_parent")
        )
        if rows.count() + documents.count() > limit:
            raise StorageWriteConflict("Too many archive entries.")
        for document in documents.order_by("path").iterator(chunk_size=100):
            if document.get_abilities(actor).get("export"):
                yield document


def archive_entries(descriptors, actor, *, contents_only=False):
    """Share one bounded manifest between downloads and durable transfer jobs."""
    limits = get_archive_extraction_limits()
    used, count, total = set(), 0, 0
    for descriptor in descriptors:
        root = _resolve(descriptor, actor)
        paths = {}
        for row in _members(root, actor, limits.max_files):
            count += 1
            if count > limits.max_files:
                raise StorageWriteConflict("Too many archive entries.")
            source = resolve_location(
                row.pk, actor, space_id=None if isinstance(row, Item) else root.space.pk
            )
            if row.pk == root.reference.pk:
                path = sanitize_archive_component(root.name)
            else:
                parent = (
                    row.docs_binding.mounted_parent.path
                    if isinstance(row, Item)
                    and row.type == "docs"
                    and row.docs_binding.mounted_parent_id
                    else str(row.path).rsplit(".", 1)[0]
                    if isinstance(row, Item)
                    else row.parent_path
                )
                if parent not in paths:
                    continue
                path = posixpath.join(
                    paths[parent],
                    sanitize_archive_component(row.title if isinstance(row, Item) else row.name),
                )
            if row.pk == root.reference.pk and contents_only:
                paths[str(row.path)] = ""
                continue
            path = _unique_entry_path(path, used)
            paths[str(row.path)] = path
            if source.kind == "docs":
                path = _unique_entry_path(path + ".pdf", used)
            if len(path) > limits.max_path_length or path.count("/") >= limits.max_depth:
                raise StorageWriteConflict("Archive path limit exceeded.")
            observed = source.observe() if source.kind in {"file", "docs"} else None
            size = observed["size"] if observed else 0
            total += size
            if size > limits.max_file_size or total > limits.max_total_size:
                raise StorageWriteConflict("Archive size limit exceeded.")
            yield StorageCopyEntry(
                source_id=row.pk,
                source=source.descriptor(),
                name=source.name,
                kind=source.kind,
                publication={"archive_path": path, "observation": observed},
            )


def _index(job):
    if job.payload.get("archive_indexed"):
        return
    job.copy_entries.all().delete()
    batch = []
    for entry in archive_entries(job.payload["archive_sources"], job.actor):
        entry.job = job
        batch.append(entry)
        if len(batch) == 100:
            StorageCopyEntry.objects.bulk_create(batch)
            batch.clear()
    StorageCopyEntry.objects.bulk_create(batch)
    job.payload = {**job.payload, "archive_indexed": True}
    job.save(update_fields=["payload", "updated_at"])


def check_archive_sources(job):
    """Check every captured permission, location and version before exposing the output."""
    job.actor.refresh_from_db()
    for descriptor in job.payload["archive_sources"]:
        _resolve(descriptor, job.actor)
    for entry in job.copy_entries.iterator(chunk_size=100):
        current = _resolve(entry.source, job.actor)
        if entry.kind in {"file", "docs"} and current.observe() != entry.publication["observation"]:
            raise StorageWriteConflict("An archive source changed. Its original was retained.")


@contextmanager
def archive_bytes(entries, actor, name, authorize=None, pdf_actor=None):
    """Spool a bounded mixed ZIP without exposing a partial export as a complete file."""
    limits = get_archive_extraction_limits()
    total = 0
    max_archive_size = get_archive_extraction_max_archive_size()
    with SpooledTemporaryFile(max_size=8 * 1024**2) as spool:
        with zipfile.ZipFile(
            spool, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
        ) as archive:
            for entry in entries:
                if authorize is not None:
                    authorize()
                actor.refresh_from_db()
                source = _resolve(entry.source, actor)
                path = entry.publication["archive_path"]
                if entry.kind == "folder":
                    archive.mkdir(path + "/")
                    continue
                observed = entry.publication["observation"]
                if source.observe() != observed:
                    raise StorageWriteConflict("An archive source changed before reading.")
                size = 0
                if entry.kind == "docs":
                    from suite_identity.document_transport import (  # noqa: PLC0415
                        actor_context,
                        pdf_stream,
                    )

                    reader = pdf_stream(
                        {
                            "document_id": str(source.reference.docs_binding.document_id),
                            "revision": observed["revision"],
                            "version": observed["version"],
                        },
                        actor=pdf_actor(source.reference) if pdf_actor else actor_context(actor),
                        limit=min(limits.max_file_size, 128 * 1024**2),
                    )
                else:
                    reader = source.open(observed)
                # Both streams close before yielding the completed spool.
                # pylint: disable-next=contextmanager-generator-missing-cleanup
                with (
                    reader as stream,
                    archive.open(path, "w", force_zip64=True) as output,
                ):
                    for chunk in iter(lambda stream=stream: stream.read(1024 * 1024), b""):
                        size += len(chunk)
                        total += len(chunk)
                        maximum = limits.max_file_size if entry.kind == "docs" else observed["size"]
                        if size > maximum or total > limits.max_total_size:
                            raise StorageWriteConflict("An archive source grew beyond its limit.")
                        output.write(chunk)
                        if spool.tell() > max_archive_size:
                            raise StorageWriteConflict("The output archive exceeds its size limit.")
                if (
                    entry.kind != "docs" and size != observed["size"]
                ) or source.observe() != observed:
                    raise StorageWriteConflict("An archive source changed while reading.")
        size = spool.tell()
        if size > max_archive_size:
            raise StorageWriteConflict("The output archive exceeds its size limit.")
        spool.seek(0)
        yield SizedFile(spool, name=name, size=size)


@contextmanager
def archive_source(job):
    """The native writer owns publication admission, checksum and recovery."""
    _index(job)
    entries = job.copy_entries.order_by("created_at", "pk").iterator(chunk_size=100)
    with archive_bytes(entries, job.actor, job.payload["name"]) as source:
        yield source


def folder_download(folder, actor, *, space_id=None, check_link=None, pdf_actor=None):
    """Download the same mixed manifest without creating a persistent copy job."""
    from urllib.parse import quote  # noqa: PLC0415

    from django.http import StreamingHttpResponse  # noqa: PLC0415

    from suite_identity.document_transport import actor_context  # noqa: PLC0415

    source = resolve_location(folder.pk, actor, space_id=space_id)
    descriptor = source.descriptor()
    name = sanitize_archive_component(source.name) + ".zip"
    # Streaming runs after request middleware has released its ContextVars.
    # Retain the verified proof now; the receiving service revalidates it.
    if pdf_actor is None:
        delegation = actor_context(actor)
        pdf_actor = lambda _document: delegation

    def authorize():
        if check_link is not None:
            check_link()
        _resolve(descriptor, actor)

    def stream():
        entries = archive_entries([descriptor], actor, contents_only=True)
        with archive_bytes(
            entries, actor, name, authorize=authorize, pdf_actor=pdf_actor
        ) as output:
            authorize()
            yield from iter(lambda: output.read(64 * 1024), b"")

    return StreamingHttpResponse(
        stream(),
        content_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name, safe='')}",
            "Cache-Control": "private, no-store",
        },
    )
