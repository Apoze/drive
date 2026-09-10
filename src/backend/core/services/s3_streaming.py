"""Streaming-safe S3 helpers (avoid whole-object RAM reads)."""

from __future__ import annotations

from io import BytesIO
from logging import getLogger

from django.conf import settings
from django.core.exceptions import RequestDataTooBig

from core.services.storage_s3_write import StorageS3Write
from core.utils.no_leak import safe_str_hash

logger = getLogger(__name__)


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def stream_to_s3_object(  # noqa: PLR0913  # pylint: disable=too-many-arguments,too-many-locals
    *,
    s3_client,
    bucket: str,
    key: str,
    body_stream,
    content_type: str,
    metadata: dict | None = None,
    content_disposition: str | None = None,
    acl: str | None = None,
    chunk_size: int = 8 * 1024 * 1024,
    actor=None,
    operation_id=None,
    max_bytes=None,
    expected_bytes=None,
    item_update=None,
    write_context=None,
) -> tuple[str | None, int]:
    """
    Stream an unknown-size body into S3 using multipart upload.

    This avoids requiring `tell()`/`seek()` on the input stream (common for request
    bodies and StreamingBody instances).
    """

    governed = write_context or (
        StorageS3Write(
            s3_client, bucket, key, actor=actor, operation_id=operation_id, item_update=item_update
        )
        if settings.STORAGE_GOVERNANCE_ENABLED
        else None
    )
    if governed:
        metadata = {**(metadata or {}), **governed.metadata}
    create_kwargs = {
        "Bucket": bucket,
        "Key": key,
        "ContentType": str(content_type or "application/octet-stream"),
        **({"Metadata": metadata} if isinstance(metadata, dict) else {}),
        **({"ContentDisposition": content_disposition} if content_disposition else {}),
        **({"ACL": acl} if acl else {}),
    }
    upload_id = None
    try:
        parts, size = [], 0
        if body_stream is not None:
            upload_id = s3_client.create_multipart_upload(**create_kwargs).get("UploadId")
            if not upload_id:
                raise RuntimeError("missing_upload_id")
            if governed:
                governed.started(upload_id)
            parts, size = _upload_parts(
                s3_client,
                body_stream,
                governed=governed,
                chunk_size=chunk_size,
                max_bytes=max_bytes,
                target={"Bucket": bucket, "Key": key, "UploadId": upload_id},
            )
            if not parts:
                s3_client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
                upload_id = None
        if expected_bytes is not None and size != expected_bytes:
            raise ValueError("Source length changed before publication.")
        response = _publish(
            s3_client, create_kwargs, governed=governed, size=size, upload_id=upload_id, parts=parts
        )
        version = response.get("VersionId")
        if governed:
            version = governed.completed(size, version)
        elif not version and upload_id:
            version = s3_client.head_object(Bucket=bucket, Key=key).get("VersionId")
        return version, size
    except Exception:
        if upload_id:
            _abort(s3_client, bucket=bucket, key=key, upload_id=upload_id)
        if governed:
            governed.failed()
        raise


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _publish(client, create_kwargs, *, governed, size, upload_id, parts):  # noqa: PLR0913
    if governed:
        if not upload_id:
            governed.started(None)
        governed.publish(size)
    conditions = getattr(governed, "publication_conditions", {})
    if upload_id:
        return client.complete_multipart_upload(
            Bucket=create_kwargs["Bucket"],
            Key=create_kwargs["Key"],
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
            **conditions,
        )
    return client.put_object(**create_kwargs, Body=b"", **conditions)


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def _upload_parts(client, stream, *, governed, chunk_size, max_bytes, target):  # noqa: PLR0913
    """Bound memory, fill short reads, and admit each part before transferring it."""
    parts, size = [], 0
    while True:
        chunk = bytearray()
        while len(chunk) < chunk_size:
            piece = stream.read(chunk_size - len(chunk))
            if not piece:
                break
            chunk.extend(piece)
        if not chunk:
            return parts, size
        size += len(chunk)
        if (max_bytes is not None and size > max_bytes) or len(parts) >= 10000:
            raise RequestDataTooBig()
        if governed:
            governed.accept(size)
        response = client.upload_part(**target, PartNumber=len(parts) + 1, Body=bytes(chunk))
        parts.append({"ETag": response.get("ETag"), "PartNumber": len(parts) + 1})


def _abort(client, *, bucket, key, upload_id):
    try:
        client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "s3_streaming: abort failed (bucket=%s key_hash=%s)", bucket, safe_str_hash(key)
        )


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def write_s3_bytes(*, s3_client, bucket, key, payload, content_type, actor=None):  # noqa: PLR0913
    """Keep legacy bounded writes cheap while routing governed writes through admission."""
    if settings.STORAGE_GOVERNANCE_ENABLED:
        version, _ = stream_to_s3_object(
            s3_client=s3_client,
            bucket=bucket,
            key=key,
            body_stream=BytesIO(payload),
            content_type=content_type,
            actor=actor,
        )
        return version
    return s3_client.put_object(Bucket=bucket, Key=key, Body=payload, ContentType=content_type).get(
        "VersionId"
    )
