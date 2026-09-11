"""Authenticated browser endpoints for copying decrypted Transfers files into Drive."""

from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework import exceptions, permissions, response, serializers, views

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


class ChunkInput(serializers.Serializer):
    offset = serializers.IntegerField(min_value=0, max_value=intake.MAX_BYTES)
    length = serializers.IntegerField(min_value=0, max_value=intake.CHUNK_BYTES)
    digest = serializers.RegexField(r"\A[0-9a-f]{64}\Z")


class SuiteFileIntakeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not settings.TRANSFERS_PUBLIC_URL or not settings.STORAGE_GOVERNANCE_ENABLED:
            raise exceptions.NotFound()

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
