"""
Tasks related to items.
"""

import hashlib
import logging
from datetime import timedelta
from os.path import splitext

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone

import boto3
import botocore
from celery.schedules import crontab

from core.api.utils import sanitize_filename
from core.models import Item, ItemTypeChoices, ItemUploadStateChoices
from core.services.regular_storage_copy import (
    copy_regular_storage_object,
    get_s3_client_error_code,
)
from core.utils.no_leak import safe_str_hash

from drive.celery_app import app

logger = logging.getLogger(__name__)

_CREATING_CLEANUP_MAX_ITEMS_PER_RUN = 200


@app.on_after_finalize.connect
def _setup_periodic_tasks(sender, **kwargs):
    """
    Periodic cleanup of stale "creating" OOXML placeholders (0-byte).

    The schedule is intentionally conservative to avoid load spikes.
    """
    sender.add_periodic_task(
        crontab(minute="*/5"),
        cleanup_stale_creating_items.s(),
        name="cleanup_stale_creating_items",
        serializer="json",
    )


@app.task
def cleanup_stale_creating_items():
    """
    Remove 0-byte items stuck in CREATING state past a TTL.

    Best-effort: items are soft+hard deleted then processed asynchronously to
    delete the object and the DB row.
    """
    ttl_seconds = int(getattr(settings, "ITEM_OOXML_CREATING_TTL_SECONDS", 900))
    ttl_seconds = max(ttl_seconds, 60)
    cutoff = timezone.now() - timedelta(seconds=ttl_seconds)

    stale = (
        Item.objects.filter(
            type=ItemTypeChoices.FILE,
            upload_state=ItemUploadStateChoices.CREATING,
            size=0,
            upload_started_at__isnull=False,
            upload_started_at__lt=cutoff,
            deleted_at__isnull=True,
            ancestors_deleted_at__isnull=True,
            hard_deleted_at__isnull=True,
        )
        .order_by("upload_started_at")
        .only("id", "filename", "upload_started_at", "deleted_at", "hard_deleted_at")
    )[:_CREATING_CLEANUP_MAX_ITEMS_PER_RUN]

    for item in stale:
        try:
            logger.info(
                "cleanup_stale_creating_items: hard-deleting stale creating item "
                "(item_id=%s file_key_hash=%s)",
                item.id,
                safe_str_hash(item.file_key) if item.filename else None,
            )
            item.soft_delete()
            item.hard_delete()
            process_item_purge.delay(item.id)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception(
                "cleanup_stale_creating_items: failed to delete stale creating item (item_id=%s)",
                item.id,
            )


@app.task
def process_item_purge(item_id):
    """
    Process the purge of an item that was either:
    - hard deleted
    - soft deleted for longer than the trashbin cutoff and grace period

    Delete children before parents and keep storage logging hashed.
    """
    logger.info("Processing item purge for %s", item_id)
    try:
        root = Item.objects.get(id=item_id)
    except Item.DoesNotExist:
        logger.error("Item %s does not exist", item_id)
        return

    now = timezone.now()
    is_hard_deleted = root.hard_deleted_at is not None
    is_soft_deleted_and_purgeable = root.deleted_at is not None and now >= (
        root.deleted_at + timedelta(days=settings.TRASHBIN_CUTOFF_DAYS + settings.PURGE_GRACE_DAYS)
    )

    if not (is_hard_deleted or is_soft_deleted_and_purgeable):
        reason = "item is not deleted"
        if root.deleted_at is not None:
            reason = f"soft-deleted but not past purge cutoff: {root.deleted_at.isoformat()}"

        logger.info("Item %s is not eligible for purge: %s", item_id, reason)
        return

    for item in Item.objects.filter(path__descendants=root.path).order_by("-path").iterator():
        if item.type == ItemTypeChoices.FILE and item.file_key:
            logger.info(
                "Purging file (item_id=%s file_key_hash=%s)",
                item.id,
                safe_str_hash(item.file_key),
            )
            try:
                default_storage.delete(item.file_key)
            except FileNotFoundError:
                pass

        item.delete()


@app.task
def rename_file(item_id, new_title):
    """Rename the file of an item. Update the filename and then rename the file on storage."""

    if not new_title:
        logger.error("New title is empty, skipping rename file")
        return

    try:
        item = Item.objects.get(id=item_id)
    except Item.DoesNotExist:
        logger.error("Item %s does not exist", item_id)
        return

    if item.type != ItemTypeChoices.FILE:
        logger.error("Item %s is not a file", item_id)
        return

    if item.upload_state != ItemUploadStateChoices.READY:
        logger.error("Item %s is not ready for renaming", item_id)
        return

    _, extension = splitext(item.filename)

    new_filename = sanitize_filename(f"{new_title}{extension}")
    from_file_key = item.file_key

    if item.filename == new_filename:
        logger.info(
            "Item %s filename has not changed, no need to move it on storage",
            item_id,
        )
        return

    item.filename = new_filename
    item.save(update_fields=["filename", "updated_at"])

    to_file_key = item.file_key

    s3_client = default_storage.connection.meta.client

    copy_regular_storage_object(
        s3_client=s3_client,
        bucket=default_storage.bucket_name,
        source_key=from_file_key,
        destination_key=to_file_key,
        metadata_directive="COPY",
        delete_source=True,
    )


@app.task
def update_suspicious_item_file_hash(item_id):
    """
    Update the file hash of a suspicious item.
    This is done in a separate task to avoid blocking the main thread.
    """
    try:
        item = Item.objects.get(id=item_id)
    except Item.DoesNotExist:
        logger.error("updating suspicious item file hash: Item %s does not exist", item_id)
        return
    if item.upload_state != ItemUploadStateChoices.SUSPICIOUS:
        logger.error("updating suspicious item file hash: Item %s is not suspicious", item_id)
        return
    with default_storage.open(item.file_key, "rb") as file:
        file_hash = hashlib.file_digest(file, "sha256").hexdigest()

    item.malware_detection_info.update({"file_hash": file_hash})
    item.save(update_fields=["malware_detection_info"])


@app.task(bind=True, max_retries=10)
def duplicate_file(self, item_to_duplicate_id, duplicated_item_id):
    """Copy a file on the storage."""
    try:
        item_to_duplicate = Item.objects.get(id=item_to_duplicate_id)
    except Item.DoesNotExist:
        logger.exception(
            "duplicating file: item_to_duplicate with id %s does not exist, aborting",
            item_to_duplicate_id,
        )
        return

    try:
        duplicated_item = Item.objects.get(id=duplicated_item_id)
    except Item.DoesNotExist:
        logger.exception(
            "duplicating file: duplicated_item with id %s does not exist, aborting",
            duplicated_item_id,
        )
        return

    if duplicated_item.upload_state != ItemUploadStateChoices.DUPLICATING:
        logger.error(
            "duplicating file: the duplidated file upload_state is not duplicating but %s, "
            "aborting",
            duplicated_item.upload_state,
        )
        return

    s3_client = default_storage.connection.meta.client
    source_key_hash = safe_str_hash(item_to_duplicate.file_key)
    destination_key_hash = safe_str_hash(duplicated_item.file_key)

    try:
        copy_regular_storage_object(
            s3_client=s3_client,
            bucket=default_storage.bucket_name,
            source_key=item_to_duplicate.file_key,
            destination_key=duplicated_item.file_key,
            metadata_directive="COPY",
        )
    except (
        boto3.exceptions.Boto3Error,
        botocore.exceptions.BotoCoreError,
        botocore.exceptions.ClientError,
    ) as exc:
        if self.request.retries >= self.max_retries:
            # delete the duplicated item
            logger.error(
                "duplicating file: %d max retries exceeded, the duplicated item %s is deleted",
                self.max_retries,
                duplicated_item.id,
            )
            duplicated_item.soft_delete()
            duplicated_item.delete()

        logger.error(
            "duplicating file: error while copying file (retries %d on %d "
            "source_key_hash=%s destination_key_hash=%s error_code=%s)",
            self.request.retries,
            self.max_retries,
            source_key_hash,
            destination_key_hash,
            get_s3_client_error_code(exc),
        )

        self.retry(exc=exc)

    duplicated_item.upload_state = ItemUploadStateChoices.READY
    duplicated_item.save(update_fields=["upload_state", "updated_at"])
