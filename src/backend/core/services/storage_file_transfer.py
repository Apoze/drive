"""Copy or move regular files with verified bytes and a durable publication journal."""

import uuid
from contextlib import ExitStack, closing
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from botocore.exceptions import BotoCoreError, ClientError
from rest_framework.exceptions import APIException

from core.models import Item, StorageBackend, StorageMoveJob, StorageReservation, StorageUsage, User
from core.services import storage_inventory as inventory
from core.services import storage_quota as quota
from core.services.s3_streaming import stream_to_s3_object
from core.services.storage_access import source_write_allowed
from core.services.storage_connections import storage_for_backend, storage_for_item
from core.services.storage_integrity import DigestReader, verify_s3_digest
from core.services.storage_move_job import dispatch_move
from core.services.storage_namespace import StorageOperationBusy, advisory_guard, namespace_guard
from core.services.storage_resources import revoke_incompatible_links
from core.services.storage_s3_write import object_head, object_version
from core.services.storage_transfer_location import verified_transfer_destination
from wopi.services.lock import LockService


def _validate(source, target, actor, *, copy=False):
    if (
        source.type != "file"
        or source.effective_upload_state() != "ready"
        or not source.storage_space_id
        or not source.get_abilities(actor).get("retrieve" if copy else "move")
        or source.hard_deleted_at
    ):
        raise quota.StorageWriteConflict("This file cannot be moved.")
    if (
        target.type != "folder"
        or not target.storage_space_id
        or not target.get_abilities(actor).get("children_create")
        or target.hard_deleted_at
    ):
        raise quota.StorageWriteConflict("This file cannot be moved to the selected folder.")
    if LockService(source).is_locked():
        raise quota.StorageWriteConflict("Close the file's editing session before moving it.")


def enqueue_s3_transfer(*, actor, source, destination, mode="move"):
    """Persist a request before broker dispatch; no storage IO runs in the request."""
    if mode not in {"move", "copy"}:
        raise quota.StorageWriteConflict("Choose a copy or a move.")
    _validate(source, destination, actor, copy=mode == "copy")
    if source.storage_backend.family != "s3" or destination.storage_backend.family != "s3":
        raise quota.StorageWriteConflict("Choose two regular file locations.")
    if mode == "move" and source.storage_space_id == destination.storage_space_id:
        raise quota.StorageWriteConflict("Use the ordinary move within this space.")
    job, _ = StorageMoveJob.objects.get_or_create(
        actor=actor,
        kind="s3_copy" if mode == "copy" else "s3_transfer",
        space=source.storage_space,
        source_path=str(source.pk),
        destination_path=str(destination.pk),
        state__in=["queued", "running", "cleanup", "conflict"],
        defaults={
            "source_identity": str(source.pk),
            "payload": {
                "copy_item": str(uuid.uuid4()) if mode == "copy" else None,
                "title": source.title,
                "destination_title": destination.storage_space.name
                if destination.pk == destination.storage_space.root_item_id
                else destination.title,
                "source_backend": str(source.storage_backend_id),
                "destination_backend": str(destination.storage_backend_id),
                "destination_space": str(destination.storage_space_id),
                "source_path": str(source.path),
                "source_key": source.file_key,
                "source_generation": source.storage_backend.configuration_generation,
                "destination_generation": destination.storage_backend.configuration_generation,
            },
        },
    )
    transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


def _items(job):
    source = Item.objects.select_related("storage_backend", "storage_space__owner", "creator").get(
        pk=job.source_path
    )
    target = Item.objects.select_related("storage_backend", "storage_space__owner").get(
        pk=job.destination_path
    )
    return source, target


def execute_s3_transfer(job):
    """Redelivery observes the operation marker before any decision to copy again."""
    if job.state == "cleanup":
        return cleanup_transfer_source(job)
    if job.state in {"done", "failed", "conflict"}:
        return job.state
    try:
        source, target = _items(job)
        with ExitStack() as stack:
            stack.enter_context(advisory_guard(f"storage-editor:{source.pk}"))
            for backend in sorted(
                {source.storage_backend, target.storage_backend},
                key=lambda value: str(value.namespace),
            ):
                stack.enter_context(namespace_guard(backend, exclusive=True))
            write = S3TransferWrite(job, source, target)
            if job.operation_id:
                write.recover()
            else:
                write.prepare()
                if write.same_object:
                    write.started(None)
                    write.publish(write.size)
                    write.finish(write.head)
                else:
                    with closing(write.open_source()) as body:
                        write.reader = DigestReader(body)
                        stream_to_s3_object(
                            s3_client=write.client,
                            bucket=write.bucket,
                            key=write.key,
                            body_stream=write.reader,
                            content_type=source.mimetype,
                            expected_bytes=write.size,
                            max_bytes=write.size,
                            write_context=write,
                        )
        job.refresh_from_db()
        return job.state
    except StorageOperationBusy:
        return "busy"
    except (quota.StorageWriteConflict, quota.StorageQuotaExceeded) as exc:
        job.refresh_from_db()
        job.state = (
            "conflict" if job.operation_id and job.operation.state != "cancelled" else "failed"
        )
        job.reason = str(exc.detail)
    except (BotoCoreError, ClientError, OSError):
        job.refresh_from_db()
        job.state = "running" if job.operation_id else "queued"
        job.reason = "Storage unavailable; this transfer will be retried."
    job.save(update_fields=["state", "reason", "updated_at"])
    return job.state


# A transfer retains two native locations, its source digest and durable journal.
# pylint: disable-next=too-many-instance-attributes
class S3TransferWrite:
    """Use quota substitution, native multipart IO and one metadata commit."""

    publication_conditions = {"IfNoneMatch": "*"}

    def __init__(self, job, source, target):
        self.job, self.source, self.target = job, source, target
        self.operation = job.operation if job.operation_id else None
        self.reader = None
        self.is_copy = job.kind == "s3_copy"
        self.source_storage = storage_for_backend(source.storage_backend)
        self.source_client = self.source_storage.connection.meta.client
        self.storage = storage_for_item(target)
        self.client, self.bucket = self.storage.connection.meta.client, self.storage.bucket_name
        prefix = (
            target.storage_backend.configuration.get("prefix", "").strip("/")
            if not target.storage_backend.legacy_s3
            else ""
        )
        self.original_key = job.payload["source_key"]
        same_storage = (
            self.bucket == self.source_storage.bucket_name
            and self.client.meta.endpoint_url == self.source_client.meta.endpoint_url
        )
        if self.operation:
            self.key = self.operation.publication["key"]
            self.prefix = self.key.rsplit("/item/", 1)[0] if "/item/" in self.key else ""
        elif (
            not self.is_copy
            and same_storage
            and (not prefix or self.original_key.startswith(prefix + "/"))
        ):
            self.key = self.original_key
            self.prefix = source.storage_key_prefix
        else:
            # Retained previous locations must not prevent a later return move.
            self.prefix = (
                prefix
                if self.is_copy
                else "/".join(part for part in (prefix, ".drive-transfers", str(job.pk)) if part)
            )
            self.key = "/".join(
                part
                for part in (
                    self.prefix,
                    "item",
                    job.payload["copy_item"] if self.is_copy else str(source.pk),
                    source.filename,
                )
                if part
            )
        self.same_object = same_storage and self.key == self.original_key
        self.head = object_head(
            self.source_client, self.source_storage.bucket_name, self.original_key
        )
        self.size = int(self.head.get("ContentLength", 0))

    def check_source(self):
        """Recheck rights, editing and source identity immediately before switching."""
        self.source.refresh_from_db()
        self.target.refresh_from_db()
        self.check_locations()
        latest = object_head(self.source_client, self.source_storage.bucket_name, self.original_key)
        expected = self.operation.publication.get(
            "source_observed_version", self.operation.expected_version
        )
        if not latest or object_version(latest) != expected:
            raise quota.StorageWriteConflict(
                "The source changed during transfer; its bytes were retained."
            )
        return latest

    def check_locations(self):
        """Revalidate logical locations without performing storage IO in a transaction."""
        self.job.actor.refresh_from_db()
        self.source.__dict__.pop("_storage_grants", None)
        self.target.__dict__.pop("_storage_grants", None)
        _validate(self.source, self.target, self.job.actor, copy=self.is_copy)
        if self.is_copy and self.job.operation_id:
            if not Item.objects.filter(
                pk=self.job.payload["copy_item"],
                storage_backend=self.target.storage_backend,
                storage_space=self.target.storage_space,
                path=f"{self.target.path}.{self.job.payload['copy_item']}",
                filename=self.source.filename,
                hard_deleted_at__isnull=True,
                deleted_at__isnull=True,
            ).exists():
                raise quota.StorageWriteConflict("The pending copy location changed.")
        actual = (
            self.source.file_key,
            str(self.source.path),
            str(self.source.storage_backend_id),
            str(self.target.storage_backend_id),
            str(self.target.storage_space_id),
            self.source.storage_backend.configuration_generation,
            self.target.storage_backend.configuration_generation,
        )
        expected = (
            self.original_key,
            self.job.payload["source_path"],
            self.job.payload["source_backend"],
            self.job.payload["destination_backend"],
            self.job.payload["destination_space"],
            self.job.payload["source_generation"],
            self.job.payload["destination_generation"],
        )
        if actual != expected:
            raise quota.StorageWriteConflict("A transfer location changed.")

    def prepare(self):
        """Reserve only additional scopes while keeping the entire source charge."""
        self.check_locations()
        if not self.head or (
            not self.same_object and object_head(self.client, self.bucket, self.key)
        ):
            raise quota.StorageWriteConflict(
                "The source is missing or the destination already exists."
            )
        planned = Item(
            creator=self.job.actor if self.is_copy else self.source.creator,
            storage_backend=self.target.storage_backend,
            storage_space=self.target.storage_space,
        )
        attribution = inventory.item_attribution(planned)
        inventory.refresh_policy(
            attribution["owner"] or self.job.actor, organization=attribution["organization"]
        )
        with transaction.atomic():
            User.objects.select_for_update(no_key=True).get(pk=self.job.actor_id)
            charged_item = self.source
            if self.is_copy:
                charged_item = Item.objects.create_child(
                    parent=self.target,
                    id=self.job.payload["copy_item"],
                    type="file",
                    title=self.source.title,
                    filename=self.source.filename,
                    description=self.source.description,
                    mimetype=self.source.mimetype,
                    creator=self.job.actor,
                    size=0,
                )
            usage = StorageUsage.objects.select_for_update().get(item=charged_item)
            if not self.is_copy and usage.size != self.size:
                raise quota.StorageWriteConflict("Refresh this file's inventory before moving it.")
            usage.version = "missing" if self.is_copy else object_version(self.head)
            usage.save(update_fields=["version", "observed_at"])
            self.operation = quota.admit(
                key=usage.key,
                actor=self.job.actor,
                size=self.size,
                target_scopes=attribution["scope_keys"],
                lifetime=timedelta(hours=24),
                publication_key=quota.resource_key(
                    f"s3-transfer:{self.target.storage_backend.namespace}:{self.key}"
                ),
            )
            self.job.operation = self.operation
            self.job.state = "running"
            self.job.save(update_fields=["operation", "state", "updated_at"])
            self.operation.publication = {
                "kind": "s3_transfer",
                "job_id": str(self.job.pk),
                "connection_id": str(self.target.storage_backend_id),
                "source_connection_id": str(self.source.storage_backend_id),
                "configuration_generation": self.job.payload["destination_generation"],
                "source_generation": self.job.payload["source_generation"],
                "key": self.key,
                "bucket": self.bucket,
                "original_key": self.original_key,
                "source_version": self.head.get("VersionId"),
                "source_etag": self.head.get("ETag"),
                "source_observed_version": object_version(self.head),
                "target_attribution": {
                    "organization": attribution["organization"],
                    "owner_id": str(attribution["owner"].pk) if attribution["owner"] else None,
                    "space_id": str(self.target.storage_space_id),
                },
            }
            self.operation.save(update_fields=["publication", "updated_at"])

    @property
    def metadata(self):
        """The existing recovery marker distinguishes this transfer's publication."""
        return {"drive-operation": str(self.operation.pk)}

    def accept(self, size):
        """A transfer has a fixed snapshot length; growth is a conflict."""
        if size > self.size:
            raise quota.StorageWriteConflict("The source grew during transfer.")

    def started(self, upload_id):
        """Persist the multipart handle before the first uploaded part."""
        self.operation = quota.record_staging(
            self.operation.pk, {**self.operation.publication, "upload_id": upload_id}
        )

    def publish(self, size):
        """Persist the source digest before asking S3 to make bytes visible."""
        self.check_source()
        publication = {
            **self.operation.publication,
            "sha256": self.reader.digest.hexdigest() if self.reader else None,
        }
        quota.begin_publication(
            self.operation.pk,
            size=size,
            observed_version=self.operation.expected_version,
            publication=publication,
        )
        self.operation.refresh_from_db()

    def open_source(self):
        """Read the observed immutable version or require its opaque ETag."""
        version = self.head.get("VersionId")
        return self.source_client.get_object(
            Bucket=self.source_storage.bucket_name,
            Key=self.original_key,
            **({"VersionId": version} if version not in {None, "", "null"} else {}),
            IfMatch=self.head["ETag"],
        )["Body"]

    def completed(self, size, version_id):
        """Reread and verify the destination before releasing any source budget."""
        if size != self.size:
            raise quota.StorageWriteConflict("Transfer size changed before verification.")
        head = self.verify()
        self.finish(head)
        return version_id

    def verify(self):
        """An ETag alone is never treated as a content checksum."""
        head = object_head(self.client, self.bucket, self.key)
        publication = self.operation.publication
        if self.same_object:
            self.check_source()
            return head
        if head.get("ContentLength") != publication.get("size") or head.get("Metadata", {}).get(
            "drive-operation"
        ) != str(self.operation.pk):
            raise quota.StorageWriteConflict("Destination publication is not yet confirmed.")
        verify_s3_digest(self.client, self.bucket, self.key, head, publication.get("sha256"))
        self.check_source()
        return head

    def finish(self, head):
        """Atomically switch native Item location, tree membership and logical charge."""
        with transaction.atomic():
            quota.commit(self.operation.pk, size=self.size, version=object_version(head))
            locked = {
                item.pk: item
                for item in Item.objects.select_for_update()
                .filter(pk__in=[self.source.pk, self.target.pk])
                .order_by("pk")
            }
            self.source, self.target = locked[self.source.pk], locked[self.target.pk]
            self.check_locations()
            if self.is_copy:
                Item.objects.filter(pk=self.job.payload["copy_item"]).update(
                    size=self.size, upload_state="ready"
                )
            else:
                Item.objects.filter(pk=self.source.pk).update(
                    storage_backend=self.target.storage_backend,
                    storage_space=self.target.storage_space,
                    storage_key_prefix=self.prefix,
                    path=f"{self.target.path}.{self.source.pk}",
                )
                StorageUsage.objects.filter(item=self.source).update(
                    backend=self.target.storage_backend
                )
            if not self.is_copy:
                revoke_incompatible_links(self.source.pk)
            retain_source = not self.same_object and not self.is_copy
            publication = {
                **self.operation.publication,
                "cleanup_pending": False,
                "source_retained": retain_source,
            }
            StorageReservation.objects.filter(pk=self.operation.pk).update(publication=publication)
            StorageMoveJob.objects.filter(pk=self.job.pk).update(
                state="cleanup" if retain_source else "done",
                reason=""
                if not retain_source
                else "Destination verified; source cleanup is pending.",
                payload={
                    **self.job.payload,
                    "source_retained": retain_source,
                    "result": self.job.payload.get("copy_item") or str(self.source.pk),
                },
                updated_at=timezone.now(),
            )

    def recover(self):
        """Never restart uncertain multipart completion or overwrite its destination."""
        self.operation.refresh_from_db()
        if self.operation.state == "committed":
            retained = self.operation.publication.get("source_retained", False)
            StorageMoveJob.objects.filter(pk=self.job.pk).update(
                state="cleanup" if retained else "done",
                reason="Destination verified; source cleanup is pending." if retained else "",
                payload={
                    **self.job.payload,
                    "result": self.job.payload.get("copy_item") or str(self.source.pk),
                },
            )
            return
        if self.operation.state == "cancelled":
            self._hide_cancelled_copy()
            StorageMoveJob.objects.filter(pk=self.job.pk).update(
                state="failed", reason="Transfer cancelled before publication."
            )
            return
        if self.operation.state == "publishing":
            self.size = self.operation.publication["size"]
            self.finish(self.verify())
            return
        # This worker owns the job lock, so no earlier worker can still publish.
        upload = self.operation.publication.get("upload_id")
        if upload:
            self.client.abort_multipart_upload(Bucket=self.bucket, Key=self.key, UploadId=upload)
        quota.cancel(self.operation.pk)
        self._hide_cancelled_copy()
        StorageMoveJob.objects.filter(pk=self.job.pk).update(
            state="failed", reason="Transfer interrupted before publication. Retry it."
        )

    def failed(self):
        """Publication timeouts remain recoverable; definite pre-publication failures cancel."""
        self.operation.refresh_from_db()
        if self.operation.state in {"reserved", "writing"}:
            quota.cancel(self.operation.pk)
            self._hide_cancelled_copy()

    def _hide_cancelled_copy(self):
        """Keep the failed job's identity while hiding its unpublished, zero-byte Item."""
        if self.is_copy:
            Item.objects.filter(
                pk=self.job.payload["copy_item"], upload_state="pending", size=0
            ).update(hard_deleted_at=timezone.now())


def _cleanup_access(job, backend):
    """Deletion needs both current destination access and the original writable scope."""
    job.actor.refresh_from_db()
    space = job.space
    space.refresh_from_db()
    backend.refresh_from_db()
    if not job.actor.is_active or not backend.enabled or not space.enabled:
        raise quota.StorageWriteConflict(
            "Source cleanup is waiting for valid transfer permissions."
        )
    if backend.configuration_generation != job.payload["source_generation"]:
        raise quota.StorageWriteConflict(
            "Source cleanup is waiting for its original connection configuration."
        )
    if not source_write_allowed(space, job.actor, job.payload["source_path"]):
        raise quota.StorageWriteConflict(
            "Source cleanup is waiting for its original write permission."
        )


def cleanup_transfer_source(job):
    """Remove only the captured immutable S3 version; never delete a key by observation."""
    operation = job.operation
    publication = operation.publication
    reason = "Source retained until the configured retention period expires."
    try:
        if operation.state != "committed" or not publication.get("source_retained"):
            raise quota.StorageWriteConflict("The transfer publication needs verification.")
        version = publication.get("source_version")
        if version in {None, "", "null"}:
            raise quota.StorageWriteConflict(
                "Source retained: this storage has no immutable version identity."
            )
        if operation.updated_at > timezone.now() - timedelta(
            days=settings.STORAGE_BACKUP_RETENTION_DAYS
        ):
            return "cleanup"
        if not publication.get("sha256"):
            raise quota.StorageWriteConflict(
                "Source retained: the destination checksum is unavailable."
            )
        backend = StorageBackend.objects.get(pk=publication["source_connection_id"])
        _cleanup_access(job, backend)
        with verified_transfer_destination(job, backend):
            _cleanup_access(job, backend)
            source = storage_for_backend(backend)
            source.connection.meta.client.delete_object(
                Bucket=source.bucket_name,
                Key=publication["original_key"],
                VersionId=version,
            )
            with transaction.atomic():
                operation.publication = {
                    **publication,
                    "source_retained": False,
                    "source_cleaned_at": timezone.now().isoformat(),
                }
                operation.save(update_fields=["publication", "updated_at"])
                job.state, job.reason = "done", ""
                job.payload = {**job.payload, "source_retained": False}
                job.save(update_fields=["state", "reason", "payload", "updated_at"])
            return "done"
    except APIException as exc:
        reason = str(exc.detail)
    except (Item.DoesNotExist, StorageBackend.DoesNotExist):
        reason = "Source retained: a transfer location is no longer available."
    except (BotoCoreError, ClientError, OSError):
        reason = "Source retained: storage cleanup is temporarily unavailable."
    finally:
        if job.state == "cleanup":
            job.reason = reason
            job.save(update_fields=["reason", "updated_at"])
    return "cleanup"
