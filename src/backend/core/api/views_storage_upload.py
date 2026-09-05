"""Single-use upload capabilities, with streamed bodies and server-side quotas."""

import uuid

from django.conf import settings
from django.core import signing
from django.core.exceptions import RequestDataTooBig
from django.core.files.storage import default_storage
from django.urls import reverse

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Item, ItemUploadStateChoices, StorageReservation
from core.services.s3_streaming import stream_to_s3_object
from core.services.storage_quota import StorageWriteConflict


def upload_url(item):
    """Keep the capability in the URL fragment so access logs never receive it."""
    if item.upload_state != ItemUploadStateChoices.PENDING or item.creator_id is None:
        return None
    token = signing.dumps(
        {
            "item": str(item.pk),
            "actor": str(item.creator_id),
            "session": item.upload_started_at.isoformat() if item.upload_started_at else None,
            "operation": str(uuid.uuid4()),
        },
        salt="drive.storage-upload",
    )
    path = reverse("storage_upload", kwargs={"item_id": item.pk})
    return f"{str(settings.DRIVE_PUBLIC_URL or '').rstrip('/')}{path}#{token}"


class StorageUploadView(APIView):
    """The capability authorizes only this pending item; no cookie authentication."""

    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = []

    def put(self, request, item_id):
        """Read the request body exactly once, without DRF multipart parsing."""
        if not settings.STORAGE_GOVERNANCE_ENABLED:
            raise PermissionDenied()
        try:
            token = signing.loads(
                request.headers.get("X-Drive-Upload-Token", ""),
                salt="drive.storage-upload",
                max_age=3600,
            )
            operation_id = uuid.UUID(token["operation"])
            item = Item.objects.select_related("creator").get(
                pk=item_id,
                creator_id=token["actor"],
                creator__is_active=True,
                upload_state=ItemUploadStateChoices.PENDING,
                deleted_at__isnull=True,
                ancestors_deleted_at__isnull=True,
                hard_deleted_at__isnull=True,
            )
            session = item.upload_started_at.isoformat() if item.upload_started_at else None
            if token["item"] != str(item_id) or token["session"] != session:
                raise PermissionDenied()
        except (signing.BadSignature, ValueError, KeyError, Item.DoesNotExist):
            raise PermissionDenied() from None
        # A previous successful upload cannot be replaced using another policy.
        if StorageReservation.objects.filter(
            resource_key=item.storageusage.key,
            state="committed",
        ).exists():
            raise StorageWriteConflict("Upload already completed.")
        try:
            stream_to_s3_object(
                s3_client=default_storage.connection.meta.client,
                bucket=default_storage.bucket_name,
                key=item.file_key,
                body_stream=request.stream,
                content_type=request.content_type,
                actor=item.creator,
                operation_id=operation_id,
                max_bytes=settings.DATA_UPLOAD_MAX_MEMORY_SIZE,
            )
        except RequestDataTooBig:
            return Response({"detail": "File exceeds the upload size limit."}, status=413)
        return Response(status=200)
