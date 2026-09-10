"""Suite attachments use Drive's existing publication and quota journal."""

import hashlib
import json
from tempfile import TemporaryFile
from uuid import uuid4

from rest_framework.exceptions import PermissionDenied, ValidationError

from core.models import StorageMoveJob
from core.services.storage_copy_job import execute_copy, validate_copy_name
from core.services.storage_namespace import advisory_guard
from core.services.storage_transfer_location import resolve_location

MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024


def import_attachment(user, data, stream):
    """An immutable content digest and destination identify each retry."""
    destination = resolve_location(
        data["destination"], user, space_id=data.get("space"), destination=True
    )
    name = validate_copy_name(data["name"])
    request_hash = hashlib.sha256(
        json.dumps(data, sort_keys=True, default=str).encode()
    ).hexdigest()
    with advisory_guard(f"storage-move:{data['request_key']}"):
        job, created = StorageMoveJob.objects.get_or_create(
            pk=data["request_key"],
            defaults={
                "actor": user,
                "space": destination.space,
                "kind": "file_copy",
                "source_path": data["digest"],
                "source_identity": data["digest"],
                "destination_path": str(destination.reference.pk),
                "payload": {
                    "external_upload": {"digest": data["digest"]},
                    "request_hash": request_hash,
                    "destination": destination.descriptor(),
                    "observation": {"size": data["size"], "mimetype": data["mimetype"]},
                    "name": name,
                    "title": name,
                    "destination_title": destination.name,
                    "copy_item": str(uuid4()),
                    "output_mimetype": data["mimetype"],
                },
            },
        )
        if not created and (
            job.actor_id != user.pk or job.payload.get("request_hash") != request_hash
        ):
            raise PermissionDenied("The transfer key belongs to another request.")
        if job.state == "done":
            return transfer_result(job)
        if job.operation_id:
            if job.operation.state in {"publishing", "committed"}:
                job.state = "running"
                execute_copy(job)
                job.refresh_from_db()
                return transfer_result(job)
            # Recovery cancels unfinished staging before a fresh write attempt.
            job.state = "running"
            execute_copy(job)
            job.refresh_from_db()
            if job.operation.state != "cancelled":
                return transfer_result(job)
            job.payload["previous_operations"] = [
                *job.payload.get("previous_operations", []),
                str(job.operation_id),
            ]
            job.operation = None
            job.payload["copy_item"] = str(uuid4())
        job.state, job.reason = "queued", ""
        job.save(update_fields=["state", "reason", "operation", "payload", "updated_at"])
        with TemporaryFile() as body:
            received, digest = 0, hashlib.sha256()
            while chunk := stream.read(min(1024 * 1024, data["size"] + 1 - received)):
                received += len(chunk)
                if received > data["size"]:
                    raise ValidationError("Attachment exceeds its announced size.")
                digest.update(chunk)
                body.write(chunk)
            if received != data["size"] or digest.hexdigest() != data["digest"]:
                raise ValidationError("Attachment is incomplete or changed.")
            body.seek(0)
            body.size = received
            execute_copy(job, provided_stream=body)
        job.refresh_from_db()
        return transfer_result(job)


def transfer_result(job):
    """The native transfer UI can observe pending analysis or retryable storage failure."""
    return {
        "job_id": str(job.pk),
        "state": job.state,
        "id": job.payload.get("result"),
        "reason": job.reason,
    }
