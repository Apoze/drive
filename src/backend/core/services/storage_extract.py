"""Extract validated ZIP/TAR snapshots with the existing directory and file journals."""

import mimetypes
import posixpath
import tarfile
import uuid
import zipfile
from contextlib import ExitStack, contextmanager
from tempfile import SpooledTemporaryFile

from django.db import transaction

from rest_framework.exceptions import APIException, PermissionDenied

from core.archive.extract import (
    _filter_paths,
    _is_tar_filename,
    _plan_tar,
    _plan_zip,
    _zipinfo_is_symlink,
)
from core.archive.limits import (
    get_archive_extraction_limits,
    get_archive_extraction_max_archive_size,
)
from core.archive.security import normalize_archive_path
from core.models import StorageCopyEntry, StorageMoveJob
from core.services.mount_archive_extraction import (
    MountArchiveExtractionPreflightError,
    ensure_mount_archive_extract_hardening,
)
from core.services.storage_copy_job import execute_copy, validate_copy_name
from core.services.storage_folder_copy import _folder, _resolve
from core.services.storage_move_job import dispatch_move
from core.services.storage_namespace import StorageOperationBusy, advisory_guard, namespace_guard
from core.services.storage_quota import StorageWriteConflict
from wopi.conversion.backends.onlyoffice import SizedFile


def _ensure_hardening():
    try:
        ensure_mount_archive_extract_hardening()
    except MountArchiveExtractionPreflightError as exc:
        raise PermissionDenied(exc.public_message, code=exc.public_code) from exc


def enqueue_extraction(*, actor, source, destination, name, selection_paths=None):
    """Always publish into a new directory; an existing directory is never adopted."""
    try:
        for path in selection_paths or []:
            normalize_archive_path(path)
    except ValueError as exc:
        raise StorageWriteConflict("Choose valid archive entries.") from exc
    if source.kind != "file" or not (
        source.name.lower().endswith(".zip") or _is_tar_filename(source.name)
    ):
        raise StorageWriteConflict("Choose a ZIP or TAR archive.")
    if destination.backend.family == "mount":
        _ensure_hardening()
    job = StorageMoveJob.objects.create(
        actor=actor,
        kind="folder_copy",
        space=source.space,
        source_path=str(source.reference.pk),
        destination_path=str(destination.reference.pk),
        source_identity=str(source.reference.pk),
        payload={
            "extract": True,
            "selection_paths": selection_paths,
            "source": source.descriptor(),
            "destination": destination.descriptor(),
            "title": validate_copy_name(name),
            "destination_title": destination.name,
        },
    )
    transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


def _validate_zip_directory(stream):
    """Bound stdlib ZipFile's central-directory allocation, including ZIP64 archives."""
    # Reuse the interpreter's ZIP/ZIP64 footer parser; it reads at most 64 KiB.
    # pylint: disable=protected-access
    footer = zipfile._EndRecData(stream)  # noqa: SLF001
    if footer is None:
        raise zipfile.BadZipFile("Missing ZIP directory.")
    limits = get_archive_extraction_limits()
    if (
        footer[zipfile._ECD_ENTRIES_TOTAL] > limits.max_files  # noqa: SLF001
        or footer[zipfile._ECD_SIZE] > 32 * 1024**2  # noqa: SLF001
    ):
        raise StorageWriteConflict("ZIP directory exceeds its entry or metadata limit.")
    stream.seek(0)


def _members(archive, limits):
    if isinstance(archive, zipfile.ZipFile):
        rows = archive.infolist()
        if len(rows) > limits.max_files:
            raise StorageWriteConflict("Too many archive entries.")
        return rows
    rows, total = [], 0
    for member in archive:
        # Validate each TAR header before the iterator skips/decompresses its body.
        total += member.size
        if member.size < 0 or member.size > limits.max_file_size or total > limits.max_total_size:
            raise StorageWriteConflict("TAR data exceeds its extraction limit.")
        rows.append(member)
        if len(rows) > limits.max_files:
            raise StorageWriteConflict("Too many archive entries.")
    return rows


@contextmanager
def _archive(job, source):
    observed = job.payload.get("observation") or source.observe()
    if source.observe() != observed:
        raise StorageWriteConflict("The archive changed. Completed files were retained.")
    job.payload = {**job.payload, "observation": observed}
    job.save(update_fields=["payload", "updated_at"])
    maximum = get_archive_extraction_max_archive_size()
    if observed["size"] > maximum:
        raise StorageWriteConflict("The archive exceeds its size limit.")
    with SpooledTemporaryFile(max_size=8 * 1024**2) as spool, source.open(observed) as stream:
        size = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            if size > min(maximum, observed["size"]):
                raise StorageWriteConflict("The archive grew beyond its size limit.")
            spool.write(chunk)
        if size != observed["size"] or source.observe() != observed:
            raise StorageWriteConflict("The archive changed while reading.")
        spool.seek(0)
        if source.name.lower().endswith(".zip"):
            _validate_zip_directory(spool)
        with (
            zipfile.ZipFile(spool)
            if source.name.lower().endswith(".zip")
            else tarfile.open(fileobj=spool, mode="r:*")
        ) as archive:
            yield archive


def _plan(archive, selection_paths=None):
    """Validate the complete bounded manifest before creating any destination."""
    limits = get_archive_extraction_limits()
    is_zip = isinstance(archive, zipfile.ZipFile)
    members = [
        member
        for member in _members(archive, limits)
        if not (
            (member.filename if is_zip else member.name) in {".", "./"}
            and (member.is_dir() if is_zip else member.isdir())
        )
    ]
    (_plan_zip if is_zip else _plan_tar)(
        archive,
        mode="selection" if selection_paths else "all",
        selection_paths=selection_paths or [],
    )
    selected = {
        normalize_archive_path(raw).normalized
        for raw in _filter_paths(
            [member.filename if is_zip else member.name for member in members],
            mode="selection" if selection_paths else "all",
            selection_paths=selection_paths or [],
        )
    }
    selected.update(
        normalize_archive_path(path).normalized
        for path in selection_paths or []
        if path.endswith("/")
    )
    selected.update(
        {
            "/".join(path.split("/")[:index])
            for path in tuple(selected)
            for index in range(1, path.count("/") + 1)
        }
    )
    entries = {}
    for member in members:
        if (is_zip and _zipinfo_is_symlink(member)) or (
            not is_zip and not (member.isfile() or member.isdir())
        ):
            raise StorageWriteConflict("Archive links and special files cannot be extracted.")
        raw = member.filename if is_zip else member.name
        path = normalize_archive_path(raw)
        if path.depth > limits.max_depth or len(path.normalized) > limits.max_path_length:
            raise StorageWriteConflict("Archive path limit exceeded.")
        for part in path.parts:
            validate_copy_name(part)
        kind = "folder" if (member.is_dir() if is_zip else member.isdir()) else "file"
        if selection_paths and path.normalized not in selected:
            continue
        if path.normalized in entries and (
            entries[path.normalized][0] != "folder" or kind != "folder"
        ):
            raise StorageWriteConflict("The archive contains conflicting paths.")
        entries[path.normalized] = (kind, raw, int(member.file_size if is_zip else member.size))
        for index in range(1, len(path.parts)):
            parent = "/".join(path.parts[:index])
            if parent in entries and entries[parent][0] != "folder":
                raise StorageWriteConflict("An archive file is also used as a directory.")
            entries.setdefault(parent, ("folder", "", 0))
        if len(entries) > limits.max_files:
            raise StorageWriteConflict("Too many extracted entries.")
    return entries


def _index(job, archive):
    if job.payload.get("extract_indexed"):
        return
    entries = _plan(archive, job.payload.get("selection_paths"))
    # Index publication is atomic: no native writes occur before every member is validated.
    with transaction.atomic():
        job.copy_entries.all().delete()
        root = StorageCopyEntry.objects.create(
            job=job,
            source_id=uuid.uuid4(),
            source=job.payload["source"],
            kind="folder",
            name=job.payload["title"],
        )
        rows = {"": root}
        batch = []
        for path, (kind, raw, size) in sorted(
            entries.items(), key=lambda row: (row[0].count("/"), row[0])
        ):
            rows[path] = StorageCopyEntry(
                job=job,
                source_id=uuid.uuid4(),
                source=job.payload["source"],
                parent=rows[posixpath.dirname(path)],
                kind=kind,
                name=posixpath.basename(path),
                publication={"member": raw, "size": size},
            )
            batch.append(rows[path])
            if len(batch) == 100:
                StorageCopyEntry.objects.bulk_create(batch)
                batch.clear()
        StorageCopyEntry.objects.bulk_create(batch)
        job.payload = {**job.payload, "extract_indexed": True}
        job.save(update_fields=["payload", "updated_at"])


def _file(job, entry, target, archive):
    if not entry.child_job_id or (
        entry.child_job.state == "failed" and job.payload.get("retry_failed")
    ):
        with transaction.atomic():
            entry.child_job = StorageMoveJob.objects.create(
                actor=job.actor,
                kind="file_copy",
                space=job.space,
                source_path=job.source_path,
                destination_path=str(target.reference.pk),
                source_identity=job.source_identity,
                payload={
                    "source": job.payload["source"],
                    "destination": target.descriptor(),
                    "name": entry.name,
                    "title": entry.name,
                    "destination_title": target.name,
                    "copy_item": str(uuid.uuid4()),
                    "observation": job.payload["observation"],
                    "output_mimetype": mimetypes.guess_type(entry.name)[0]
                    or "application/octet-stream",
                    "extraction_parent": str(job.pk),
                    "parent_job": str(job.pk),
                },
            )
            entry.save(update_fields=["child_job", "updated_at"])
    with advisory_guard(f"storage-move:{entry.child_job_id}"):
        child = StorageMoveJob.objects.select_related("actor", "operation").get(
            pk=entry.child_job_id
        )
        if child.state in {"failed", "conflict"}:
            raise StorageWriteConflict(
                "An extracted file needs recovery; completed entries were retained."
            )
        if child.state != "done":
            with (
                archive.open(entry.publication["member"])
                if isinstance(archive, zipfile.ZipFile)
                else archive.extractfile(entry.publication["member"])
            ) as stream:
                outcome = execute_copy(
                    child,
                    provided_stream=SizedFile(
                        stream, name=entry.name, size=entry.publication["size"]
                    ),
                )
            if outcome != "done":
                return False
        child.refresh_from_db()
        entry.target_id, entry.done = child.payload["result"], True
        entry.save(update_fields=["target_id", "done", "updated_at"])
    return True


def execute_extraction(job):
    """Read one archive snapshot per bounded pass, never once for every member."""
    if job.state in {"done", "failed", "conflict"}:
        return job.state
    try:
        job.actor.refresh_from_db()
        source = _resolve(job.payload["source"], job.actor)
        destination = _resolve(job.payload["destination"], job.actor, destination=True)
        if destination.backend.family == "mount":
            _ensure_hardening()
        job.state, job.reason = "running", ""
        job.save(update_fields=["state", "reason", "updated_at"])
        with _archive(job, source) as archive, ExitStack() as guards:
            _index(job, archive)
            for backend in sorted(
                {source.backend, destination.backend}, key=lambda row: str(row.namespace)
            ):
                guards.enter_context(namespace_guard(backend, exclusive=True))
            for entry in (
                job.copy_entries.filter(done=False)
                .select_related("parent", "child_job")
                .order_by("created_at", "pk")[:20]
            ):
                if entry.parent_id:
                    entry.parent.refresh_from_db(fields=["publication"])
                target = (
                    _resolve(entry.parent.publication["target"], job.actor, destination=True)
                    if entry.parent_id
                    else destination
                )
                if entry.kind == "folder":
                    folder = _folder(entry, target, job.actor)
                    entry.publication = {**entry.publication, "target": folder.descriptor()}
                    entry.done = True
                    entry.save(update_fields=["publication", "done", "updated_at"])
                elif not _file(job, entry, target, archive):
                    return "more"
        if job.copy_entries.filter(done=False).exists():
            return "more"
        job.state = "done"
        job.payload = {
            **job.payload,
            "result": str(job.copy_entries.get(parent__isnull=True).target_id),
        }
        job.save(update_fields=["state", "payload", "updated_at"])
        return "done"
    except StorageOperationBusy:
        return "busy"
    except APIException as exc:
        job.state, job.reason = "conflict", str(exc.detail)[:255]
    except (ValueError, zipfile.BadZipFile, tarfile.TarError):
        job.state, job.reason = "conflict", "The archive is invalid or exceeds extraction limits."
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        job.state, job.reason = "running", "Storage unavailable; extraction will be retried."
    job.save(update_fields=["state", "reason", "updated_at"])
    return job.state
