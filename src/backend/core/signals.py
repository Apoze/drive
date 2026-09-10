"""
Declare and configure the signals for the impress core application
"""

from functools import partial

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import signals
from django.dispatch import receiver

from core.services import storage_quota
from core.services.storage_inventory import item_usage

from . import models
from .tasks.search import trigger_batch_file_indexer


@receiver(signals.pre_delete, sender=models.ItemAccess)
def lock_document_owner_deletion(sender, instance, **kwargs):
    """Queryset/cascade deletion must use the same lock as individual ACL edits."""
    if instance.role == "owner" and instance.item.type == models.ItemTypeChoices.DOCS:
        models.Item.objects.select_for_update().get(pk=instance.item_id)


@receiver(signals.post_delete, sender=models.ItemAccess)
def preserve_document_owner(sender, instance, **kwargs):
    """Check after the whole SQL batch, so deleting two owners cannot orphan Docs."""
    if (
        instance.role == "owner"
        and instance.item.type == models.ItemTypeChoices.DOCS
        and models.DocsBinding.objects.filter(item_id=instance.item_id)
        .exclude(state="purged")
        .exists()
        and not models.ItemAccess.objects.filter(item_id=instance.item_id, role="owner").exists()
    ):
        raise ValidationError("Transfer document ownership before deleting its last owner.")


@receiver(signals.post_save, sender=models.ItemAccess)
@receiver(signals.post_delete, sender=models.ItemAccess)
def document_access_changed(sender, instance, **kwargs):
    """Generic Drive sharing also invalidates native document metadata revisions."""
    if not getattr(settings, "DOCS_DRIVE_ENABLED", False):
        return
    from core.services.docs_lifecycle import queue_change, queue_tree_changes  # noqa: PLC0415

    item = instance.item
    if item.type == models.ItemTypeChoices.DOCS:
        queue_change(item)
    if item.type in {models.ItemTypeChoices.DOCS, models.ItemTypeChoices.FOLDER}:
        queue_tree_changes(item)


@receiver(signals.post_save, sender=models.Item)
def account_item_storage(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    """Keep the storage ledger current when native Item metadata changes."""
    if (
        getattr(settings, "STORAGE_GOVERNANCE_ENABLED", False)
        and instance.type == models.ItemTypeChoices.FILE
    ):
        # A placeholder's declared size is not a completed upload.
        if created:
            item_usage(instance, initial_size=0)
        elif instance.upload_state != models.ItemUploadStateChoices.PENDING:
            item_usage(instance)


@receiver(signals.pre_delete, sender=models.Item)
def retire_item_storage(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """Physical deletion retires bytes without removing their audit identity."""
    if instance.type == models.ItemTypeChoices.DOCS:
        if models.DocsBinding.objects.filter(item=instance).exclude(state="purged").exists():
            raise ValidationError(
                "Confirm the native document purge before removing its reference."
            )
        return
    if getattr(settings, "STORAGE_GOVERNANCE_ENABLED", False):
        storage_quota.guard_metadata_change(models.StorageUsage.objects.filter(item=instance))
        usage = models.StorageUsage.objects.filter(item=instance).first()
        if usage:
            storage_quota.observe_usage(
                key=usage.key,
                size=0,
                scope_keys=usage.scope_keys,
                organization=usage.organization,
            )


@receiver(signals.post_save, sender=models.Item)
def file_post_save(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Asynchronous call to the document indexer at the end of the transaction.
    Note : Within the transaction we can have an empty content and a serialization
    error.
    """
    transaction.on_commit(partial(trigger_batch_file_indexer, instance))


@receiver(signals.post_save, sender=models.ItemAccess)
def file_access_post_save(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    """
    Asynchronous call to the document indexer at the end of the transaction.
    """
    if not created:
        transaction.on_commit(partial(trigger_batch_file_indexer, instance.item))
