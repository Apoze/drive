"""Archive extraction API views."""

from __future__ import annotations

import uuid

from django.shortcuts import get_object_or_404

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core import models
from core.api.serializers_archive_extraction import (
    ArchiveExtractionStatusSerializer,
    StartArchiveExtractionSerializer,
)
from core.archive.extract import (
    get_archive_extraction_job_status,
    is_supported_archive_for_server_extraction,
    set_archive_extraction_job_status,
    start_archive_extraction_job,
)
from core.entitlements import get_entitlements_backend
from core.tasks.archive import extract_archive_to_drive_task


class ArchiveExtractionStartView(APIView):
    """Start a server-side extraction job for an archive item."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):  # noqa: PLR0911  # pylint: disable=too-many-return-statements
        """Validate request and enqueue a Celery extraction task."""

        serializer = StartArchiveExtractionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        archive_item_id = str(serializer.validated_data["item_id"])
        destination_folder_id = str(serializer.validated_data["destination_folder_id"])
        mode = serializer.validated_data["mode"]
        collision_policy = serializer.validated_data.get("collision_policy") or "rename"
        create_root_folder = bool(serializer.validated_data.get("create_root_folder"))
        selection_paths = serializer.validated_data.get("selection_paths") or []

        entitlements_backend = get_entitlements_backend()
        can_upload = entitlements_backend.can_upload(user)
        if not can_upload.get("result"):
            return Response(
                {"detail": can_upload.get("message", "Upload not allowed.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        archive_item = get_object_or_404(models.Item, pk=archive_item_id)
        destination = get_object_or_404(models.Item, pk=destination_folder_id)

        if destination.type != models.ItemTypeChoices.FOLDER:
            return Response(
                {"detail": "Destination must be a folder."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if archive_item.type != models.ItemTypeChoices.FILE:
            return Response(
                {"detail": "Item must be a file."}, status=status.HTTP_400_BAD_REQUEST
            )

        if archive_item.effective_upload_state() != models.ItemUploadStateChoices.READY:
            return Response(
                {"detail": "Item is not ready."}, status=status.HTTP_400_BAD_REQUEST
            )

        if archive_item.upload_state == models.ItemUploadStateChoices.SUSPICIOUS:
            return Response(
                {"detail": "Suspicious items cannot be extracted."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not is_supported_archive_for_server_extraction(archive_item):
            return Response(
                {"detail": "Unsupported archive format for server extraction."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not archive_item.get_abilities(user).get("retrieve", False):
            return Response(status=status.HTTP_403_FORBIDDEN)
        if not destination.get_abilities(user).get("children_create", False):
            return Response(status=status.HTTP_403_FORBIDDEN)

        job_id = str(uuid.uuid4())
        start_archive_extraction_job(
            job_id=job_id,
            archive_item_id=archive_item_id,
            destination_folder_id=destination_folder_id,
            user_id=str(user.id),
            mode=mode,
            selection_paths=selection_paths,
            collision_policy=collision_policy,
            create_root_folder=create_root_folder,
        )

        try:
            extract_archive_to_drive_task.apply_async(
                kwargs={
                    "job_id": job_id,
                    "archive_item_id": archive_item_id,
                    "destination_folder_id": destination_folder_id,
                    "user_id": str(user.id),
                    "mode": mode,
                    "selection_paths": selection_paths,
                    "collision_policy": collision_policy,
                    "create_root_folder": create_root_folder,
                },
                task_id=job_id,
            )
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            # Celery eager mode can raise immediately; keep a best-effort status for the UI.
            set_archive_extraction_job_status(
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


class ArchiveExtractionStatusView(APIView):
    """Poll status/progress for an extraction job."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id: uuid.UUID):
        """Return current job status for the authenticated owner."""

        payload = get_archive_extraction_job_status(str(job_id))
        owner_id = payload.get("user_id")
        if owner_id and str(request.user.id) != str(owner_id):
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ArchiveExtractionStatusSerializer(data=payload)
        serializer.is_valid(raise_exception=False)
        return Response(serializer.data, status=status.HTTP_200_OK)
