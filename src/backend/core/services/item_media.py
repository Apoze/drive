"""Serve explicit S3 destinations through their native client with bounded reads."""

from django.http import FileResponse, HttpResponse
from django.utils.http import http_date, parse_http_date_safe

from botocore.exceptions import BotoCoreError, ClientError
from rest_framework.exceptions import APIException, NotFound, PermissionDenied

from core.models import Item, ItemTypeChoices, ItemUploadStateChoices
from core.services.storage_connections import storage_for_item
from core.services.storage_s3_write import object_head
from core.utils.share_links import current_item_share_token, validate_item_share_token


def check_share_access(item, user, token):
    """A public folder token authorizes only its still-public descendants."""
    if user.is_authenticated:
        return
    identity = validate_item_share_token(token or "")
    root = (
        Item.objects.filter(
            pk=identity, path__ancestors=item.path, hard_deleted_at__isnull=True
        ).first()
        if identity
        else None
    )
    if (
        not root
        or not current_item_share_token(root, token)
        or not root.get_abilities(user).get("media_auth")
    ):
        raise PermissionDenied()


def media_response(item, request, *, preview=False):
    """Authorization precedes HEAD, conditional evaluation and streaming GET."""
    if item.type != ItemTypeChoices.FILE or item.effective_upload_state() in {
        ItemUploadStateChoices.PENDING,
        ItemUploadStateChoices.EXPIRED,
    }:
        raise PermissionDenied()
    check_share_access(item, request.user, request.query_params.get("share_token"))
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.api.utils import is_previewable_item  # noqa: PLC0415

    if preview and not is_previewable_item(item):
        raise PermissionDenied()
    return stream_item_response(item, request, preview=preview)


def stream_item_response(item, request, *, preview=False):
    """Native transport after the caller has authorized its item or public resource link."""
    try:
        return _native_response(item, request, preview=preview)
    except (ClientError, BotoCoreError) as exc:
        error = APIException("The storage is temporarily unavailable.")
        error.status_code = 503
        if isinstance(exc, ClientError) and exc.response.get("Error", {}).get("Code") in {
            "PreconditionFailed",
            "412",
        }:
            error = APIException("The file changed while opening it. Please retry.")
            error.status_code = 409
        raise error from None


# Conditional and ranged responses share the same observed HEAD snapshot.
# pylint: disable-next=too-many-locals
def _native_response(item, request, *, preview):
    """Read a version or condition every unversioned read on the observed ETag."""
    storage = storage_for_item(item)
    client, bucket = storage.connection.meta.client, storage.bucket_name
    head = object_head(client, bucket, item.file_key)
    if not head:
        raise NotFound()
    size, etag = int(head["ContentLength"]), head.get("ETag", "")
    modified = head.get("LastModified")
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store, no-transform",
        "X-Content-Type-Options": "nosniff",
        "X-Robots-Tag": "noindex",
    }
    if etag:
        headers["ETag"] = etag
    if modified:
        headers["Last-Modified"] = http_date(modified.timestamp())
    tags = [
        tag.strip().removeprefix("W/")
        for tag in request.headers.get("If-None-Match", "").split(",")
    ]
    if etag and (etag in tags or "*" in tags):
        return HttpResponse(status=304, headers=headers)
    range_header = request.headers.get("Range", "")
    if_range = request.headers.get("If-Range")
    if if_range and if_range != etag:
        date = parse_http_date_safe(if_range)
        if not modified or date is None or int(modified.timestamp()) > date:
            range_header = ""
    # Reuse the range grammar already qualified for mounted browser streams.
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.api.viewsets import MountViewSet  # noqa: PLC0415

    try:
        # pylint: disable-next=protected-access
        part = MountViewSet._parse_single_bytes_range(  # noqa: SLF001
            header_value=range_header, size=size
        )
    except (ValueError, IndexError):
        return HttpResponse(status=416, headers={**headers, "Content-Range": f"bytes */{size}"})
    status, length = (206, part[1] - part[0] + 1) if part else (200, size)
    if part:
        headers["Content-Range"] = f"bytes {part[0]}-{part[1]}/{size}"
    headers["Content-Length"] = str(length)
    content_type = item.mimetype or "application/octet-stream"
    if request.method == "HEAD":
        return HttpResponse(status=status, headers=headers, content_type=content_type)
    body = client.get_object(
        Bucket=bucket,
        Key=item.file_key,
        **(
            {"VersionId": head["VersionId"]}
            if head.get("VersionId") not in {None, "", "null"}
            else {}
        ),
        **({"IfMatch": etag} if etag else {}),
        **({"Range": f"bytes={part[0]}-{part[1]}"} if part else {}),
    )["Body"]
    # FileResponse registers close() even when the client never consumes the iterator.
    result = FileResponse(
        body,
        status=status,
        headers=headers,
        content_type=content_type,
        as_attachment=not preview,
        filename=item.filename or item.title,
    )
    result.block_size = 64 * 1024
    return result
