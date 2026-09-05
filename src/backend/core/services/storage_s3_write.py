"""Durable quota admission around native S3 multipart publication."""

import uuid

from django.db import transaction

from botocore.exceptions import ClientError

from core.models import Item, StorageReservation, StorageUsage, User
from core.services import storage_inventory as inventory
from core.services import storage_quota as quota


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
    return str(head.get("VersionId") or head.get("ETag") or "missing")


# The write context retains source, destination and durable operation state.
# pylint: disable-next=too-many-instance-attributes
class StorageS3Write:
    """Keep storage IO outside quota transactions, retaining ambiguous outcomes."""

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def __init__(  # noqa: PLR0913
        self, client, bucket, key, *, actor=None, operation_id=None, item_update=None
    ):
        if transaction.get_connection().in_atomic_block:
            raise quota.StorageWriteConflict("Commit item metadata before starting storage IO.")
        parts = key.split("/", 2)
        if len(parts) != 3 or parts[0] != "item":
            raise quota.StorageWriteConflict("Only registered Drive objects may be published.")
        try:
            item_id = uuid.UUID(parts[1])
            self.item = Item.objects.select_related("creator").get(
                pk=item_id, hard_deleted_at__isnull=True
            )
        except (ValueError, Item.DoesNotExist):
            raise quota.StorageWriteConflict() from None
        if self.item.deleted_at or self.item.ancestors_deleted_at:
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
        self.client, self.bucket, self.key = client, bucket, key
        self.head = object_head(client, bucket, key)
        actor = actor or self.item.creator
        if actor is None:
            raise quota.StorageWriteConflict("Assign an owner before writing this object.")
        inventory.refresh_policy(self.item.creator or actor)
        usage = StorageUsage.objects.get(key=quota.resource_key(f"item:{self.item.pk}"))
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
        self.publishing = False
        self.size = 0

    @property
    def metadata(self):
        """A private operation marker makes a lost completion reply recoverable."""
        return {"drive-operation": str(self.operation.pk)}

    def started(self, upload_id):
        """Persist multipart identity before any part is sent."""
        publication = {
            "kind": "s3",
            "bucket": self.bucket,
            "key": self.key,
            "item_id": str(self.item.pk),
            "upload_id": upload_id,
            "original_key": self.original_key,
            "item_update": self.item_update,
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
        with transaction.atomic():
            quota.commit(self.operation.pk, size=size, version=object_version(head))
            Item.objects.filter(pk=self.item.pk).update(size=size, **self.item_update)
        return version_id or head.get("VersionId")

    def failed(self):
        """A completion timeout must retain its reservation until reconciliation."""
        if not self.publishing:
            quota.cancel(self.operation.pk)
