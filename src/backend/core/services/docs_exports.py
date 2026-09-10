"""Publish an authorized native PDF through the existing file copy journal."""

import hashlib
import json
from tempfile import TemporaryFile
from uuid import uuid4

from rest_framework.exceptions import PermissionDenied, ValidationError

from core.models import Item, StorageMoveJob
from core.services.storage_copy_job import accept_verified_copy, execute_copy, validate_copy_name
from core.services.storage_namespace import advisory_guard
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_transfer_location import resolve_location


def export_file(user, data, stream):  # noqa: PLR0912
    """Retries retain a stable output; no source is made public or read as a file."""
    item = Item.objects.filter(docs_binding__document_id=data["document_id"]).first()
    if item is None or not item.get_abilities(user).get("export"):
        raise PermissionDenied()
    source = resolve_location(item.pk, user)
    destination = resolve_location(
        data["destination"], user, space_id=data.get("space_id"), destination=True
    )
    name = validate_copy_name(data["name"])
    if not name.lower().endswith(".pdf"):
        raise ValidationError("Choose a PDF filename.")
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    with advisory_guard(f"storage-move:{data['request_key']}"):
        job, created = StorageMoveJob.objects.get_or_create(
            pk=data["request_key"],
            defaults={
                "actor": user,
                "space": destination.space,
                "kind": "file_copy",
                "source_path": str(item.pk),
                "destination_path": str(destination.reference.pk),
                "source_identity": str(item.pk),
                "payload": {
                    "docs_export": True,
                    "docs_revision": data["revision"],
                    "request_hash": digest,
                    "source": source.descriptor(),
                    "destination": destination.descriptor(),
                    "observation": source.observe(),
                    "name": name,
                    "title": item.title,
                    "destination_title": destination.name,
                    "copy_item": str(uuid4()),
                    "output_mimetype": "application/pdf",
                },
            },
        )
        if not created and (job.actor_id != user.pk or job.payload.get("request_hash") != digest):
            raise PermissionDenied("This export key belongs to another request.")
        if job.state != "done" and job.operation_id:
            if job.operation.state == "committed":
                job.state = "running"
                execute_copy(job)
                job.refresh_from_db()
            elif job.operation.state == "publishing":
                # This exact request already supplied its captured PDF. Confirm
                # its destination bytes, even if the native document later changed.
                job.state = "conflict"
                job.save(update_fields=["state"])
                accept_verified_copy(job)
        if job.state != "done":
            if (
                item.docs_binding.revision != data["revision"]
                or source.observe()["version"] != data["version"]
            ):
                raise StorageWriteConflict("The document changed. Export its current version.")
            if job.state in {"failed", "conflict"}:
                if job.operation_id and job.operation.state == "cancelled":
                    job.payload["previous_operations"] = [
                        *job.payload.get("previous_operations", []),
                        str(job.operation_id),
                    ]
                    job.operation = None
                    job.payload["copy_item"] = str(uuid4())
                job.state = "queued"
                job.save(update_fields=["state", "operation", "payload", "updated_at"])
            with TemporaryFile() as body:
                received, checksum = 0, hashlib.sha256()
                while chunk := stream.read(min(1024 * 1024, data["size"] + 1 - received)):
                    received += len(chunk)
                    if received > data["size"]:
                        raise ValidationError("Export exceeds the announced size.")
                    checksum.update(chunk)
                    body.write(chunk)
                body.seek(0)
                if (
                    received != data["size"]
                    or checksum.hexdigest() != data["digest"]
                    or body.read(5) != b"%PDF-"
                ):
                    raise ValidationError("The PDF export is incomplete or invalid.")
                body.seek(0)
                body.size = received
                execute_copy(job, provided_stream=body)
            job.refresh_from_db()
        return {
            "id": str(job.pk),
            "state": job.state,
            "resource_id": job.payload.get("result"),
            "reason": job.reason,
        }
