"""Move a mounted file into native S3 with one identity and quota substitution."""

import posixpath
import uuid
from contextlib import ExitStack, contextmanager
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from lasuite.malware_detection import malware_detection

from core.malware_detection import analysis_kwargs
from core.models import (
    Item,
    StorageMoveJob,
    StorageResource,
    StorageUsage,
    User,
)
from core.mounts.providers import virtual
from core.services import storage_inventory as inventory
from core.services import storage_native_transfer_source as native_source
from core.services import storage_quota as quota
from core.services.s3_streaming import stream_to_s3_object
from core.services.storage_connections import storage_for_item
from core.services.storage_copy_job import _permanent_failure, validate_copy_name
from core.services.storage_file_transfer import S3TransferWrite
from core.services.storage_integrity import DigestReader, verify_mount_digest
from core.services.storage_mount_write import _stat_or_none
from core.services.storage_move_job import dispatch_move
from core.services.storage_namespace import StorageOperationBusy, namespace_guard
from core.services.storage_recovery import cleanup_operation
from core.services.storage_resources import bind_legacy_shares, transfer_native_links
from core.services.storage_s3_write import object_head, object_version
from core.services.storage_spaces import authorize, context, namespace_path, resolve_space_mount
from core.services.storage_transfer_location import resolve_location, verified_transfer_destination
from wopi.services.lock import guard_mount_editors
from wopi.utils import compute_mount_entry_version


def enqueue_mount_s3_move(*, actor, source, destination):
    """Queue a stable native reference, without exposing a provisional S3 Item."""
    if (
        source.kind != "file"
        or source.backend.family != "mount"
        or destination.backend.family != "s3"
    ):
        raise quota.StorageWriteConflict("Select a mounted file and an object-storage folder.")
    validate_copy_name(source.name)
    space, user, _ = context(source.mount)
    authorize(space, user, source.path, write=True)
    job, _ = StorageMoveJob.objects.get_or_create(
        actor=actor,
        kind="mount_s3_transfer",
        space=source.space,
        source_path=str(source.reference.pk),
        destination_path=str(destination.reference.pk),
        state__in=["queued", "running", "cleanup", "conflict"],
        defaults={
            "source_identity": source.reference.provider_identity,
            "payload": {
                "source": source.descriptor(),
                "destination": destination.descriptor(),
                "title": source.name,
                "destination_title": destination.name,
            },
        },
    )
    if job.payload["destination"] != destination.descriptor():
        raise quota.StorageWriteConflict("Recover the existing move before changing its target.")
    transaction.on_commit(lambda: dispatch_move(job.pk))
    return job


# The source adapter retains the same multipart protocol with native source metadata.
# pylint: disable-next=too-many-instance-attributes
class MountedS3TransferWrite(S3TransferWrite):
    """Reuse multipart integrity/recovery; retain the native source before metadata commit."""

    # Source initialization deliberately replaces the S3-only source connection.
    # pylint: disable-next=super-init-not-called
    def __init__(self, job):
        self.job = job
        self.operation = job.operation if job.operation_id else None
        self.source = StorageResource.objects.get(pk=job.source_path)
        self.target = resolve_location(job.destination_path, job.actor, destination=True).reference
        self.reader = None
        self.is_copy = self.same_object = False
        self.storage = storage_for_item(self.target)
        self.client, self.bucket = self.storage.connection.meta.client, self.storage.bucket_name
        prefix = self.target.storage_backend.configuration.get("prefix", "").strip("/")
        prefix = posixpath.join(prefix, ".drive-transfers", str(job.pk))
        if self.operation:
            marker = f"item/{self.source.pk}/{job.payload['title']}"
            prefix = self.operation.publication["key"].removesuffix(marker).rstrip("/")
        planned = Item(
            pk=self.source.pk,
            type="file",
            filename=job.payload["title"],
            storage_backend=self.target.storage_backend,
            storage_space=self.target.storage_space,
            storage_key_prefix=prefix,
        )
        self.prefix = planned.storage_key_prefix
        self.key = planned.file_key
        self.original_key = job.payload["source"]["path"]
        self.size = (
            self.operation.publication["source_size"] if self.operation else self.source.size
        )
        self.head = {}

    def check_locations(self):
        """Source access remains mandatory after its private quarantine rename."""
        self.job.actor.refresh_from_db()
        self.source.refresh_from_db()
        source = self.job.payload["source"]
        if (
            self.source.missing and not (self.operation and self.operation.state == "publishing")
        ) or str(self.source.pk) != source["id"]:
            raise quota.StorageWriteConflict("The source reference changed.")
        target = resolve_location(self.job.destination_path, self.job.actor, destination=True)
        if target.descriptor() != self.job.payload["destination"]:
            raise quota.StorageWriteConflict("The destination folder changed.")
        self.target = target.reference

    @contextmanager
    def source_context(self):
        """Pin the authorized native parent while operating on its journaled private sibling."""
        descriptor = self.job.payload["source"]
        mount = resolve_space_mount(descriptor["space"], self.job.actor)
        if not mount:
            raise quota.StorageWriteConflict("Source write permission was removed.")
        # Native transfer shares the virtual provider's confinement and authorization boundary.
        # pylint: disable-next=protected-access
        with virtual._target(  # noqa: SLF001
            mount, descriptor["path"], write=True
        ) as native_target:
            space, _, _, _, path = native_target
            if (
                str(space.backend_id) != descriptor["backend"]
                or space.backend.configuration_generation != descriptor["generation"]
                or space.backend.namespace != self.source.namespace
                or namespace_path(space.backend, path) != self.source.path
            ):
                raise quota.StorageWriteConflict("The source location changed.")
            guard_mount_editors(space.backend, path)
            yield native_target

    def check_source(self):
        self.check_locations()
        with self.source_context() as (_, _, provider, native, path):
            info = self.operation.publication
            retained = _stat_or_none(provider, native, info["backup_path"])
            entry = retained or provider.stat(mount=native, normalized_path=path)
            if (
                entry.object_identity != info["backup_identity"]
                or compute_mount_entry_version(entry) != info["source_observed_version"]
                or entry.size != self.size
            ):
                raise quota.StorageWriteConflict(
                    "The source changed; both locations were retained."
                )
            return entry

    def prepare(self):
        self.check_locations()
        if object_head(self.client, self.bucket, self.key):
            raise quota.StorageWriteConflict("The destination object already exists.")
        with self.source_context() as (space, _, provider, native, path):
            if not callable(getattr(provider, "rename_no_replace", None)):
                raise quota.StorageWriteConflict("This storage cannot safely retain the source.")
            entry = provider.stat(mount=native, normalized_path=path)
            if entry.entry_type != "file" or entry.object_identity != self.job.source_identity:
                raise quota.StorageWriteConflict("The source identity changed.")
            usage = inventory.observe_entry(space.backend, entry)
            bind_legacy_shares(space.backend, path)
            self.size = int(entry.size or 0)
            attribution = inventory.item_attribution(
                Item(
                    creator=usage.owner or self.job.actor,
                    storage_backend=self.target.storage_backend,
                    storage_space=self.target.storage_space,
                )
            )
            inventory.refresh_policy(
                attribution["owner"] or self.job.actor, organization=attribution["organization"]
            )
            with transaction.atomic():
                User.objects.select_for_update(no_key=True).get(pk=self.job.actor_id)
                usage = StorageUsage.objects.select_for_update().get(pk=usage.pk)
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
                self.operation.publication = {
                    "kind": "mount_s3_transfer",
                    "job_id": str(self.job.pk),
                    "connection_id": str(self.target.storage_backend_id),
                    "configuration_generation": (
                        self.target.storage_backend.configuration_generation
                    ),
                    "key": self.key,
                    "bucket": self.bucket,
                    "backend_id": str(space.backend_id),
                    "source_path": path,
                    "path": path,
                    "source_kind": "file",
                    "backup_size": self.size,
                    "backup_path": posixpath.join(
                        posixpath.dirname(path), f".drive-txn-{self.operation.pk.hex}.moved"
                    ),
                    "backup_identity": entry.object_identity,
                    "source_observed_version": compute_mount_entry_version(entry),
                    "source_size": self.size,
                    "cleanup_pending": False,
                    "creator_id": str(usage.owner_id or self.job.actor_id),
                    "target_attribution": {
                        "organization": attribution["organization"],
                        "owner_id": str(attribution["owner"].pk) if attribution["owner"] else None,
                        "space_id": str(self.target.storage_space_id),
                        "path": "",
                    },
                }
                self.operation.save(update_fields=["publication", "updated_at"])
                self.job.operation, self.job.state = self.operation, "running"
                self.job.save(update_fields=["operation", "state", "updated_at"])

    def publish(self, size):
        """Release the native read handle before quarantine; SMB may deny an open-file rename."""
        if self.reader:
            self.reader.stream.close()
        super().publish(size)

    def finish(self, head):
        """Verify the retained source, then switch reference, charge and favorites atomically."""
        self.check_source()
        with self.source_context() as (_, _, provider, native, path):
            info = self.operation.publication
            backup = _stat_or_none(provider, native, info["backup_path"])
            if backup is None:
                provider.rename_no_replace(
                    mount=native, src_normalized_path=path, dst_normalized_path=info["backup_path"]
                )
            entry = self.check_source()
            verify_mount_digest(provider, native, info["backup_path"], entry, info["sha256"])
            with transaction.atomic():
                self.check_locations()
                quota.commit(self.operation.pk, size=self.size, version=object_version(head))
                item = Item.objects.create_child(
                    parent=self.target,
                    id=self.source.pk,
                    share_link_nonce=uuid.uuid4(),
                    type="file",
                    title=self.job.payload["title"],
                    filename=self.job.payload["title"],
                    creator_id=info["creator_id"],
                    mimetype=self.job.payload["mimetype"],
                    size=0,
                )
                # The Item is first visible with the existing charge at this transaction's commit.
                StorageUsage.objects.filter(item=item, size=0).delete()
                StorageUsage.objects.filter(key=self.operation.resource_key).update(
                    item=item,
                    backend=self.target.storage_backend,
                    native_key=None,
                    provider_identity="",
                )
                Item.objects.filter(pk=item.pk).update(
                    size=self.size, upload_state="analyzing", storage_key_prefix=self.prefix
                )
                StorageResource.objects.filter(pk=self.source.pk).update(missing=True)
                transfer_native_links(self.source, item)
                self.operation.publication = {
                    **info,
                    "source_retained": True,
                    "cleanup_pending": True,
                }
                self.operation.save(update_fields=["publication", "updated_at"])
                self.job.state, self.job.reason = (
                    "cleanup",
                    "Destination verified; source retained.",
                )
                self.job.payload = {
                    **self.job.payload,
                    "source_retained": True,
                    "result": str(item.pk),
                }
                self.job.save(update_fields=["state", "reason", "payload", "updated_at"])
                item.refresh_from_db()
                transaction.on_commit(
                    lambda: malware_detection.analyse_file(
                        item.file_key, item_id=item.pk, **analysis_kwargs(item)
                    )
                )


def execute_mount_s3_move(job):
    """One job lock owns multipart publication, native quarantine and crash recovery."""
    if job.state == "cleanup":
        return cleanup_mount_source(job)
    if job.state in {"done", "failed", "conflict"}:
        return job.state
    try:
        if job.operation_id and job.operation.state == "committed":
            job.state = "cleanup"
            job.save(update_fields=["state", "updated_at"])
            return job.state
        writer = MountedS3TransferWrite(job)
        with ExitStack() as guards:
            for backend in sorted(
                {job.space.backend, writer.target.storage_backend},
                key=lambda entry: str(entry.namespace),
            ):
                guards.enter_context(namespace_guard(backend, exclusive=True))
            if job.operation_id:
                writer.recover()
            else:
                source = resolve_location(job.source_path, job.actor, space_id=job.space_id)
                observation = source.observe()
                job.payload = {**job.payload, "mimetype": observation["mimetype"]}
                job.save(update_fields=["payload", "updated_at"])
                writer.prepare()
                with source.open(observation) as stream:
                    writer.reader = DigestReader(stream)
                    stream_to_s3_object(
                        s3_client=writer.client,
                        bucket=writer.bucket,
                        key=writer.key,
                        body_stream=writer.reader,
                        content_type=observation["mimetype"],
                        expected_bytes=writer.size,
                        max_bytes=writer.size,
                        write_context=writer,
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


def cleanup_mount_source(job):
    """Recheck both permissions and verified destination before private backup collection."""
    operation = job.operation
    info = operation.publication
    cutoff = timezone.now() - timedelta(days=settings.STORAGE_BACKUP_RETENTION_DAYS)
    if operation.updated_at > cutoff:
        return "cleanup"
    try:
        if operation.state != "committed" or not info.get("source_retained"):
            raise quota.StorageWriteConflict("The transfer publication needs verification.")
        job.actor.refresh_from_db()
        with (
            verified_transfer_destination(job, job.space.backend),
            native_source.retained_source_context(job) as target,
        ):
            provider, native, retained = target
            native_source.verify_retained_source(job, provider, native, retained)
            if cleanup_operation(operation.pk, move_job_id=job.pk) != "cleaned":
                return "cleanup"
            operation.refresh_from_db()
            operation.publication = {**operation.publication, "source_retained": False}
            with transaction.atomic():
                operation.save(update_fields=["publication", "updated_at"])
                job.state, job.reason = "done", ""
                job.payload = {**job.payload, "source_retained": False}
                job.save(update_fields=["state", "reason", "payload", "updated_at"])
            return "done"
    except StorageOperationBusy:
        return "busy"
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        job.reason = str(getattr(exc, "detail", "Source retained: cleanup needs verification."))[
            :255
        ]
        job.save(update_fields=["reason", "updated_at"])
        return "cleanup"
