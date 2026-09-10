"""Private Messages file exchange; credentials identify the peer, not its user."""

import hashlib
import json
import secrets
from tempfile import TemporaryFile
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse

from rest_framework import exceptions, permissions, response, serializers, views
from suite_identity.document_transport import actor_context, resolve_actor
from suite_identity.http import read_credential

from core.services.item_exports import iter_document_pdf
from core.services.messages_files import MAX_ATTACHMENT_BYTES, import_attachment
from core.services.storage_transfer_location import resolve_location


class FileReadSerializer(serializers.Serializer):
    resource = serializers.UUIDField()
    space = serializers.UUIDField(required=False, allow_null=True)
    export = serializers.BooleanField(default=False)


class FileWriteSerializer(serializers.Serializer):
    destination = serializers.UUIDField()
    space = serializers.UUIDField(required=False, allow_null=True)
    request_key = serializers.UUIDField()
    name = serializers.CharField(max_length=255)
    mimetype = serializers.RegexField(r"\A[\w.+-]+/[\w.+-]+\Z")
    size = serializers.IntegerField(min_value=1, max_value=MAX_ATTACHMENT_BYTES)
    digest = serializers.RegexField(r"\A[0-9a-f]{64}\Z")


def receive(request, purpose):
    """Do not accept browser cookies, IdP tokens, URLs or storage paths here."""
    try:
        expected = read_credential(getattr(settings, f"MESSAGES_FILES_{purpose.upper()}_KEY_FILE"))
    except (OSError, ValueError, AttributeError):
        raise exceptions.NotFound() from None
    supplied = request.headers.get("X-Messages-Key", "")
    if (
        not supplied.isascii()
        or len(supplied) > 256
        or not secrets.compare_digest(expected, supplied)
    ):
        raise exceptions.AuthenticationFailed()
    raw = request.headers.get("X-Messages-Context", "")
    if len(raw) > 16384:
        raise exceptions.ValidationError("Transfer context exceeds its limit.")
    try:
        context = json.loads(raw)
        if not isinstance(context, dict) or not isinstance(context.get("payload"), dict):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise exceptions.ValidationError("Invalid transfer context.") from None
    request.user = resolve_actor(context.get("actor"))
    if not request.user.is_authenticated:
        raise exceptions.PermissionDenied()
    return context["payload"]


class MessagesFileView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    parser_classes = []

    def put(self, request):
        """Verify bytes before the existing S3/provider publication and quota admission."""
        serializer = FileWriteSerializer(data=receive(request, "mutation"))
        serializer.is_valid(raise_exception=True)
        result = import_attachment(request.user, serializer.validated_data, request.stream)
        return response.Response(result, status=201 if result["state"] == "done" else 202)

    def post(self, request):
        """Capture one stable, bounded copy, with an explicit native Docs export."""
        serializer = FileReadSerializer(data=receive(request, "read"))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        source = resolve_location(data["resource"], request.user, space_id=data.get("space"))
        if source.kind not in {"file", "docs"}:
            raise exceptions.ValidationError("Choose a file or a native document.")
        is_document = source.kind == "docs"
        if is_document and (
            not data["export"] or not source.reference.get_abilities(request.user).get("export")
        ):
            raise exceptions.PermissionDenied("Choose an explicit authorized document export.")
        observation = source.observe()
        if not is_document and observation["size"] > MAX_ATTACHMENT_BYTES:
            raise exceptions.ValidationError("Attachment exceeds the mail size limit.")
        body = TemporaryFile()
        size, digest = 0, hashlib.sha256()

        def consume(chunks):
            nonlocal size
            for chunk in chunks:
                size += len(chunk)
                if size > MAX_ATTACHMENT_BYTES:
                    raise exceptions.ValidationError("Attachment exceeds the mail size limit.")
                body.write(chunk)
                digest.update(chunk)

        try:
            if is_document:
                consume(iter_document_pdf(source.reference, actor_context(request.user)))
            else:
                with source.open(observation) as stream:
                    consume(iter(lambda: stream.read(1024 * 1024), b""))
            fresh = resolve_location(data["resource"], request.user, space_id=data.get("space"))
            if fresh.descriptor() != source.descriptor() or fresh.observe() != observation:
                raise exceptions.ValidationError("The source changed; select its current version.")
            body.seek(0)
            result = FileResponse(
                body, content_type="application/pdf" if is_document else observation["mimetype"]
            )
            result["Content-Length"] = str(size)
            result["X-Content-SHA256"] = digest.hexdigest()
            result["X-Attachment-Name"] = quote(
                source.name + (".pdf" if is_document else ""), safe=""
            )
            result["Cache-Control"] = "no-store"
            return result
        except BaseException:
            body.close()
            raise
