"""Resumable bounded browser intake, published by Drive's native copy journal."""

import hashlib
import json
import os
import posixpath
import shutil
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.db.models import BigIntegerField, Sum
from django.db.models.functions import Cast
from django.utils import timezone

from rest_framework.exceptions import PermissionDenied, ValidationError
from suite_identity.document_transport import actor_context, resolve_actor

from core.models import Item, StorageMoveJob, StorageReservation
from core.mounts.providers.base import MountEntry
from core.services import storage_inventory as inventory
from core.services import storage_quota as quota
from core.services.storage_copy_job import execute_copy, prepare_external_retry, validate_copy_name
from core.services.storage_namespace import advisory_guard
from core.services.storage_transfer_location import resolve_location
from core.services.suite_files import transfer_result

CHUNK_BYTES = 25 * 1024**2
MAX_BYTES = 20 * 1024**3


def spool_path(job):
    """Only a server-generated UUID addresses this private, dedicated spool."""
    return Path(settings.TRANSFERS_INTAKE_DIRECTORY) / str(job.pk)


def destination_for(user, data):
    return resolve_location(data["destination"], user, space_id=data["space"], destination=True)


def prepare(user, data):
    """The caller holds the same job lock used by the native recovery worker."""
    destination = destination_for(user, data)
    data = {**data, "name": validate_copy_name(data["name"])}
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    existing = StorageMoveJob.objects.filter(pk=data["request_key"]).first()
    if existing:
        if existing.actor_id != user.pk or existing.payload.get("request_hash") != fingerprint:
            raise PermissionDenied("This request key is already used.")
        return existing
    root = Path(settings.TRANSFERS_INTAKE_DIRECTORY)
    if not root.is_dir():
        raise quota.StorageWriteConflict("The private transfer spool is unavailable.")
    if (root / str(data["request_key"])).exists():
        raise quota.StorageWriteConflict("This spool entry needs recovery. Start another copy.")
    if destination.backend.family == "s3":
        attribution = inventory.item_attribution(
            Item(
                creator=user,
                storage_backend=destination.backend,
                storage_space=destination.space,
            )
        )
    else:
        entry = MountEntry("file", posixpath.join(destination.path, data["name"]), data["name"], 0)
        record = inventory.mount_record(
            destination.backend, entry, actor=user, lookup_existing=False
        )
        attribution = {
            key: record[key] for key in ("scope_keys", "organization", "owner", "backend", "space")
        }
    inventory.refresh_policy(
        attribution["owner"] or user, organization=destination.backend.organization
    )
    key = quota.resource_key(f"intake:{data['request_key']}")
    # One short admission lock protects the shared disk budget, not file IO.
    with advisory_guard("suite-intake-budget"), transaction.atomic():
        capacity = (
            StorageMoveJob.objects.filter(
                payload__suite_intake__isnull=False,
            )
            .exclude(payload__suite_intake__cleaned=True)
            .aggregate(
                total=Sum(Cast("payload__observation__size", BigIntegerField())),
                received=Sum(Cast("payload__suite_intake__received", BigIntegerField())),
            )
        )
        reserved = capacity["total"] or 0
        outstanding = reserved - (capacity["received"] or 0)
        free = shutil.disk_usage(root).free
        if (
            reserved + data["size"] > settings.TRANSFERS_INTAKE_MAX_BYTES
            or free - outstanding - data["size"] < settings.TRANSFERS_INTAKE_FREE_BYTES
        ):
            raise quota.StorageQuotaExceeded("The private transfer spool is full. Try later.")
        quota.observe_usage(key=key, size=0, **attribution)
        reservation = quota.admit(key=key, actor=user, size=data["size"])
        job = StorageMoveJob.objects.create(
            pk=data["request_key"],
            actor=user,
            space=destination.space,
            kind="file_copy",
            source_path=str(data["request_key"]),
            source_identity=str(data["request_key"]),
            destination_path=str(destination.reference.pk),
            payload={
                "request_hash": fingerprint,
                "external_upload": {"digest": ""},
                "destination": destination.descriptor(),
                "observation": {"size": data["size"], "mimetype": data["mimetype"]},
                "name": data["name"],
                "title": data["name"],
                "destination_title": destination.name,
                "copy_item": str(uuid4()),
                "output_mimetype": data["mimetype"],
                "suite_intake": {
                    "cleaned": False,
                    "reservation": str(reservation.pk),
                    "received": 0,
                    "expires": int(time.time()) + 3600,
                    "ready": False,
                    "actor": actor_context(user),
                },
            },
        )
        reservation.publication = {"suite_intake_job_id": str(job.pk), "cleanup_pending": True}
        reservation.save(update_fields=["publication"])
    try:
        with spool_path(job).open("xb") as body:
            os.fchmod(body.fileno(), 0o600)
    except OSError:
        cancel(job)
        raise quota.StorageWriteConflict("The private transfer spool is unavailable.") from None
    return job


def authorize(job, user):
    if job.actor_id != user.pk or not job.payload.get("suite_intake"):
        raise PermissionDenied()
    expected = job.payload["destination"]
    current = destination_for(user, {"destination": expected["id"], "space": expected["space"]})
    if current.descriptor() != expected:
        raise quota.StorageWriteConflict("The destination changed. Start a new copy.")


def append(job, user, data, stream):
    """An acknowledged block is durable; a lost response can be replayed exactly."""
    authorize(job, user)
    offset, length, digest = data["offset"], data["length"], data["digest"]
    intake = job.payload["suite_intake"]
    size = job.payload["observation"]["size"]
    if (
        job.state in {"done", "failed", "conflict"}
        or intake["ready"]
        or intake["expires"] <= time.time()
    ):
        raise quota.StorageWriteConflict("This intake no longer accepts blocks.")
    if offset + length > size or offset % CHUNK_BYTES or length != min(CHUNK_BYTES, size - offset):
        raise ValidationError("Invalid transfer block.")
    block = stream.read(length + 1)
    if len(block) != length or hashlib.sha256(block).hexdigest() != digest:
        raise ValidationError("The transfer block is incomplete or changed.")
    received = intake["received"]
    if offset > received:
        raise quota.StorageWriteConflict("Resume at the acknowledged offset.")
    with spool_path(job).open("r+b") as body:
        body.seek(offset)
        if offset < received:
            if (
                offset + length > received
                or hashlib.sha256(body.read(length)).hexdigest() != digest
            ):
                raise quota.StorageWriteConflict("A replayed block changed.")
            return
        if shutil.disk_usage(body.name).free - length < settings.TRANSFERS_INTAKE_FREE_BYTES:
            raise quota.StorageQuotaExceeded("The private transfer spool is full. Try later.")
        body.truncate(received)  # Discard an unacknowledged write left by a crashed process.
        body.write(block)
        body.flush()
        os.fsync(body.fileno())
    intake.update(
        received=received + length, actor=actor_context(user), expires=int(time.time()) + 3600
    )
    with transaction.atomic():
        StorageReservation.objects.filter(pk=intake["reservation"], state="reserved").update(
            expires_at=timezone.now() + timedelta(hours=1),
        )
        job.save(update_fields=["payload", "updated_at"])


def finish(job, user):
    authorize(job, user)
    intake = job.payload["suite_intake"]
    if job.state in {"done", "failed", "conflict"}:
        return
    if intake["expires"] <= time.time() or intake["received"] != job.payload["observation"]["size"]:
        raise ValidationError("The transfer is incomplete or expired.")
    intake.update(ready=True, actor=actor_context(user), expires=int(time.time()) + 3600)
    job.save(update_fields=["payload", "updated_at"])


def cleanup(job):
    """Release admission only after local plaintext has actually been removed."""
    spool_path(job).unlink(missing_ok=True)
    intake = job.payload["suite_intake"]
    quota.cancel(intake["reservation"])
    intake["cleaned"] = True
    job.save(update_fields=["payload", "updated_at"])
    reservation = StorageReservation.objects.get(pk=intake["reservation"])
    reservation.publication.update(cleanup_pending=False, cleaned_at=timezone.now().isoformat())
    reservation.save(update_fields=["publication"])


def cancel(job):
    if job.operation_id and job.operation.state in {"publishing", "committed"}:
        raise quota.StorageWriteConflict("Publication is being confirmed; refresh its result.")
    if job.operation_id:
        from core.services.storage_recovery import cleanup_operation  # noqa: PLC0415

        quota.cancel(job.operation_id)
        cleanup_operation(job.operation_id)
    cleanup(job)
    job.state, job.reason = "failed", "Transfer cancelled or expired."
    job.save(update_fields=["state", "reason", "updated_at"])


def execute(job):
    """Native worker/reconciler owns the job lock, including uncertain publication."""
    intake = job.payload["suite_intake"]
    if job.state in {"done", "failed"}:
        cleanup(job)
        return job.state
    if intake["expires"] <= time.time() and not job.operation_id:
        cancel(job)
        return job.state
    if not intake["ready"]:
        return "queued"
    actor = resolve_actor(intake["actor"])
    authorize(job, actor)
    if not prepare_external_retry(job):
        if job.state == "done":
            cleanup(job)
        return job.state
    with spool_path(job).open("rb") as body:
        if not job.payload["external_upload"]["digest"]:
            digest = hashlib.file_digest(body, "sha256").hexdigest()
            body.seek(0)
            job.payload["external_upload"]["digest"] = digest
            job.save(update_fields=["payload", "updated_at"])
        body.size = job.payload["observation"]["size"]
        # Native publication immediately makes its own atomic quota reservation.
        # A concurrent writer can cause refusal here, never exceed the budget.
        quota.cancel(intake["reservation"])
        execute_copy(job, provided_stream=body)
    job.refresh_from_db()
    if job.state in {"done", "failed"}:
        cleanup(job)
    return job.state


def result(job):
    return {
        **transfer_result(job),
        "received": job.payload["suite_intake"]["received"],
        "size": job.payload["observation"]["size"],
        "chunk_size": CHUNK_BYTES,
    }
