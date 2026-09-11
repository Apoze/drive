"""Private bounded reads for Transfers, with a stable observed source version."""

import hashlib
import json
from tempfile import TemporaryFile

from django.core import signing
from django.http import FileResponse

from rest_framework import exceptions, permissions, response, serializers, views

from core.api.suite_files import FileReadSerializer, receive
from core.models import Item
from core.mounts.providers import virtual
from core.services.storage_transfer_location import resolve_location

CHUNK_BYTES = 25 * 1024**2
MAX_BYTES = 20 * 1024**3


def observed(source):
    observation = source.observe()
    digest = hashlib.sha256(
        json.dumps(
            {"location": source.descriptor(), "observation": observation},
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    return observation, digest


def readable(data, user):
    source = resolve_location(data["resource"], user, space_id=data.get("space"))
    if source.kind != "file":
        raise exceptions.ValidationError("Choose a file; native documents require a PDF export.")
    if isinstance(source.reference, Item) and not source.reference.get_abilities(user).get(
        "download"
    ):
        raise exceptions.PermissionDenied("This file cannot be exported.")
    return source


class ChunkInput(serializers.Serializer):
    snapshot = serializers.CharField(max_length=4096)
    offset = serializers.IntegerField(min_value=0, max_value=MAX_BYTES)
    length = serializers.IntegerField(min_value=0, max_value=CHUNK_BYTES)


class SuiteFileChunksView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    parser_classes = []

    def patch(self, request):
        serializer = FileReadSerializer(data=receive(request, "read", "TRANSFERS"))
        serializer.is_valid(raise_exception=True)
        source = readable(serializer.validated_data, request.user)
        observation, fingerprint = observed(source)
        size = observation["size"]
        if not 0 <= size <= MAX_BYTES:
            raise exceptions.ValidationError("The file exceeds the Transfers size limit.")
        if (
            source.mount
            and size > CHUNK_BYTES
            and not virtual.get_browser_stream_capabilities(
                mount=source.mount,
            ).supports_random_access
        ):
            raise exceptions.ValidationError("This storage cannot safely resume large reads.")
        token = signing.dumps(
            {
                "actor": str(request.user.pk),
                "resource": str(source.reference.pk),
                "space": str(source.space.pk),
                "fingerprint": fingerprint,
            },
            salt="suite.transfers.source",
        )
        result = response.Response(
            {
                "snapshot": token,
                "name": source.name,
                "size": size,
                "fingerprint": fingerprint,
                "mimetype": observation["mimetype"],
                "chunk_size": CHUNK_BYTES,
            }
        )
        result["Cache-Control"] = "no-store"
        return result

    def post(self, request):
        serializer = ChunkInput(data=receive(request, "read", "TRANSFERS"))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            snapshot = signing.loads(data["snapshot"], salt="suite.transfers.source", max_age=3600)
            if snapshot["actor"] != str(request.user.pk):
                raise signing.BadSignature()
        except (signing.BadSignature, KeyError, TypeError):
            raise exceptions.PermissionDenied("Select the source again.") from None
        source = readable(snapshot, request.user)
        observation, fingerprint = observed(source)
        if fingerprint != snapshot["fingerprint"]:
            raise exceptions.ValidationError("The source changed. Select its current version.")
        offset, length = data["offset"], data["length"]
        if offset + length > observation["size"] or (length == 0 and offset != 0):
            raise exceptions.ValidationError("Invalid source range.")
        body = TemporaryFile()
        try:
            remaining, digest = length, hashlib.sha256()
            with source.open(observation, offset=offset, length=length) as stream:
                while remaining:
                    chunk = stream.read(min(1024**2, remaining))
                    if not chunk or len(chunk) > remaining:
                        raise exceptions.ValidationError("The source was truncated.")
                    remaining -= len(chunk)
                    digest.update(chunk)
                    body.write(chunk)
            fresh = readable(snapshot, request.user)
            if observed(fresh)[1] != fingerprint:
                raise exceptions.ValidationError("The source changed during the read.")
            body.seek(0)
            result = FileResponse(body, content_type="application/octet-stream")
            result["Content-Length"] = str(length)
            result["X-Content-SHA256"] = digest.hexdigest()
            result["Cache-Control"] = "no-store"
            return result
        except BaseException:
            body.close()
            raise
