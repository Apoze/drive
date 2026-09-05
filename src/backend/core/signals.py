"""
Declare and configure the signals for the impress core application
"""

from functools import partial

from django.conf import settings
from django.db import transaction
from django.db.models import signals
from django.dispatch import receiver

from core.services import storage_quota
from core.services.storage_inventory import item_usage

from . import models
from .tasks.search import trigger_batch_file_indexer


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
    if getattr(settings, "STORAGE_GOVERNANCE_ENABLED", False):
        storage_quota.guard_metadata_change(models.StorageUsage.objects.filter(item=instance))
        key = storage_quota.resource_key(f"item:{instance.pk}")
        usage = models.StorageUsage.objects.filter(key=key).first()
        if usage:
            storage_quota.observe_usage(
                key=key,
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
