"""Durable copies between native filesystem spaces and regular S3 locations."""

import posixpath
import uuid
from contextlib import ExitStack, nullcontext

from django.db import transaction
from django.utils import timezone

from botocore.exceptions import ClientError
from lasuite.malware_detection import malware_detection
from rest_framework.exceptions import APIException

from core.malware_detection import analysis_kwargs
from core.models import Item, StorageBackend, StorageMoveJob, StorageResource
from core.mounts.providers import virtual
from core.mounts.providers.base import MountProviderError
from core.services import storage_quota as quota
from core.services.mount_write_transaction import MountWriteLimits
from core.services.s3_streaming import stream_to_s3_object
from core.services.storage_connections import storage_for_item
from core.services.storage_integrity import DigestReader
from core.services.storage_move_job import dispatch_move
from core.services.storage_namespace import StorageOperationBusy, namespace_guard
from core.services.storage_recovery import _reconcile_mount, _reconcile_s3, cleanup_operation
from core.services.storage_s3_write import StorageS3Write
from core.services.storage_transfer_location import resolve_location


def validate_copy_name(name):
    """Native basenames cannot turn a Drive title into a path or staging location."""
    if not isinstance(name, str):
        raise quota.StorageWriteConflict("Choose a valid destination filename.")
    if (
        len(name) > 255
        or not name.strip()
        or name in {".", ".."}
        or any(character in name for character in ("/", "\\", "\x00"))
        or name.startswith(".drive-txn-")
    ):
        raise quota.StorageWriteConflict("Choose a valid destination filename.")
    return name


def enqueue_copy(*, actor, source, destination, name=None, conversion=None):
    """Queue logical references; native paths and credentials are never accepted as targets."""
    if source.kind != "file":
        raise quota.StorageWriteConflict("Select a file to copy.")
    name = validate_copy_name(source.name if name is None else name)
    job, _ = StorageMoveJob.objects.get_or_create(
        actor=actor,
        kind="file_copy",
        space=source.space,
        source_path=str(source.reference.pk),
        destination_path=str(destination.reference.pk),
        state__in=["queued", "running", "conflict"],
        defaults={
            "source_identity": str(source.reference.pk),
            "payload": {
                "title": name,
                "destination_title": destination.name,
                "source": source.descriptor(),
                "destination": destination.descriptor(),
                "name": name,
                "copy_item": str(uuid.uuid4()),
                **({"conversion": conversion} if conversion else {}),
            },
        },
    )
    if (
        job.payload["name"] != name
        or job.payload["destination"] != destination.descriptor()
        or job.payload.get("conversion") != conversion
    ):
        raise quota.StorageWriteConflict("A copy to this folder is already active.")
    transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


def link_copy_operation(job_id, operation, space, actor):
    """Called inside admission's transaction so a worker never loses its reservation."""
    job = StorageMoveJob.objects.select_for_update().get(
        pk=job_id, actor=actor, kind="file_copy", state="running"
    )
    if job.operation_id or job.payload["destination"]["space"] != str(space.pk):
        raise quota.StorageWriteConflict("This copy already has a publication journal.")
    job.operation = operation
    job.save(update_fields=["operation", "updated_at"])
    return {
        "copy_job_id": str(job.pk),
        "source_connection_id": job.payload.get("source", job.payload["destination"])["backend"],
    }


def _location(job, key):
    expected = job.payload[key]
    current = resolve_location(
        expected["id"],
        job.actor,
        space_id=expected["space"],
        destination=key == "destination",
    )
    if current.descriptor() != expected:
        raise quota.StorageWriteConflict("A copy location changed; start a new request.")
    return current


def _locations(job):
    if intake := job.payload.get("suite_intake"):
        from suite_identity.document_transport import resolve_actor  # noqa: PLC0415

        job.actor = resolve_actor(intake["actor"])
    job.actor.refresh_from_db()
    for descriptor in job.payload.get("archive_sources", []):
        current = resolve_location(descriptor["id"], job.actor, space_id=descriptor["space"])
        if current.descriptor() != descriptor:
            raise quota.StorageWriteConflict("An archive source changed location or access.")
    source = None if job.payload.get("external_upload") else _location(job, "source")
    return source, _location(job, "destination")


def _check_source(job):
    source, _ = _locations(job)
    if job.payload.get("external_upload"):
        return job.payload["external_upload"]["digest"]
    if job.payload.get("docs_export") and (
        not source.reference.get_abilities(job.actor).get("export")
        or source.reference.docs_binding.revision != job.payload["docs_revision"]
    ):
        raise quota.StorageWriteConflict("The document or its export permission changed.")
    if job.payload.get("archive_sources"):
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_archive import check_archive_sources  # noqa: PLC0415

        check_archive_sources(job)
        return job.operation.publication["sha256"] if job.operation_id else None
    expected = job.payload["observation"]
    if job.payload.get("conversion") and not virtual.can_write(
        mount=source.mount, normalized_path=source.path
    ):
        raise quota.StorageWriteConflict("The conversion permission was removed.")
    if source.observe() != expected:
        raise quota.StorageWriteConflict(
            "The source changed during copying; its bytes were retained."
        )
    return job.operation.publication["sha256"] if job.operation_id else None


@transaction.atomic
def _pending_item(job, destination):
    """Reuse the same hidden output identity after a crash before quota admission."""
    item = Item.objects.filter(pk=job.payload["copy_item"]).first()
    if item:
        if (
            item.upload_state != "pending"
            or item.hard_deleted_at
            or str(item.path) != f"{destination.reference.path}.{item.pk}"
            or item.storage_space_id != destination.space.pk
            or item.filename != job.payload["name"]
        ):
            raise quota.StorageWriteConflict("The pending copy changed.")
        return item
    if (
        job.payload.get("external_upload")
        and destination.reference.children()
        .filter(filename=job.payload["name"], deleted_at__isnull=True, hard_deleted_at__isnull=True)
        .exists()
    ):
        raise quota.StorageWriteConflict(
            "A file with this name already exists. Choose another name."
        )
    return Item.objects.create_child(
        parent=destination.reference,
        id=job.payload["copy_item"],
        creator=job.actor,
        type="file",
        title=job.payload["name"],
        filename=job.payload["name"],
        mimetype=job.payload.get("output_mimetype", job.payload["observation"]["mimetype"]),
        size=0,
    )


def _write(job, source, destination, converted=None):
    expected_size = converted.size if converted is not None else job.payload["observation"]["size"]
    with (
        nullcontext(converted) if converted is not None else source.open(job.payload["observation"])
    ) as stream:
        reader = DigestReader(stream)

        def check():
            expected_digest = _check_source(job)
            if job.payload.get("external_upload") and reader.digest.hexdigest() != expected_digest:
                raise quota.StorageWriteConflict("The uploaded content changed during publication.")
            if reader.size != expected_size:
                raise quota.StorageWriteConflict("The output size changed during publication.")
            return reader.digest.hexdigest()

        if destination.backend.family == "s3":
            item = _pending_item(job, destination)
            storage = storage_for_item(item)
            writer = StorageS3Write(
                storage.connection.meta.client,
                storage.bucket_name,
                item.file_key,
                actor=job.actor,
                copy_job_id=job.pk,
            )
            writer.source_check = check
            stream_to_s3_object(
                s3_client=storage.connection.meta.client,
                bucket=storage.bucket_name,
                key=item.file_key,
                body_stream=reader,
                content_type=item.mimetype,
                expected_bytes=expected_size,
                max_bytes=expected_size,
                write_context=writer,
            )
        else:
            virtual.write_stream(
                mount=destination.mount,
                final_path=posixpath.join(destination.path, job.payload["name"]),
                chunks=iter(lambda: reader.read(1024 * 1024), b""),
                limits=MountWriteLimits(max_bytes=expected_size),
                must_be_missing=True,
                copy_job_id=job.pk,
                source_check=check,
            )


@transaction.atomic
def _finish(job):
    job.refresh_from_db()
    if job.operation.state != "committed":
        raise quota.StorageWriteConflict("The copy's publication is not confirmed.")
    if job.operation.publication.get("kind") == "s3":
        item = Item.objects.get(pk=job.payload["copy_item"], hard_deleted_at__isnull=True)
        if item.upload_state == "pending":
            item.upload_state = "analyzing"
            item.save(update_fields=["upload_state"])
            transaction.on_commit(
                lambda: malware_detection.analyse_file(
                    item.file_key, item_id=item.pk, **analysis_kwargs(item)
                )
            )
        result_id = job.payload["copy_item"]
    else:
        result_id = str(
            StorageResource.objects.get(
                identity_key=quota.resource_key(f"reference:{job.operation.resource_key}")
            ).pk
        )
    if job.payload.get("archive_sources"):
        job.copy_entries.update(done=True)
    job.state, job.reason = "done", ""
    job.payload = {**job.payload, "result": result_id}
    job.save(update_fields=["state", "reason", "payload", "updated_at"])


def _hide_cancelled_output(job):
    Item.objects.filter(pk=job.payload["copy_item"], size=0, upload_state="pending").update(
        hard_deleted_at=timezone.now()
    )


def _recover(job):
    operation = job.operation
    if operation.state in {"reserved", "writing"}:
        quota.cancel(operation.pk)
        cleanup_operation(operation.pk)
        operation.refresh_from_db()
    if operation.state == "cancelled":
        _hide_cancelled_output(job)
        raise quota.StorageWriteConflict("Copy interrupted before publication; retry the request.")
    if operation.state == "publishing":
        _check_source(job)
        reconcile = _reconcile_s3 if operation.publication.get("kind") == "s3" else _reconcile_mount
        if reconcile(operation, source_check=lambda: _check_source(job)) != "committed":
            raise quota.StorageWriteConflict(
                "The destination is not confirmed; its bytes were retained."
            )


def _permanent_failure(error):
    """Unavailable storage retries; a replaced source or revoked grant needs a new request."""
    if isinstance(error, APIException):
        return error.status_code < 500 and error.status_code not in {408, 429}
    if isinstance(error, ClientError):
        return str(error.response.get("Error", {}).get("Code")) in {
            "412",
            "PreconditionFailed",
            "404",
            "NoSuchKey",
            "AccessDenied",
        }
    return isinstance(error, MountProviderError) and error.public_code in {
        "mount.path.not_found",
        "mount.access.denied",
        "mount.provider.invalid_config",
    }


def prepare_external_retry(job):
    """Recover a previous publication before starting another external write."""
    if job.state == "done":
        return False
    if job.operation_id:
        publishing = job.operation.state in {"publishing", "committed"}
        job.state = "running"
        execute_copy(job)
        job.refresh_from_db()
        if publishing or job.operation.state != "cancelled":
            return False
        job.payload["previous_operations"] = [
            *job.payload.get("previous_operations", []),
            str(job.operation_id),
        ]
        job.operation = None
        job.payload["copy_item"] = str(uuid.uuid4())
    job.state, job.reason = "queued", ""
    job.save(update_fields=["state", "reason", "operation", "payload", "updated_at"])
    return True


# Copies and conversions share the same bounded publication and recovery branches.
# pylint: disable-next=too-many-branches
def execute_copy(job, provided_stream=None):  # noqa: PLR0912, PLR0915
    """The outer move-job advisory lock owns execution and every recovery attempt."""
    if (
        (job.payload.get("docs_export") or job.payload.get("external_upload"))
        and provided_stream is None
        and not job.operation_id
    ):
        return "queued"
    if job.state in {"done", "failed", "conflict"}:
        return job.state
    try:
        if job.payload.get("archive_sources") and job.payload.get("actor"):
            from suite_identity.document_transport import resolve_actor  # noqa: PLC0415

            actor = resolve_actor(job.payload["actor"])
            if actor.pk != job.actor_id:
                raise quota.StorageWriteConflict("The archive actor changed.")
            job.actor = actor
        if job.operation_id and job.operation.state == "committed":
            _finish(job)
            return "done"
        source, destination = _locations(job)
        job.state = "running"
        if "observation" not in job.payload:
            job.payload = {**job.payload, "observation": source.observe()}
        job.save(update_fields=["state", "payload", "updated_at"])
        with ExitStack() as guards:
            converted = provided_stream
            if job.payload.get("archive_sources") and not job.operation_id:
                # pylint: disable-next=import-outside-toplevel,cyclic-import
                from core.services.storage_archive import archive_source  # noqa: PLC0415

                converted = guards.enter_context(archive_source(job))
            if job.payload.get("conversion") and not job.operation_id:
                # pylint: disable-next=import-outside-toplevel,cyclic-import
                from wopi.conversion.native import converted_native_source  # noqa: PLC0415

                converted = guards.enter_context(converted_native_source(job, source))
            backends = {destination.backend}
            if source is not None:
                backends.add(source.backend)
            if job.payload.get("archive_sources"):
                backends.update(
                    StorageBackend.objects.filter(
                        pk__in=list(
                            job.copy_entries.values_list("source__backend", flat=True).distinct()
                        )
                    )
                )
            for backend in sorted(backends, key=lambda entry: str(entry.namespace)):
                guards.enter_context(namespace_guard(backend, exclusive=True))
            if job.operation_id:
                _recover(job)
            else:
                _write(job, source, destination, converted)
            _finish(job)
            return "done"
    except StorageOperationBusy:
        return "busy"
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        job.refresh_from_db()
        uncertain = job.operation_id and job.operation.state == "publishing"
        committed = job.operation_id and job.operation.state == "committed"
        if _permanent_failure(exc) and not committed:
            job.state = "conflict" if uncertain else "failed"
            job.reason = str(getattr(exc, "detail", "Copy could not be completed."))[:255]
        else:
            job.state = "running" if job.operation_id else "queued"
            job.reason = "Storage unavailable; this copy will be retried."
        if job.state == "failed":
            if job.operation_id and job.operation.state in {"reserved", "writing"}:
                quota.cancel(job.operation_id)
                cleanup_operation(job.operation_id)
            _hide_cancelled_output(job)
        job.save(update_fields=["state", "reason", "updated_at"])
        return job.state


def accept_verified_copy(job):
    """Explicitly keep the captured version after rechecking access and destination bytes."""
    if job.kind != "file_copy" or job.state != "conflict" or not job.operation_id:
        raise quota.StorageWriteConflict("This copy has no unresolved publication.")
    operation = job.operation
    if operation.state != "publishing" or not operation.publication.get("sha256"):
        raise quota.StorageWriteConflict("The copy does not have a verifiable published version.")
    source, destination = _locations(job)
    with ExitStack() as guards:
        backends = {destination.backend}
        if source is not None:
            backends.add(source.backend)
        for backend in sorted(backends, key=lambda row: str(row.namespace)):
            guards.enter_context(namespace_guard(backend, exclusive=True))
        reconcile = _reconcile_s3 if operation.publication.get("kind") == "s3" else _reconcile_mount
        if reconcile(operation, source_check=lambda: _locations(job)) != "committed":
            raise quota.StorageWriteConflict("The destination differs from the captured copy.")
        _finish(job)
    job.refresh_from_db()
    return job
