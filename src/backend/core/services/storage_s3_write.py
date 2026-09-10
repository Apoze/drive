"""Durable quota admission around native S3 multipart publication."""

from django.core.exceptions import ValidationError
from django.db import transaction

from botocore.exceptions import ClientError

from core.models import Item, StorageReservation, StorageUsage, User
from core.services import storage_inventory as inventory
from core.services import storage_quota as quota
from core.services.storage_connections import item_for_key, storage_for_item
from core.services.storage_integrity import verify_s3_digest


def object_head(client, bucket, key):
    """Only a confirmed missing object is treated as empty storage."""
    try:
        return client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code")) in {"404", "NoSuchKey", "NotFound"}:
            return {}
        raise


def object_version(head):
    """Version IDs are preferred; unversioned S3 still supplies an opaque ETag."""
    version = head.get("VersionId")
    return str(version if version not in {None, "", "null"} else head.get("ETag") or "missing")


# The write context retains source, destination and durable operation state.
# pylint: disable-next=too-many-instance-attributes
class StorageS3Write:
    """Keep storage IO outside quota transactions, retaining ambiguous outcomes."""

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(  # noqa: PLR0913
        self,
        client,
        bucket,
        key,
        *,
        actor=None,
        operation_id=None,
        item_update=None,
        copy_job_id=None,
    ):
        if transaction.get_connection().in_atomic_block:
            raise quota.StorageWriteConflict("Commit item metadata before starting storage IO.")
        try:
            self.item = item_for_key(key)
        except (ValueError, ValidationError, Item.DoesNotExist):
            raise quota.StorageWriteConflict() from None
        if self.item.deleted_at or self.item.ancestors_deleted_at or self.item.hard_deleted_at:
            raise quota.StorageWriteConflict()
        self.original_key = self.item.file_key
        self.item_update = item_update or {}
        if set(self.item_update) - {"filename", "title"}:
            raise quota.StorageWriteConflict()
        expected_key = (
            f"{self.item.key_base}/{self.item_update.get('filename', self.item.filename)}"
        )
        if expected_key != key:
            raise quota.StorageWriteConflict()
        storage = storage_for_item(self.item)
        if (
            bucket != storage.bucket_name
            or client.meta.endpoint_url != storage.connection.meta.client.meta.endpoint_url
        ):
            raise quota.StorageWriteConflict("The publication destination does not match the item.")
        self.client, self.bucket, self.key = client, bucket, key
        self.head = object_head(client, bucket, key)
        actor = actor or self.item.creator
        if actor is None:
            raise quota.StorageWriteConflict("Assign an owner before writing this object.")
        self._check_access(actor)
        usage = StorageUsage.objects.get(item=self.item)
        inventory.refresh_policy(usage.owner or actor, organization=usage.organization)
        with transaction.atomic():
            # Match quota.admit's actor -> usage -> budget lock order.
            User.objects.select_for_update(no_key=True).get(pk=actor.pk)
            usage = StorageUsage.objects.select_for_update().get(pk=usage.pk)
            if (
                operation_id
                and StorageReservation.objects.filter(
                    resource_key=usage.key,
                    state="committed",
                ).exists()
            ):
                raise quota.StorageWriteConflict("Upload already completed.")
            if StorageReservation.objects.filter(
                resource_key=usage.key, state__in=["reserved", "writing", "publishing"]
            ).exists():
                raise quota.StorageWriteConflict()
            # A rename keeps its logical charge while publishing under the new key.
            usage.version = object_version(self.head)
            usage.save(update_fields=["version", "observed_at"])
            self.operation = quota.admit(
                key=usage.key,
                actor=actor,
                size=usage.size,
                operation_id=operation_id,
            )
            if copy_job_id:
                # pylint: disable-next=import-outside-toplevel,cyclic-import
                from core.services.storage_copy_job import link_copy_operation  # noqa: PLC0415

                self.operation.publication = link_copy_operation(
                    copy_job_id, self.operation, self.item.storage_space, actor
                )
                self.operation.save(update_fields=["publication", "updated_at"])
        self.source_cleanup = None
        self.source_reader = None
        self.source_check = None
        self.publishing = False
        self.size = 0

    def _check_access(self, actor):
        """Revalidate the connection and space for capabilities issued before revocation."""
        if self.item.storage_backend_id:
            self.item.__dict__.pop("_storage_grants", None)
            backend = self.item.storage_backend
            if (
                not backend.enabled
                or backend.maintenance
                or (self.item.storage_space_id and not self.item.get_abilities(actor).get("update"))
            ):
                raise quota.StorageWriteConflict("This storage space is not writable.")

    @property
    def metadata(self):
        """A private operation marker makes a lost completion reply recoverable."""
        return {"drive-operation": str(self.operation.pk)}

    @property
    def publication_conditions(self):
        """Close the race between the last HEAD and native multipart completion."""
        return {"IfMatch": self.head["ETag"]} if self.head else {"IfNoneMatch": "*"}

    def started(self, upload_id):
        """Persist multipart identity before any part is sent."""
        publication = {
            **self.operation.publication,
            "kind": "s3",
            "bucket": self.bucket,
            "key": self.key,
            "item_id": str(self.item.pk),
            "upload_id": upload_id,
            "original_key": self.original_key,
            "item_update": self.item_update,
            "source_cleanup": self.source_cleanup,
            "source_retained": bool(self.source_cleanup),
            "connection_id": str(self.item.storage_backend_id)
            if self.item.storage_backend_id
            else None,
            "configuration_generation": (
                self.item.storage_backend.configuration_generation
                if self.item.storage_backend_id
                else None
            ),
        }
        self.operation = quota.record_staging(self.operation.pk, publication)

    def accept(self, size):
        """Reserve the real stream length before transferring the next part."""
        self.size = size
        if size > self.operation.previous_size + self.operation.reserved_bytes:
            self.operation = quota.extend(self.operation.pk, size=size)

    def publish(self, size):
        """Fence deletion, rename and concurrent updates immediately before completion."""
        self.item.refresh_from_db()
        if (
            self.item.hard_deleted_at
            or self.item.deleted_at
            or self.item.ancestors_deleted_at
            or self.item.file_key != self.original_key
            or not User.objects.filter(pk=self.operation.actor_id, is_active=True).exists()
        ):
            raise quota.StorageWriteConflict()
        self.operation.refresh_from_db()
        self._check_access(self.operation.actor)
        check_rename_source(self.client, self.bucket, self.operation.publication)
        if self.source_check:
            self.operation.publication["sha256"] = self.source_check()
        if self.source_reader:
            self.operation.publication["sha256"] = self.source_reader.digest.hexdigest()
        quota.begin_publication(
            self.operation.pk,
            observed_version=object_version(object_head(self.client, self.bucket, self.key)),
            size=size,
            publication=self.operation.publication,
        )
        self.publishing = True

    def completed(self, size, version_id):
        """Publish metadata and accounting together; caller owns MIME/upload state."""
        head = object_head(self.client, self.bucket, self.key)
        if (
            head.get("Metadata", {}).get("drive-operation") != str(self.operation.pk)
            or head.get("ContentLength") != size
        ):
            raise quota.StorageWriteConflict("S3 publication requires reconciliation.")
        if digest := self.operation.publication.get("sha256"):
            verify_s3_digest(self.client, self.bucket, self.key, head, digest)
        check_rename_source(self.client, self.bucket, self.operation.publication)
        if self.source_check:
            self.source_check()
        with transaction.atomic():
            quota.commit(self.operation.pk, size=size, version=object_version(head))
            Item.objects.filter(pk=self.item.pk).update(size=size, **self.item_update)
        return version_id or head.get("VersionId")

    def failed(self):
        """A completion timeout must retain its reservation until reconciliation."""
        if not self.publishing:
            quota.cancel(self.operation.pk)


def check_rename_source(client, bucket, publication):
    """A retained rename source must still match before logical publication."""
    source = publication.get("source_cleanup")
    if (
        source
        and object_version(object_head(client, bucket, source["key"])) != source["observed_version"]
    ):
        raise quota.StorageWriteConflict("The rename source changed; both copies were retained.")
