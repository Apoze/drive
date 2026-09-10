"""Resolve logical transfer endpoints while keeping S3 and provider IO separate."""

import mimetypes
from contextlib import ExitStack, closing, contextmanager
from dataclasses import dataclass

from rest_framework.exceptions import NotFound

from core.models import Item, StorageResource, StorageSpace
from core.mounts.providers import virtual
from core.services.storage_connections import storage_for_item
from core.services.storage_integrity import verify_mount_digest, verify_s3_digest
from core.services.storage_namespace import advisory_guard, namespace_guard
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_resources import resolve_mounted, resolve_resource_space
from core.services.storage_s3_write import object_head, object_version
from core.services.storage_spaces import resolve_space_mount
from wopi.services.lock import LockService, guard_mount_editors
from wopi.utils import compute_mount_entry_version


@dataclass
class TransferLocation:
    """A permitted reference with the native read contract needed by transfer workers."""

    reference: Item | StorageResource
    space: StorageSpace
    path: str
    mount: dict | None = None

    @property
    def backend(self):
        """The physical connection is never an end-user destination identifier."""
        return self.space.backend

    @property
    def kind(self):
        """Retain native metadata without manufacturing Item rows for mounted files."""
        return self.reference.type if isinstance(self.reference, Item) else self.reference.kind

    @property
    def name(self):
        """A filename is distinct from an object key or a connection's native root."""
        if self.space.root_item_id == self.reference.pk or (
            self.backend.family == "mount" and self.path == "/"
        ):
            return self.space.name
        return (
            (self.reference.filename or self.reference.title)
            if isinstance(self.reference, Item)
            else self.reference.name
        )

    def descriptor(self):
        """Fence configuration and location changes after admission to the queue."""
        return {
            "id": str(self.reference.pk),
            "space": str(self.space.pk),
            "backend": str(self.backend.pk),
            "generation": self.backend.configuration_generation,
            "path": self.path,
        }

    def observe(self):
        """Observe the actual source version, never infer integrity from an ETag."""
        if self.kind == "docs":
            from core.models import StorageUsage  # noqa: PLC0415

            usage = StorageUsage.objects.get(item=self.reference)
            return {
                "size": usage.size,
                "version": usage.version,
                "mimetype": "application/pdf",
                "revision": self.reference.docs_binding.revision,
            }
        if self.kind != "file":
            raise StorageWriteConflict("Select a file to copy.")
        if self.backend.family == "s3":
            storage = storage_for_item(self.reference)
            head = object_head(storage.connection.meta.client, storage.bucket_name, self.path)
            if not head:
                raise StorageWriteConflict("The source is no longer available.")
            return {
                "size": int(head["ContentLength"]),
                "version": object_version(head),
                "etag": head["ETag"],
                "version_id": head.get("VersionId"),
                "mimetype": head.get("ContentType", "application/octet-stream"),
            }
        entry = virtual.stat(mount=self.mount, normalized_path=self.path)
        if entry.entry_type != "file" or not entry.object_identity:
            raise StorageWriteConflict("This source cannot be copied with a stable identity.")
        return {
            "size": int(entry.size or 0),
            "version": compute_mount_entry_version(entry),
            "identity": entry.object_identity,
            "mimetype": mimetypes.guess_type(self.name)[0] or "application/octet-stream",
        }

    @contextmanager
    def open(self, observation):
        """Keep native streams open only for the bounded transfer loop."""
        if self.kind == "docs":
            raise StorageWriteConflict("Native documents require an explicit export.")
        if self.backend.family == "s3":
            storage = storage_for_item(self.reference)
            version = observation.get("version_id")
            with closing(
                storage.connection.meta.client.get_object(
                    Bucket=storage.bucket_name,
                    Key=self.path,
                    IfMatch=observation["etag"],
                    **({"VersionId": version} if version not in {None, "", "null"} else {}),
                )["Body"]
            ) as stream:
                yield stream
        else:
            with virtual.open_read(mount=self.mount, normalized_path=self.path) as stream:
                yield stream


def item_location(item, actor, *, destination=False):
    """Apply Item access and readiness to both paged enumeration and single lookups."""
    if not actor.is_authenticated or not actor.is_active:
        raise NotFound()
    if item.type == "docs":
        from core.services.docs_resources import placement  # noqa: PLC0415

        if not item.get_abilities(actor).get("children_create" if destination else "retrieve"):
            raise NotFound()
        _, space = placement(item)
        if space is None:
            raise StorageWriteConflict("Choose a Drive location for this document first.")
        return TransferLocation(item, space, str(item.path))
    ability = "children_create" if destination else "retrieve"
    if not item.storage_space_id or not item.get_abilities(actor).get(ability):
        raise NotFound()
    if (
        item.deleted_at
        or item.ancestors_deleted_at
        or item.hard_deleted_at
        or (item.type == "file" and item.effective_upload_state() != "ready")
    ):
        raise NotFound()
    return TransferLocation(
        item, item.storage_space, str(item.path) if item.type == "folder" else item.file_key
    )


def resolve_location(
    reference_id, actor, *, space_id=None, destination=False, allow_document=False
):
    """Apply source read or destination write permission before exposing a location."""
    if not actor.is_authenticated or not actor.is_active:
        raise NotFound()
    item = (
        Item.objects.select_related("storage_backend", "storage_space__backend", "creator")
        .filter(pk=reference_id, hard_deleted_at__isnull=True)
        .first()
    )
    if item:
        location = item_location(item, actor, destination=destination)
    else:
        resource, space = resolve_resource_space(reference_id, actor, space_id)
        resource, path = resolve_mounted(reference_id, space, actor, write=destination)
        location = TransferLocation(resource, space, path, resolve_space_mount(space.pk, actor))
    if (
        destination
        and location.kind != "folder"
        and not (allow_document and location.kind == "docs")
    ):
        raise StorageWriteConflict("Choose a destination folder.")
    return location


@contextmanager
def verified_transfer_destination(job, source_backend):
    """Follow the stable reference after later moves, then verify bytes before collection."""
    job.actor.refresh_from_db()
    destination = resolve_location(job.source_path, job.actor)
    expected = job.operation.publication.get("sha256")
    if destination.kind != "file" or not expected:
        raise StorageWriteConflict("Source retained: destination verification is unavailable.")
    with ExitStack() as guards:
        guards.enter_context(advisory_guard(f"storage-editor:{destination.reference.pk}"))
        for backend in sorted(
            {source_backend, destination.backend}, key=lambda row: str(row.namespace)
        ):
            guards.enter_context(namespace_guard(backend, exclusive=True))
        if destination.backend.family == "s3":
            if LockService(destination.reference).is_locked():
                raise StorageWriteConflict("Source retained until the editing session closes.")
            storage = storage_for_item(destination.reference)
            client, bucket = storage.connection.meta.client, storage.bucket_name
            head = object_head(client, bucket, destination.path)
            if not head:
                raise StorageWriteConflict("Source retained: the destination is unavailable.")
            publication = job.operation.publication
            source_key = publication.get("original_key") or job.payload.get("source", {}).get(
                "path"
            )
            source_version = publication.get("source_version") or job.payload.get(
                "observation", {}
            ).get("version_id")
            if (
                source_backend.family == "s3"
                and source_backend.namespace == destination.backend.namespace
                and source_key == destination.path
                and source_version == head.get("VersionId")
            ):
                raise StorageWriteConflict("Source retained: this version is the current file.")
            verify_s3_digest(client, bucket, destination.path, head, expected)
        else:
            # Pin the current parent; direct NAS replacement must not change the verified entry.
            target = guards.enter_context(
                # pylint: disable-next=protected-access
                virtual._target(destination.mount, destination.path)  # noqa: SLF001
            )
            _, _, provider, mount, path = target
            guard_mount_editors(destination.backend, path)
            entry = provider.stat(mount=mount, normalized_path=path)
            if entry.object_identity != destination.reference.provider_identity:
                raise StorageWriteConflict("Source retained: destination identity changed.")
            verify_mount_digest(provider, mount, path, entry, expected)
        job.actor.refresh_from_db()
        latest = resolve_location(job.source_path, job.actor)
        if latest.descriptor() != destination.descriptor():
            raise StorageWriteConflict("Source retained: destination access or location changed.")
        yield destination
