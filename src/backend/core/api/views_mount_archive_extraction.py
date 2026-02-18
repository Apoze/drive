"""Mount archive extraction status API views."""

from __future__ import annotations

import uuid

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.serializers_archive_extraction import ArchiveExtractionStatusSerializer
from core.archive.extract_mount import get_mount_archive_extraction_job_status


class MountArchiveExtractionStatusView(APIView):
    """Poll status/progress for a mount extraction job."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id: uuid.UUID):
        payload = get_mount_archive_extraction_job_status(str(job_id))
        owner_id = payload.get("user_id")
        if owner_id and str(request.user.id) != str(owner_id):
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ArchiveExtractionStatusSerializer(data=payload)
        serializer.is_valid(raise_exception=False)
        return Response(serializer.data, status=status.HTTP_200_OK)

