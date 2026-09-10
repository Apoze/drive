"""Recover proven publications; retain uncertain writes and original versions."""

from contextlib import nullcontext
from datetime import timedelta

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from botocore.exceptions import ClientError

from core.models import Item, StorageBackend, StorageReservation, StorageResource
from core.mounts.registry import get_mount_provider
from core.services import storage_quota as quota
from core.services.mount_write_transaction import same_mount_entry
from core.services.storage_connections import storage_for_backend
from core.services.storage_integrity import verify_mount_digest, verify_s3_digest
from core.services.storage_mount_write import _stat_or_none
from core.services.storage_namespace import namespace_guard
from core.services.storage_s3_write import check_rename_source, object_head, object_version
from core.services.storage_spaces import native_connection
from wopi.utils import compute_mount_entry_version


# Each journal family has a different owner; dispatch before applying generic lease rules.
# pylint: disable-next=too-many-return-statements
def reconcile_operation(operation_id, *, move_job_id=None):  # noqa: PLR0911
    """An expired lease allows observation, never guessing that a write failed."""
    operation = StorageReservation.objects.get(pk=operation_id)
    if operation.state in {"committed", "cancelled"}:
        return operation.state
    if folder_job := operation.publication.get("folder_job_id"):
        if folder_job == str(move_job_id):
            return _reconcile_mount(operation)
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_move_job import execute_move  # noqa: PLC0415

        return execute_move(folder_job)
    if operation.publication.get("kind") in {"move", "tree_move"}:
        job = getattr(operation, "storagemovejob", None)
        if job and job.pk != move_job_id:
            # Reuse the job's grant/configuration checks and worker lock on every recovery route.
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_move_job import execute_move  # noqa: PLC0415

            return execute_move(job.pk)
    if move_job := operation.publication.get("move_job_id"):
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_move_job import execute_move  # noqa: PLC0415

        return execute_move(move_job)
    if copy_job := operation.publication.get("copy_job_id"):
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_move_job import execute_move  # noqa: PLC0415

        return execute_move(copy_job)
    if admin_job := operation.publication.get("admin_job_id"):
        # The owning job lock also fences scheduled reconciliation against a live worker.
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_admin_jobs import execute_admin_job  # noqa: PLC0415

        return execute_admin_job(admin_job)
    if operation.publication.get("kind") in {"s3_transfer", "mount_s3_transfer"}:
        # Transfer recovery verifies the digest and commits location and accounting together.
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_move_job import execute_move  # noqa: PLC0415

        return execute_move(operation.publication["job_id"])
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
    return _reconcile_mount(operation) if publication.get("backend_id") else "uncertain"


def _publication_storage(publication):
    """Recover the journaled connection, never the current default destination."""
    if connection_id := publication.get("connection_id"):
        backend = StorageBackend.objects.get(pk=connection_id)
        return storage_for_backend(backend)
    return default_storage


def _reconcile_s3(operation, *, source_check=None):
    publication = operation.publication
    storage = _publication_storage(publication)
    if publication.get("bucket") != storage.bucket_name:
        return "uncertain"
    head = object_head(storage.connection.meta.client, publication["bucket"], publication["key"])
    if (
        head.get("Metadata", {}).get("drive-operation") != str(operation.pk)
        or head.get("ContentLength") != publication["size"]
    ):
        return "uncertain"
    if digest := publication.get("sha256"):
        verify_s3_digest(
            storage.connection.meta.client, publication["bucket"], publication["key"], head, digest
        )
    check_rename_source(storage.connection.meta.client, publication["bucket"], publication)
    if source_check:
        source_check()
    with transaction.atomic():
        quota.commit(operation.pk, size=publication["size"], version=object_version(head))
        Item.objects.filter(pk=publication["item_id"]).update(
            size=publication["size"],
            **publication.get("item_update", {}),
        )
    return "committed"


def finish_mount_deletion(operation, backend):
    """Commit only a proven removal, preserving references and retained versions."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_tree_transfer import relocate_recovery_paths  # noqa: PLC0415

    with transaction.atomic():
        if anchor_id := operation.publication.get("docs_anchor"):
            from core.services.docs_anchors import finish_folder_deletion  # noqa: PLC0415

            finish_folder_deletion(anchor_id, operation.actor)
        relocate_recovery_paths(operation)
        quota.commit(operation.pk, size=0, version="missing")
        StorageResource.objects.filter(
            namespace=backend.namespace,
            provider_identity=operation.publication.get("backup_identity", ""),
            created_at__lte=operation.created_at,
        ).update(missing=True)


# Publication kinds must be observed before their distinct commit steps.
# pylint: disable-next=too-many-return-statements,too-many-branches
def _reconcile_mount(operation, *, source_check=None):  # noqa: PLR0911, PLR0912
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
        if publication.get("kind") == "delete" and publication.get("backup_path"):
            backup = _stat_or_none(provider, mount, publication["backup_path"])
            if (
                backup
                and backup.object_identity == publication.get("backup_identity")
                and (
                    not publication.get("backup_version")
                    or compute_mount_entry_version(backup) == publication["backup_version"]
                )
            ):
                finish_mount_deletion(operation, backend)
                if final:
                    # pylint: disable-next=import-outside-toplevel,cyclic-import
                    from core.services.storage_inventory import observe_entry  # noqa: PLC0415

                    observe_entry(backend, final)
                return "committed"
            if not backup and final and final.object_identity == publication.get("backup_identity"):
                quota.cancel(operation.pk, publication_ruled_out=True)
                return "cancelled"
            return "uncertain"
        if final is None:
            if publication.get("kind") == "delete":
                finish_mount_deletion(operation, backend)
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
        if (
            publication.get("kind") == "move"
            and publication.get("source_version")
            and compute_mount_entry_version(final) != publication["source_version"]
        ):
            return "uncertain"
        if publication.get("kind") in {"tree_move", "reclassify"}:
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_tree_transfer import finish_transfer  # noqa: PLC0415

            finish_transfer(operation.pk, version=compute_mount_entry_version(final))
            return "committed"
        if digest := publication.get("sha256"):
            verify_mount_digest(provider, mount, path, final, digest)
        if source_check:
            source_check()
        if publication.get("move_job_id"):
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_native_transfer import finish_native_move  # noqa: PLC0415

            finish_native_move(operation, backend, final)
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
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_resources import observe_resources  # noqa: PLC0415

        observe_resources(backend, [final])
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


def _cleanup_s3(operation):
    """Abort only journaled staging and remove only immutable retained versions."""
    publication = operation.publication
    storage = _publication_storage(publication)
    upload_id = publication.get("upload_id")
    if upload_id and publication.get("bucket") == storage.bucket_name:
        try:
            storage.connection.meta.client.abort_multipart_upload(
                Bucket=publication["bucket"],
                Key=publication["key"],
                UploadId=upload_id,
            )
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code")) != "NoSuchUpload":
                raise
    source = publication.get("source_cleanup")
    if operation.state == "committed" and source:
        cutoff = timezone.now() - timedelta(days=settings.STORAGE_BACKUP_RETENTION_DAYS)
        if (
            operation.updated_at > cutoff
            or source.get("version") in {None, "", "null"}
            or not publication.get("sha256")
        ):
            # An unversioned key has no immutable identity: preserve external replacements.
            return "retained"
        storage.connection.meta.client.delete_object(
            Bucket=publication["bucket"], Key=source["key"], VersionId=source["version"]
        )
        publication["source_retained"] = False
    return "cleaned"


# Retention and active restoration have distinct outcomes for the scheduler.
# pylint: disable-next=too-many-return-statements
def cleanup_operation(operation_id, *, move_job_id=None):  # noqa: PLR0911
    """Delete only private objects identified by this terminal operation's journal."""
    operation = StorageReservation.objects.get(pk=operation_id)
    if operation.state not in {"committed", "cancelled"}:
        return "active"
    if (
        operation.restore_jobs.filter(state__in=["queued", "running"]).exists()
        or operation.restore_jobs.filter(
            operation__state__in=["reserved", "writing", "publishing"]
        ).exists()
    ):
        return "retained"
    publication = operation.publication
    owner = (
        publication.get("job_id")
        if publication.get("kind") == "mount_s3_transfer"
        else publication.get("move_job_id")
        if operation.state == "committed"
        else None
    )
    if owner and owner != str(move_job_id):
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_move_job import execute_move  # noqa: PLC0415

        return execute_move(owner)
    publication["cleanup_checked_at"] = timezone.now().isoformat()
    StorageReservation.objects.filter(pk=operation.pk).update(publication=publication)
    if publication.get("kind") == "s3":
        if _cleanup_s3(operation) == "retained":
            return "retained"
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
                    if entry.entry_type == "folder" and any(
                        provider.iter_children(mount=mount, normalized_path=path)
                    ):
                        # Child reservations own their retained copies. Their bounded
                        # cleanup runs first; never recursively erase an unknown child.
                        return "retained"
                    provider.remove(mount=mount, normalized_path=path)
    publication["cleanup_pending"] = False
    publication["cleaned_at"] = timezone.now().isoformat()
    StorageReservation.objects.filter(pk=operation.pk).update(publication=publication)
    return "cleaned"


def restore_backup(operation_id, *, space_id, actor_id, destination, job_id=None):
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
    publication = operation.publication.get("native_source") or operation.publication
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

            def chunks():
                while piece := stream.read(64 * 1024):
                    yield piece
                if not same_mount_entry(entry, provider.stat(mount=native, normalized_path=path)):
                    raise quota.StorageWriteConflict(
                        "The retained version changed during restoration."
                    )

            return virtual.write_stream(
                mount=target,
                final_path=destination,
                must_be_missing=True,
                job_id=job_id,
                chunks=chunks(),
            )
