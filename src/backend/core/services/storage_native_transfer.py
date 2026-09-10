"""Moves into native filesystems retain one logical reference and quota charge."""

import posixpath
from contextlib import ExitStack
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import (
    Item,
    StorageBackend,
    StorageMoveJob,
    StorageResource,
    StorageResourceFavorite,
    StorageUsage,
    User,
)
from core.mounts.providers import virtual
from core.services import storage_native_transfer_source as native_source
from core.services import storage_quota as quota
from core.services.mount_write_transaction import MountWriteLimits
from core.services.storage_access import source_write_allowed
from core.services.storage_connections import storage_for_backend
from core.services.storage_copy_job import _permanent_failure, validate_copy_name
from core.services.storage_integrity import DigestReader
from core.services.storage_move_job import dispatch_move
from core.services.storage_namespace import StorageOperationBusy, advisory_guard, namespace_guard
from core.services.storage_recovery import _reconcile_mount, cleanup_operation
from core.services.storage_resources import (
    observe_resources,
    revoke_incompatible_links,
    transfer_item_links,
)
from core.services.storage_spaces import authorize, context, resolve_space_mount
from core.services.storage_transfer_location import (
    TransferLocation,
    resolve_location,
    verified_transfer_destination,
)
from wopi.services.lock import LockService
from wopi.utils import compute_mount_entry_version


def enqueue_native_transfer(*, actor, source, destination):
    """Queue a logical move; storage bytes stay unchanged until the worker admits it."""
    if source.kind != "file" or destination.backend.family != "mount":
        raise quota.StorageWriteConflict("Choose a regular file and a mounted destination folder.")
    if source.backend.family == "s3":
        if source.space.root_item_id == source.reference.pk or not source.reference.get_abilities(
            actor
        ).get("move"):
            raise quota.StorageWriteConflict("This file cannot be moved.")
    else:
        space, user, _ = context(source.mount)
        authorize(space, user, source.path, write=True)
    name = validate_copy_name(source.name)
    job, _ = StorageMoveJob.objects.get_or_create(
        actor=actor,
        kind="s3_mount_transfer" if source.backend.family == "s3" else "mount_mount_transfer",
        space=source.space,
        source_path=str(source.reference.pk),
        destination_path=str(destination.reference.pk),
        state__in=["queued", "running", "cleanup", "conflict"],
        defaults={
            "source_identity": str(source.reference.pk),
            "payload": {
                "source": source.descriptor(),
                "destination": destination.descriptor(),
                "title": name,
                "destination_title": destination.name,
                "source_tree_path": str(source.reference.path),
            },
        },
    )
    if job.payload["destination"] != destination.descriptor():
        raise quota.StorageWriteConflict("Recover the existing move before changing its target.")
    transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


def _locations(job):
    job.actor.refresh_from_db()
    if job.kind == "mount_mount_transfer" and job.payload.get("native_source"):
        # Its original path may already be quarantined after a lost metadata commit.
        source = TransferLocation(
            StorageResource.objects.get(pk=job.source_path),
            job.space,
            job.payload["source"]["path"],
            resolve_space_mount(job.space_id, job.actor),
        )
        native_source.check_source(job)
    else:
        source = resolve_location(job.source_path, job.actor, space_id=job.space_id)
    destination = resolve_location(
        job.destination_path,
        job.actor,
        space_id=job.payload["destination"]["space"],
        destination=True,
    )
    if (source.descriptor(), destination.descriptor()) != (
        job.payload["source"],
        job.payload["destination"],
    ):
        raise quota.StorageWriteConflict("A transfer location changed.")
    if source.backend.family == "s3" and (
        not source.reference.get_abilities(job.actor).get("move")
        or LockService(source.reference).is_locked()
    ):
        raise quota.StorageWriteConflict(
            "Source permission changed or an editing session is active."
        )
    return source, destination


def _check_source(job, reader=None):
    source, _ = _locations(job)
    expected = job.payload["observation"]
    changed = (
        source.observe() != expected
        if source.backend.family == "s3"
        else compute_mount_entry_version(native_source.check_source(job)) != expected["version"]
    )
    if changed or (reader is not None and reader.size != expected["size"]):
        raise quota.StorageWriteConflict(
            "The source changed during transfer; its bytes were retained."
        )
    if reader and source.backend.family == "mount":
        reader.stream.close()
    return reader.digest.hexdigest() if reader else job.operation.publication["sha256"]


def prepare_move_target(job_id, usage, actor):
    """Creator-attributed destinations keep the file's creator, not the moving editor."""
    if not usage.space_id or not usage.space.attribute_to_creator:
        return usage
    job = StorageMoveJob.objects.get(pk=job_id, actor=actor)
    creator = (
        Item.objects.select_related("creator").get(pk=job.source_path).creator
        if job.kind == "s3_mount_transfer"
        else StorageUsage.objects.select_related("owner")
        .get(key=job.payload["native_source"]["usage_key"])
        .owner
    )
    if creator is None:
        raise quota.StorageWriteConflict("Assign the file's ownership before moving it.")
    scopes = [key for key in usage.scope_keys if not key.startswith(("user:", "user-backend:"))]
    scopes += [f"user:{creator.pk}", f"user-backend:{creator.pk}:{usage.backend.namespace}"]
    return quota.observe_usage(
        key=usage.key,
        size=0,
        scope_keys=scopes,
        owner=creator,
        space=usage.space,
        organization=usage.organization,
    )


def admit_native_move(job_id, target_usage, actor, space):
    """Reserve only newly charged scopes and bind the destination path to this journal."""
    job = StorageMoveJob.objects.select_for_update().get(
        pk=job_id, actor=actor, kind__in=["s3_mount_transfer", "mount_mount_transfer"]
    )
    if job.operation_id or job.payload["destination"]["space"] != str(space.pk):
        raise quota.StorageWriteConflict("This move already has a publication journal.")
    User.objects.select_for_update(no_key=True).get(pk=actor.pk)
    usage = StorageUsage.objects.select_for_update().get(
        **(
            {"item_id": job.source_path}
            if job.kind == "s3_mount_transfer"
            else {"key": job.payload["native_source"]["usage_key"]}
        )
    )
    observation = job.payload["observation"]
    if usage.size != observation["size"] or target_usage.size:
        raise quota.StorageWriteConflict("Refresh the storage inventory before moving this file.")
    usage.version = observation["version"]
    usage.save(update_fields=["version", "observed_at"])
    operation = quota.admit(
        key=usage.key,
        actor=actor,
        size=usage.size,
        target_scopes=target_usage.scope_keys,
        lifetime=timedelta(hours=24),
        publication_key=quota.resource_key(f"path:{space.backend.namespace}:{target_usage.path}"),
    )
    job.operation, job.state = operation, "running"
    job.save(update_fields=["operation", "state", "updated_at"])
    return operation, {
        "move_job_id": str(job.pk),
        "destination_usage_id": str(target_usage.pk),
        "source_connection_id": job.payload["source"]["backend"],
        "source_retained": True,
        **(
            {"native_source": job.payload["native_source"]}
            if job.kind == "mount_mount_transfer"
            else {}
        ),
        "target_attribution": {
            "owner_id": str(target_usage.owner_id) if target_usage.owner_id else None,
            "space_id": str(target_usage.space_id) if target_usage.space_id else None,
            "organization": target_usage.organization,
            "path": target_usage.path,
        },
    }


def finish_native_move(operation, backend, final):
    """Switch location and logical ownership in the same commit as native identity binding."""
    job = StorageMoveJob.objects.select_related("actor", "operation").get(
        pk=operation.publication["move_job_id"]
    )
    _check_source(job)
    _, destination = _locations(job)
    if job.kind == "mount_mount_transfer":
        native_source.check_source(job, retain=True)
    with transaction.atomic():
        _, destination = _locations(job)
        item = (
            Item.objects.select_for_update().get(pk=job.source_path)
            if job.kind == "s3_mount_transfer"
            else None
        )
        if item and item.hard_deleted_at:
            raise quota.StorageWriteConflict("The source is no longer active.")
        quota.bind_native_identity(
            operation.resource_key,
            native_key=quota.resource_key(f"mount:{backend.namespace}:{final.object_identity}"),
            provider_identity=final.object_identity,
        )
        quota.commit(
            operation.pk, size=int(final.size or 0), version=compute_mount_entry_version(final)
        )
        StorageUsage.objects.filter(
            pk=operation.publication["destination_usage_id"], size=0
        ).delete()
        StorageUsage.objects.filter(key=operation.resource_key).update(item=None, backend=backend)
        StorageResource.objects.update_or_create(
            pk=job.source_path,
            defaults={
                "namespace": backend.namespace,
                "identity_key": quota.resource_key(f"reference:{operation.resource_key}"),
                "path": operation.publication["target_attribution"]["path"],
                "parent_path": posixpath.dirname(
                    operation.publication["target_attribution"]["path"]
                )
                or "/",
                "name": final.name,
                "kind": "file",
                "size": int(final.size or 0),
                "provider_identity": final.object_identity,
                "modified_at": final.modified_at,
                "version": compute_mount_entry_version(final),
                "missing": False,
            },
        )
        if item:
            transfer_item_links(
                item, destination.space, posixpath.join(destination.path, job.payload["title"])
            )
        else:
            StorageResourceFavorite.objects.filter(resource_id=job.source_path).update(
                space=destination.space
            )
        observe_resources(backend, [final])
        # Metadata removal cannot delete S3 bytes; their journal retains the exact source location.
        if item:
            Item.objects.filter(pk=item.pk).delete()
        revoke_incompatible_links(job.source_path)
        job.state, job.reason = "cleanup", "Destination verified; source cleanup is pending."
        job.payload = {**job.payload, "source_retained": True, "result": job.source_path}
        job.save(update_fields=["state", "reason", "payload", "updated_at"])


# Each journal state has a distinct retry or publication action.
# pylint: disable-next=too-many-branches
def execute_native_transfer(job):  # noqa: PLR0912
    """Recover uncertain publication before considering any second write."""
    if job.state == "cleanup":
        return (
            cleanup_native_source(job)
            if job.kind == "mount_mount_transfer"
            else cleanup_s3_source(job)
        )
    if job.state in {"done", "failed", "conflict"}:
        return job.state
    try:
        if job.operation_id and job.operation.state == "committed":
            job.state = "cleanup"
            job.save(update_fields=["state", "updated_at"])
            return "cleanup"
        source, destination = _locations(job)
        with ExitStack() as guards:
            guards.enter_context(advisory_guard(f"storage-editor:{source.reference.pk}"))
            for backend in sorted(
                {source.backend, destination.backend}, key=lambda row: str(row.namespace)
            ):
                guards.enter_context(namespace_guard(backend, exclusive=True))
            if job.operation_id:
                if job.operation.state == "publishing":
                    if (
                        _reconcile_mount(job.operation, source_check=lambda: _check_source(job))
                        != "committed"
                    ):
                        raise quota.StorageWriteConflict(
                            "The destination publication needs verification."
                        )
                else:
                    quota.cancel(job.operation_id)
                    cleanup_operation(job.operation_id)
                    raise quota.StorageWriteConflict("The move was interrupted before publication.")
            else:
                observation = source.observe()
                job.payload = {**job.payload, "observation": observation}
                job.state = "running"
                job.save(update_fields=["payload", "state", "updated_at"])
                if job.kind == "mount_mount_transfer":
                    native_source.prepare_source(job)
                with source.open(observation) as stream:
                    reader = DigestReader(stream)
                    virtual.write_stream(
                        mount=destination.mount,
                        final_path=posixpath.join(destination.path, job.payload["title"]),
                        chunks=iter(lambda: reader.read(1024 * 1024), b""),
                        limits=MountWriteLimits(max_bytes=observation["size"]),
                        must_be_missing=True,
                        move_job_id=job.pk,
                        source_check=lambda: _check_source(job, reader),
                    )
        job.refresh_from_db()
        return job.state
    except StorageOperationBusy:
        return "busy"
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        job.refresh_from_db()
        uncertain = job.operation_id and job.operation.state == "publishing"
        if _permanent_failure(exc):
            job.state = "conflict" if uncertain else "failed"
            job.reason = str(getattr(exc, "detail", "The move needs verification."))[:255]
        else:
            job.state = "running" if job.operation_id else "queued"
            job.reason = "Storage unavailable; this move will be retried."
        job.save(update_fields=["state", "reason", "updated_at"])
        return job.state


@transaction.atomic
def finish_source_cleanup(job):
    """Record collection without changing the destination's logical charge."""
    operation = job.operation
    operation.publication = {
        **operation.publication,
        "source_retained": False,
        "cleanup_pending": False,
    }
    operation.save(update_fields=["publication", "updated_at"])
    job.state, job.reason = "done", ""
    job.payload = {**job.payload, "source_retained": False}
    job.save(update_fields=["state", "reason", "payload", "updated_at"])


def source_s3_cleanup_access(job):
    """Recheck the original writable subtree, even after a long destination checksum."""
    job.actor.refresh_from_db()
    source = job.payload["source"]
    backend = StorageBackend.objects.get(pk=source["backend"])
    job.space.refresh_from_db()
    if (
        not job.actor.is_active
        or not job.space.enabled
        or not backend.enabled
        or backend.configuration_generation != source["generation"]
    ):
        raise quota.StorageWriteConflict(
            "Source retained: transfer permissions or configuration changed."
        )
    if not source_write_allowed(job.space, job.actor, job.payload["source_tree_path"]):
        raise quota.StorageWriteConflict("Source retained: original write permission was removed.")
    return backend


def cleanup_s3_source(job):
    """Collect only an immutable captured S3 version after destination revalidation."""
    operation = job.operation
    cutoff = timezone.now() - timedelta(days=settings.STORAGE_BACKUP_RETENTION_DAYS)
    if operation.updated_at > cutoff:
        return "cleanup"
    try:
        version = job.payload["observation"].get("version_id")
        if version in {None, "", "null"}:
            raise quota.StorageWriteConflict(
                "Source retained: storage has no immutable version identity."
            )
        source = job.payload["source"]
        backend = source_s3_cleanup_access(job)
        with verified_transfer_destination(job, backend):
            backend = source_s3_cleanup_access(job)
            storage = storage_for_backend(backend)
            storage.connection.meta.client.delete_object(
                Bucket=storage.bucket_name, Key=source["path"], VersionId=version
            )
            finish_source_cleanup(job)
            return "done"
    except StorageOperationBusy:
        return "busy"
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        job.reason = str(getattr(exc, "detail", "Source retained: cleanup needs verification."))[
            :255
        ]
        job.save(update_fields=["reason", "updated_at"])
        return "cleanup"


def cleanup_native_source(job):
    """Collect the private source only while its verified native destination remains intact."""
    operation = job.operation
    cutoff = timezone.now() - timedelta(days=settings.STORAGE_BACKUP_RETENTION_DAYS)
    if operation.updated_at > cutoff:
        return "cleanup"
    try:
        if operation.state != "committed" or not operation.publication.get("source_retained"):
            raise quota.StorageWriteConflict("The transfer publication needs verification.")
        if (
            operation.restore_jobs.filter(state__in=["queued", "running"]).exists()
            or operation.restore_jobs.filter(
                operation__state__in=["reserved", "writing", "publishing"]
            ).exists()
        ):
            return "cleanup"
        job.actor.refresh_from_db()
        with (
            verified_transfer_destination(job, job.space.backend),
            native_source.retained_source_context(job) as target,
        ):
            provider, mount, info = target
            if native_source.verify_retained_source(job, provider, mount, info):
                provider.remove(mount=mount, normalized_path=info["backup_path"])
            finish_source_cleanup(job)
            return "done"
    except StorageOperationBusy:
        return "busy"
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        job.reason = str(getattr(exc, "detail", "Source retained: cleanup needs verification."))[
            :255
        ]
        job.save(update_fields=["reason", "updated_at"])
        return "cleanup"
