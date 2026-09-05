"""Recover proven publications; retain uncertain writes and original versions."""

from contextlib import nullcontext
from datetime import timedelta

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from botocore.exceptions import ClientError

from core.models import Item, StorageBackend, StorageReservation
from core.mounts.registry import get_mount_provider
from core.services import storage_quota as quota
from core.services.storage_mount_write import _stat_or_none
from core.services.storage_namespace import namespace_guard
from core.services.storage_s3_write import object_head, object_version
from core.services.storage_spaces import native_connection
from wopi.utils import compute_mount_entry_version


def reconcile_operation(operation_id):
    """An expired lease allows observation, never guessing that a write failed."""
    operation = StorageReservation.objects.get(pk=operation_id)
    if operation.state in {"committed", "cancelled"}:
        return operation.state
    if operation.expires_at > timezone.now():
        return "active"
    if operation.state in {"reserved", "writing"}:
        # begin_publication rejects expired operations, even if their worker wakes.
        quota.cancel(operation.pk)
        cleanup_operation(operation.pk)
        return "cancelled"
    publication = operation.publication
    if publication.get("kind") == "s3":
        return _reconcile_s3(operation)
    if publication.get("backend_id"):
        return _reconcile_mount(operation)
    return "uncertain"


def _reconcile_s3(operation):
    publication = operation.publication
    if publication.get("bucket") != default_storage.bucket_name:
        return "uncertain"
    head = object_head(
        default_storage.connection.meta.client, publication["bucket"], publication["key"]
    )
    if (
        head.get("Metadata", {}).get("drive-operation") != str(operation.pk)
        or head.get("ContentLength") != publication["size"]
    ):
        return "uncertain"
    with transaction.atomic():
        quota.commit(operation.pk, size=publication["size"], version=object_version(head))
        Item.objects.filter(pk=publication["item_id"]).update(
            size=publication["size"],
            **publication.get("item_update", {}),
        )
    return "committed"


# pylint: disable-next=too-many-return-statements
def _reconcile_mount(operation):  # noqa: PLR0911
    publication = operation.publication
    backend = StorageBackend.objects.get(pk=publication["backend_id"])
    mount = {**native_connection(backend), "_deny_reparse": True}
    provider = get_mount_provider(mount["provider"])
    path = publication["path"]
    confine = getattr(provider, "confine", None)
    with (
        namespace_guard(backend, exclusive=True, recovery=True),
        confine(mount=mount, normalized_path=path) if confine else nullcontext(),
    ):
        final = _stat_or_none(provider, mount, path)
        if final is None:
            if publication.get("kind") == "delete":
                # pylint: disable-next=import-outside-toplevel,cyclic-import
                from core.services.storage_tree_transfer import (  # noqa: PLC0415
                    relocate_recovery_paths,
                )

                relocate_recovery_paths(operation)
                quota.commit(operation.pk, size=0, version="missing")
                return "committed"
            backup_path = publication.get("backup_path")
            if backup_path:
                backup = _stat_or_none(provider, mount, backup_path)
                if backup and backup.object_identity == publication.get("backup_identity"):
                    provider.rename_no_replace(
                        mount=mount, src_normalized_path=backup_path, dst_normalized_path=path
                    )
                    quota.cancel(operation.pk, publication_ruled_out=True)
                    return "cancelled"
            return "uncertain"
        identity = publication.get("staging_identity") or publication.get("source_identity")
        if final.object_identity != identity or int(final.size or 0) != publication["size"]:
            if publication.get("kind") == "mount" and final.object_identity == publication.get(
                "backup_identity"
            ):
                quota.cancel(operation.pk, publication_ruled_out=True)
                return "cancelled"
            return "uncertain"
        if publication.get("kind") in {"tree_move", "reclassify"}:
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_tree_transfer import finish_transfer  # noqa: PLC0415

            finish_transfer(operation.pk, version=compute_mount_entry_version(final))
            return "committed"
        with transaction.atomic():
            quota.bind_native_identity(
                operation.resource_key,
                native_key=quota.resource_key(f"mount:{backend.namespace}:{identity}"),
                provider_identity=identity,
            )
            quota.commit(
                operation.pk, size=publication["size"], version=compute_mount_entry_version(final)
            )
        return "committed"


def reconcile_expired_operations():
    """Bound each periodic pass; slow/unavailable storage is retried separately."""
    return (
        StorageReservation.objects.filter(
            state__in=["reserved", "writing", "publishing"],
            expires_at__lte=timezone.now(),
        )
        .order_by("expires_at")
        .values_list("pk", flat=True)[:200]
    )


def cleanup_candidates():
    """Cancelled streams and expired retained copies are retried until confirmed."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from django.db.models import Q  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(days=settings.STORAGE_BACKUP_RETENTION_DAYS)
    return (
        StorageReservation.objects.filter(
            Q(state="cancelled") | Q(state="committed", updated_at__lte=cutoff),
            publication__cleanup_pending=True,
        )
        .order_by(F("publication__cleanup_checked_at").asc(nulls_first=True), "updated_at")
        .values_list("pk", flat=True)[:200]
    )


def cleanup_operation(operation_id):
    """Delete only private objects identified by this terminal operation's journal."""
    operation = StorageReservation.objects.get(pk=operation_id)
    if operation.state not in {"committed", "cancelled"}:
        return "active"
    publication = operation.publication
    publication["cleanup_checked_at"] = timezone.now().isoformat()
    StorageReservation.objects.filter(pk=operation.pk).update(publication=publication)
    if publication.get("kind") == "s3":
        upload_id = publication.get("upload_id")
        if upload_id and publication.get("bucket") == default_storage.bucket_name:
            try:
                default_storage.connection.meta.client.abort_multipart_upload(
                    Bucket=publication["bucket"],
                    Key=publication["key"],
                    UploadId=upload_id,
                )
            except ClientError as exc:
                if str(exc.response.get("Error", {}).get("Code")) != "NoSuchUpload":
                    raise
    elif publication.get("backend_id"):
        backend = StorageBackend.objects.get(pk=publication["backend_id"])
        mount = {**native_connection(backend), "_deny_reparse": True}
        provider = get_mount_provider(mount["provider"])
        cutoff = timezone.now() - timedelta(days=settings.STORAGE_BACKUP_RETENTION_DAYS)
        with namespace_guard(backend, exclusive=True, allow_maintenance=True):
            for path_field, identity_field in (
                ("temp_path", "staging_identity"),
                ("backup_path", "backup_identity"),
            ):
                path = publication.get(path_field)
                if not path:
                    continue
                confine = getattr(provider, "confine", None)
                with confine(mount=mount, normalized_path=path) if confine else nullcontext():
                    entry = _stat_or_none(provider, mount, path)
                    if entry is None:
                        continue
                    if entry.object_identity != publication.get(identity_field):
                        return "uncertain"
                    if path_field == "backup_path" and (
                        operation.updated_at > cutoff
                        or (entry.modified_at and entry.modified_at > cutoff)
                    ):
                        return "retained"
                    provider.remove(mount=mount, normalized_path=path)
    publication["cleanup_pending"] = False
    publication["cleaned_at"] = timezone.now().isoformat()
    StorageReservation.objects.filter(pk=operation.pk).update(publication=publication)
    return "cleaned"


def restore_backup(operation_id, *, space_id, actor_id, destination):
    """An operator restores a retained version as a new, quota-governed file."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.models import User  # noqa: PLC0415

    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.mounts.providers import virtual  # noqa: PLC0415

    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_spaces import resolve_space_mount  # noqa: PLC0415

    actor = User.objects.get(pk=actor_id, is_active=True, is_superuser=True)
    target = resolve_space_mount(space_id, actor)
    if not target:
        raise quota.StorageWriteConflict("The restoration destination is not accessible.")
    operation = StorageReservation.objects.get(pk=operation_id, state="committed")
    publication = operation.publication
    if not publication.get("backup_path"):
        raise quota.StorageWriteConflict("No retained version is recorded for this operation.")
    backend = StorageBackend.objects.get(pk=publication["backend_id"])
    native = {**native_connection(backend), "_deny_reparse": True}
    provider = get_mount_provider(native["provider"])
    path = publication["backup_path"]
    confine = getattr(provider, "confine", None)
    with (
        namespace_guard(backend, allow_maintenance=True),
        confine(mount=native, normalized_path=path) if confine else nullcontext(),
    ):
        entry = provider.stat(mount=native, normalized_path=path)
        if entry.entry_type != "file" or entry.object_identity != publication.get(
            "backup_identity"
        ):
            raise quota.StorageWriteConflict("The retained version is no longer available.")
        with provider.open_read(mount=native, normalized_path=path) as stream:
            return virtual.write_stream(
                mount=target,
                final_path=destination,
                must_be_missing=True,
                chunks=iter(lambda: stream.read(64 * 1024), b""),
            )
