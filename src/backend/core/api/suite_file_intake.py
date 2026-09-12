"""Authenticated browser endpoints for copying decrypted Transfers files into Drive."""

import hashlib
import secrets
import time

from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework import exceptions, permissions, response, serializers, views
from suite_identity.access import principal_id
from suite_identity.document_transport import actor_context, resolve_actor

from core.models import StorageMoveJob
from core.services import suite_file_intake as intake
from core.services.storage_move_job import dispatch_move
from core.services.storage_namespace import advisory_guard


class IntakeInput(serializers.Serializer):
    destination = serializers.UUIDField()
    space = serializers.UUIDField()
    request_key = serializers.UUIDField()
    name = serializers.CharField(max_length=255)
    mimetype = serializers.RegexField(r"\A[\w.+-]+/[\w.+-]+\Z")
    size = serializers.IntegerField(min_value=0, max_value=intake.MAX_BYTES)
    mobile_challenge = serializers.RegexField(r"\A[0-9a-f]{64}\Z", required=False)


class ChunkInput(serializers.Serializer):
    offset = serializers.IntegerField(min_value=0, max_value=intake.MAX_BYTES)
    length = serializers.IntegerField(min_value=0, max_value=intake.CHUNK_BYTES)
    digest = serializers.RegexField(r"\A[0-9a-f]{64}\Z")


class SuiteFileIntakeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if (
            not (settings.TRANSFERS_PUBLIC_URL or settings.CHAT_PUBLIC_URL)
            or not settings.STORAGE_GOVERNANCE_ENABLED
        ):
            raise exceptions.NotFound()
        principal = request.headers.get("X-Suite-Principal")
        if principal is not None and principal != str(principal_id(request.user)):
            raise exceptions.PermissionDenied("Use the same suite account in Drive and Chat.")

    def job(self, request, job_id):
        return get_object_or_404(
            StorageMoveJob,
            pk=job_id,
            actor=request.user,
            payload__suite_intake__isnull=False,
        )

    def post(self, request):
        serializer = IntakeInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with advisory_guard(f"storage-move:{data['request_key']}"):
            job = intake.prepare(request.user, data)
            if data.get("mobile_challenge"):
                # Only a fresh browser session renews this operation's proof.
                job.payload["suite_intake"]["actor"] = actor_context(request.user)
                job.save(update_fields=["payload", "updated_at"])
            return response.Response(intake.result(job), status=201)

    def get(self, request, job_id):
        job = self.job(request, job_id)
        intake.authorize(job, request.user)
        return response.Response(intake.result(job))

    def put(self, request, job_id):
        serializer = ChunkInput(
            data={
                "offset": request.headers.get("X-Upload-Offset"),
                "length": request.headers.get("Content-Length"),
                "digest": request.headers.get("X-Content-SHA256"),
            }
        )
        serializer.is_valid(raise_exception=True)
        with advisory_guard(f"storage-move:{job_id}"):
            job = self.job(request, job_id)
            intake.append(job, request.user, serializer.validated_data, request.stream)
            return response.Response(intake.result(job))

    def patch(self, request, job_id):
        with advisory_guard(f"storage-move:{job_id}"):
            job = self.job(request, job_id)
            intake.finish(job, request.user)
            result = intake.result(job)
        dispatch_move(job.pk)
        return response.Response(result, status=200 if job.state == "done" else 202)

    def delete(self, request, job_id):
        with advisory_guard(f"storage-move:{job_id}"):
            job = self.job(request, job_id)
            if job.state != "done":
                intake.cancel(job)
        return response.Response(status=204)


class MobileFileIntakeView(SuiteFileIntakeView):
    """A private verifier admits only an already browser-approved copy job."""

    authentication_classes = []
    permission_classes = []
    http_method_names = ["get", "put", "patch", "delete", "options"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        job = get_object_or_404(StorageMoveJob, pk=kwargs["job_id"])
        grant = job.payload.get("suite_intake", {})
        verifier = request.headers.get("X-Intake-Verifier", "")
        if (
            len(verifier) != 64
            or any(character not in "0123456789abcdef" for character in verifier)
            or not secrets.compare_digest(
                hashlib.sha256(verifier.encode()).hexdigest(), grant.get("mobile_challenge", "")
            )
            or grant.get("expires", 0) <= time.time()
        ):
            raise exceptions.PermissionDenied("This copy authorization is invalid or expired.")
        request.user = resolve_actor(grant.get("actor"))
        intake.authorize(job, request.user)

    def finalize_response(self, request, result, *args, **kwargs):
        result = super().finalize_response(request, result, *args, **kwargs)
        result["Cache-Control"] = "private, no-store"
        return result
