"""Authorized transfer requests and durable progress, without physical storage details."""

from django.conf import settings
from django.db.models import Count, Q

from rest_framework import decorators, exceptions, permissions, response, serializers, viewsets
from suite_identity.document_transport import actor_context

from core.api.storage_resources import StoragePagination
from core.models import StorageMoveJob
from core.services.storage_copy_job import accept_verified_copy
from core.services.storage_folder_copy import retain_interrupted_staging
from core.services.storage_move_job import enqueue_transfer
from core.services.storage_namespace import advisory_guard
from core.services.storage_quota import StorageWriteConflict
from core.services.storage_transfer_impact import transfer_impact
from core.services.storage_transfer_location import resolve_location


# Input validation only; persistence belongs to the journal service.
# pylint: disable-next=abstract-method
class TransferSourceSerializer(serializers.Serializer):
    """A selected resource and its optional authorized view."""

    source = serializers.UUIDField()
    source_space = serializers.UUIDField(required=False)


# Input validation only; the journal service persists transfers.
# pylint: disable-next=abstract-method
class TransferRequestSerializer(TransferSourceSerializer):
    """Destinations are logical folder references, never native paths or buckets."""

    destination_space = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False, max_length=255)
    destination = serializers.UUIDField()
    mode = serializers.ChoiceField(choices=["move", "copy"], default="move")
    request_key = serializers.UUIDField(required=False)


# Read-only estimation deliberately has no serializer persistence methods.
# pylint: disable-next=abstract-method
class TransferImpactSerializer(serializers.Serializer):
    """Bound a metadata-only preview before the user queues any work."""

    sources = TransferSourceSerializer(many=True, allow_empty=False, max_length=100)
    destination = serializers.UUIDField()
    destination_space = serializers.UUIDField(required=False)
    mode = serializers.ChoiceField(choices=["move", "copy", "archive", "extract"])
    name = serializers.CharField(required=False, max_length=255)
    selection_paths = serializers.ListField(
        child=serializers.CharField(max_length=512),
        required=False,
        allow_empty=False,
        max_length=1000,
    )


# DRF calls detail actions with pk even though get_object handles its lookup.
# pylint: disable=unused-argument
class StorageTransferViewSet(viewsets.GenericViewSet):
    """Users can inspect and retry only their own authorized transfer requests."""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StoragePagination
    serializer_class = TransferRequestSerializer

    def get_queryset(self):
        """Filter ownership before pagination or identifier lookup."""
        return (
            StorageMoveJob.objects.filter(actor=self.request.user)
            .select_related("operation")
            .annotate(
                entries_total=Count("copy_entries"),
                entries_done=Count("copy_entries", filter=Q(copy_entries__done=True)),
            )
            .order_by("-created_at")
        )

    @staticmethod
    def _serialize(job):
        operation = job.operation if job.operation_id else None
        entries_total = getattr(job, "entries_total", None)
        has_entries = (
            bool(entries_total) if entries_total is not None else job.copy_entries.exists()
        )
        return {
            "id": str(job.pk),
            "mode": "copy"
            if job.kind in {"s3_copy", "file_copy", "folder_copy", "docs_copy"}
            else "move",
            "title": job.payload.get("title", ""),
            "destination": job.payload.get("destination_title", ""),
            "state": job.state,
            "reason": job.reason,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "phase": operation.state if operation else "queued",
            "bytes": operation.publication.get("size", operation.previous_size)
            if operation
            else None,
            "source_retained": job.payload.get("source_retained", False),
            "progress": {
                "total": getattr(job, "entries_total", 0),
                "done": getattr(job, "entries_done", 0),
            }
            if job.kind in {"folder_copy", "folder_move", "docs_copy"}
            or job.payload.get("archive_sources")
            else None,
            "can_retry": not job.payload.get("extraction_parent")
            and job.state == "failed"
            and job.kind
            in {
                "s3_transfer",
                "mount_s3_transfer",
                "s3_mount_transfer",
                "mount_mount_transfer",
                "s3_copy",
                "file_copy",
                "folder_copy",
                "folder_move",
                "item_move",
                "item_tree_move",
                "native_resource_move",
                "docs_copy",
                "docs_move",
            },
            "can_cancel": job.state == "queued"
            and not job.operation_id
            and not has_entries
            and not job.payload.get("indexed"),
            "can_recover": job.state == "conflict",
            "can_accept": job.kind == "file_copy"
            and job.state == "conflict"
            and operation is not None
            and operation.state == "publishing"
            and bool(operation.publication.get("sha256")),
        }

    def create(self, request):
        """Apply the same access checks again inside the worker before publication."""
        if not settings.STORAGE_UNIFIED_ENABLED:
            raise exceptions.NotFound()
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        job = enqueue_transfer(
            actor=request.user,
            source=resolve_location(
                data.validated_data["source"],
                request.user,
                space_id=data.validated_data.get("source_space"),
            ),
            destination=resolve_location(
                data.validated_data["destination"],
                request.user,
                space_id=data.validated_data.get("destination_space"),
                destination=True,
            ),
            mode=data.validated_data["mode"],
            name=data.validated_data.get("name"),
            request_key=data.validated_data.get("request_key"),
        )
        return response.Response(self._serialize(job), status=202)

    @decorators.action(detail=False, methods=["post"])
    def impact(self, request):
        """Estimate only permitted data; no reservation, job or network scan is created."""
        if not settings.STORAGE_UNIFIED_ENABLED:
            raise exceptions.NotFound()
        serializer = TransferImpactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        destination = resolve_location(
            data["destination"],
            request.user,
            space_id=data.get("destination_space"),
            destination=True,
        )
        sources = [
            resolve_location(row["source"], request.user, space_id=row.get("source_space"))
            for row in data["sources"]
        ]
        return response.Response(
            transfer_impact(
                sources,
                destination,
                request.user,
                "copy" if data["mode"] in {"archive", "extract"} else data["mode"],
            )
        )

    @decorators.action(detail=False, methods=["post"])
    def extract(self, request):
        """Extract one archive into a new folder in an authorized space."""
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_extract import enqueue_extraction  # noqa: PLC0415

        if not settings.STORAGE_UNIFIED_ENABLED:
            raise exceptions.NotFound()
        serializer = TransferImpactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["mode"] != "extract" or len(data["sources"]) != 1:
            raise exceptions.ValidationError("Select one archive to extract.")
        selected = data["sources"][0]
        job = enqueue_extraction(
            actor=request.user,
            source=resolve_location(
                selected["source"], request.user, space_id=selected.get("source_space")
            ),
            destination=resolve_location(
                data["destination"],
                request.user,
                space_id=data.get("destination_space"),
                destination=True,
            ),
            name=data.get("name", "extracted"),
            selection_paths=data.get("selection_paths"),
        )
        return response.Response(self._serialize(job), status=202)

    @decorators.action(detail=False, methods=["post"])
    def archive(self, request):
        """Create one ZIP from an authorized selection on any configured family."""
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_archive import enqueue_archive  # noqa: PLC0415

        if not settings.STORAGE_UNIFIED_ENABLED:
            raise exceptions.NotFound()
        serializer = TransferImpactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["mode"] != "archive":
            raise exceptions.ValidationError("Select archive mode for this operation.")
        sources = [
            resolve_location(row["source"], request.user, space_id=row.get("source_space"))
            for row in data["sources"]
        ]
        destination = resolve_location(
            data["destination"],
            request.user,
            space_id=data.get("destination_space"),
            destination=True,
        )
        job = enqueue_archive(
            actor=request.user,
            sources=sources,
            destination=destination,
            name=data.get("name", "archive.zip"),
        )
        return response.Response(self._serialize(job), status=202)

    def list(self, request):
        """Bound history pagination and expose no connection credentials or native keys."""
        page = self.paginate_queryset(self.get_queryset().exclude(payload__has_key="parent_job"))
        return self.get_paginated_response([self._serialize(job) for job in page])

    def retrieve(self, request, pk=None):
        """Progress is durable even when the broker or a worker is unavailable."""
        return response.Response(self._serialize(self.get_object()))

    @decorators.action(detail=True, methods=["get"])
    def entries(self, request, pk=None):
        """Expose a bounded manifest and child recovery actions to the job's owner only."""
        job = self.get_object()
        page = self.paginate_queryset(
            job.copy_entries.select_related("child_job__operation").order_by("created_at", "pk")
        )
        return self.get_paginated_response(
            [
                {
                    "id": str(entry.pk),
                    "title": entry.name,
                    "kind": entry.kind,
                    "done": entry.done,
                    "retained_staging": len(entry.publication.get("retained_staging", [])),
                    "transfer": self._serialize(entry.child_job) if entry.child_job_id else None,
                }
                for entry in page
            ]
        )

    @decorators.action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel queued intent; a publishing operation must be recovered instead."""
        job = self.get_object()
        with advisory_guard(f"storage-move:{job.pk}"):
            job.refresh_from_db()
            if (
                job.state != "queued"
                or job.operation_id
                or job.copy_entries.exists()
                or job.payload.get("indexed")
            ):
                raise StorageWriteConflict("This transfer has started and must be recovered.")
            job.state, job.reason = "failed", "Cancelled before any bytes were written."
            job.save(update_fields=["state", "reason", "updated_at"])
        return response.Response(self._serialize(job))

    @decorators.action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        """A failed request creates a fresh journal and preserves the previous history."""
        job = self.get_object()
        if job.kind in {"docs_move", "docs_copy"}:
            from core.services.docs_jobs import enqueue  # noqa: PLC0415

            target = job.payload["destination"]
            job = enqueue(
                request.user,
                resolve_location(job.source_path, request.user),
                resolve_location(
                    target["id"],
                    request.user,
                    space_id=target["space"],
                    destination=True,
                    allow_document=True,
                ),
                mode=job.payload["mode"],
                request_key=job.pk,
                with_accesses=job.payload["with_accesses"],
            )
            return response.Response(self._serialize(job), status=202)
        if job.state != "failed" or (job.operation_id and job.operation.state != "cancelled"):
            raise StorageWriteConflict("Recover the existing publication before retrying.")
        if job.kind not in {
            "s3_transfer",
            "mount_s3_transfer",
            "s3_mount_transfer",
            "mount_mount_transfer",
            "s3_copy",
            "file_copy",
            "folder_copy",
            "folder_move",
            "item_move",
            "item_tree_move",
            "native_resource_move",
        }:
            raise StorageWriteConflict("Retry this legacy move from its original folder.")
        if job.payload.get("extraction_parent"):
            raise StorageWriteConflict("Recover the parent extraction to retry this file.")
        if job.payload.get("extract"):
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_extract import enqueue_extraction  # noqa: PLC0415

            next_job = enqueue_extraction(
                actor=request.user,
                source=resolve_location(job.source_path, request.user, space_id=job.space_id),
                destination=resolve_location(
                    job.destination_path,
                    request.user,
                    space_id=job.payload["destination"]["space"],
                    destination=True,
                ),
                name=job.payload["title"],
                selection_paths=job.payload.get("selection_paths"),
            )
            return response.Response(self._serialize(next_job), status=202)
        if job.payload.get("archive_sources"):
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_archive import enqueue_archive  # noqa: PLC0415

            next_job = enqueue_archive(
                actor=request.user,
                sources=[
                    resolve_location(row["id"], request.user, space_id=row["space"])
                    for row in job.payload["archive_sources"]
                ],
                destination=resolve_location(
                    job.destination_path,
                    request.user,
                    space_id=job.payload["destination"]["space"],
                    destination=True,
                ),
                name=job.payload["name"],
            )
            return response.Response(self._serialize(next_job), status=202)
        if job.payload.get("conversion"):
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_copy_job import enqueue_copy  # noqa: PLC0415

            next_job = enqueue_copy(
                actor=request.user,
                source=resolve_location(job.source_path, request.user, space_id=job.space_id),
                destination=resolve_location(
                    job.destination_path,
                    request.user,
                    space_id=job.payload["destination"]["space"],
                    destination=True,
                ),
                name=job.payload["name"],
                conversion=job.payload["conversion"],
            )
            return response.Response(self._serialize(next_job), status=202)
        next_job = enqueue_transfer(
            actor=request.user,
            source=resolve_location(
                job.payload.get("source", {}).get("id", job.source_path),
                request.user,
                space_id=job.payload.get("source", {}).get("space", str(job.space_id)),
            ),
            destination=resolve_location(
                job.payload.get("destination", {}).get("id", job.destination_path),
                request.user,
                space_id=job.payload.get("destination", {}).get(
                    "space", job.payload.get("destination_space")
                ),
                destination=True,
            ),
            mode="copy" if job.kind in {"s3_copy", "file_copy", "folder_copy"} else "move",
            name=job.payload.get("name")
            or (job.payload.get("title") if job.kind in {"folder_copy", "folder_move"} else None),
        )
        return response.Response(self._serialize(next_job), status=202)

    @decorators.action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Publish the verified captured copy only after an explicit user request."""
        job = self.get_object()
        with advisory_guard(f"storage-move:{job.pk}"):
            job.refresh_from_db()
            accept_verified_copy(job)
        return response.Response(self._serialize(job))

    @decorators.action(detail=True, methods=["post"])
    def recover(self, request, pk=None):
        """Reobserve an unresolved publication without starting a second transfer."""
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_move_job import dispatch_move  # noqa: PLC0415

        job = self.get_object()
        if job.kind in {"docs_copy", "docs_move"}:
            return self.retry(request, pk=pk)
        with advisory_guard(f"storage-move:{job.pk}"):
            job.refresh_from_db()
            if job.state != "conflict":
                raise StorageWriteConflict("This transfer does not require manual recovery.")
            job.state = "running"
            if job.kind in {"folder_copy", "folder_move"}:
                retain_interrupted_staging(job)
                job.payload = {**job.payload, "retry_failed": True}
                if settings.DOCS_DRIVE_ENABLED:
                    job.payload["actor"] = actor_context(request.user)
                if job.kind == "folder_move" and not job.payload.get("finalizing"):
                    job.copy_entries.filter(kind="folder").update(done=False, enumerated=False)
            job.save(update_fields=["state", "payload", "updated_at"])
        dispatch_move(job.pk)
        return response.Response(self._serialize(job), status=202)
