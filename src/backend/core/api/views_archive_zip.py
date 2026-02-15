"""Archive zip creation API views."""

from __future__ import annotations

import uuid

from django.shortcuts import get_object_or_404

from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core import models
from core.api.serializers_archive_zip import (
    ArchiveZipStatusSerializer,
    StartArchiveZipSerializer,
)
from core.archive.zip_create import (
    get_archive_zip_job_status,
    set_archive_zip_job_status,
    start_archive_zip_job,
)
from core.entitlements import get_entitlements_backend
from core.tasks.archive import create_zip_from_items_task


class ArchiveZipStartView(APIView):
    """Start a server-side zip creation job."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Validate inputs and enqueue a Celery job to create a zip archive."""

        serializer = StartArchiveZipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        item_ids = [str(i) for i in serializer.validated_data["item_ids"]]
        destination_folder_id = str(serializer.validated_data["destination_folder_id"])
        archive_name = serializer.validated_data["archive_name"]

        entitlements_backend = get_entitlements_backend()
        can_upload = entitlements_backend.can_upload(user)
        if not can_upload.get("result"):
            raise PermissionDenied(can_upload.get("message", "Upload not allowed."))

        destination = get_object_or_404(models.Item, pk=destination_folder_id)
        if destination.type != models.ItemTypeChoices.FOLDER:
            raise ValidationError("Destination must be a folder.")
        if not destination.get_abilities(user).get("children_create", False):
            raise PermissionDenied()

        sources = list(
            models.Item.objects.filter(id__in=item_ids).filter(
                deleted_at__isnull=True,
                hard_deleted_at__isnull=True,
                ancestors_deleted_at__isnull=True,
            )
        )
        if len(sources) != len(set(item_ids)):
            raise NotFound()

        for item in sources:
            if not item.get_abilities(user).get("retrieve", False):
                raise PermissionDenied()
            if item.type == models.ItemTypeChoices.FILE:
                if item.effective_upload_state() != models.ItemUploadStateChoices.READY:
                    raise ValidationError("A selected file is not ready.")
                if item.upload_state == models.ItemUploadStateChoices.SUSPICIOUS:
                    raise PermissionDenied("Suspicious items cannot be compressed.")

        job_id = str(uuid.uuid4())
        start_archive_zip_job(
            job_id=job_id,
            source_item_ids=item_ids,
            destination_folder_id=destination_folder_id,
            user_id=str(user.id),
            archive_name=archive_name,
        )

        try:
            create_zip_from_items_task.apply_async(
                kwargs={
                    "job_id": job_id,
                    "source_item_ids": item_ids,
                    "destination_folder_id": destination_folder_id,
                    "user_id": str(user.id),
                    "archive_name": archive_name,
                },
                task_id=job_id,
            )
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            set_archive_zip_job_status(
                job_id,
                {
                    "state": "failed",
                    "progress": {
                        "files_done": 0,
                        "total": 0,
                        "bytes_done": 0,
                        "bytes_total": 0,
                    },
                    "errors": [{"detail": str(exc)}],
                    "user_id": str(user.id),
                },
            )

        return Response({"job_id": job_id}, status=status.HTTP_201_CREATED)


class ArchiveZipStatusView(APIView):
    """Poll status/progress for a zip creation job."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id: uuid.UUID):
        """Return the current job status for the authenticated owner."""

        payload = get_archive_zip_job_status(str(job_id))
        owner_id = payload.get("user_id")
        if owner_id and str(request.user.id) != str(owner_id):
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ArchiveZipStatusSerializer(data=payload)
        serializer.is_valid(raise_exception=False)
        return Response(serializer.data, status=status.HTTP_200_OK)
