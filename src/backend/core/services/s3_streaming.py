"""Streaming-safe S3 helpers (avoid whole-object RAM reads)."""

from __future__ import annotations

from logging import getLogger

from core.utils.no_leak import safe_str_hash

logger = getLogger(__name__)


def stream_to_s3_object(  # noqa: PLR0913
    *,
    s3_client,
    bucket: str,
    key: str,
    body_stream,
    content_type: str,
    metadata: dict | None = None,
    acl: str | None = None,
    chunk_size: int = 8 * 1024 * 1024,
) -> tuple[str | None, int]:
    """
    Stream an unknown-size body into S3 using multipart upload.

    This avoids requiring `tell()`/`seek()` on the input stream (common for request
    bodies and StreamingBody instances).
    """

    bytes_written = 0
    upload_id: str | None = None
    parts: list[dict] = []

    create_kwargs = {
        "Bucket": bucket,
        "Key": key,
        "ContentType": str(content_type or "application/octet-stream"),
        **({"Metadata": metadata} if isinstance(metadata, dict) else {}),
        **({"ACL": acl} if acl else {}),
    }

    try:
        create_resp = s3_client.create_multipart_upload(**create_kwargs)
        upload_id = create_resp.get("UploadId")
        if not upload_id:
            raise RuntimeError("missing_upload_id")

        part_number = 1
        while True:
            chunk = body_stream.read(chunk_size)
            if not chunk:
                break
            resp = s3_client.upload_part(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=chunk,
            )
            parts.append({"ETag": resp.get("ETag"), "PartNumber": part_number})
            bytes_written += len(chunk)
            part_number += 1

        if not parts:
            # Empty body: fall back to a simple put.
            put_kwargs = {
                "Bucket": bucket,
                "Key": key,
                "Body": b"",
                "ContentType": str(content_type or "application/octet-stream"),
                **({"Metadata": metadata} if isinstance(metadata, dict) else {}),
                **({"ACL": acl} if acl else {}),
            }
            put_resp = s3_client.put_object(**put_kwargs)
            return (put_resp.get("VersionId"), 0)

        complete_resp = s3_client.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
        version_id = complete_resp.get("VersionId")
        if version_id:
            return (version_id, bytes_written)

        head = s3_client.head_object(Bucket=bucket, Key=key)
        return (head.get("VersionId"), bytes_written)
    except Exception:  # noqa: BLE001
        if upload_id:
            try:
                s3_client.abort_multipart_upload(
                    Bucket=bucket, Key=key, UploadId=upload_id
                )
            except Exception:  # noqa: BLE001
                key_hash = safe_str_hash(str(key))
                logger.exception(
                    "s3_streaming: abort multipart failed (bucket=%s key_hash=%s)",
                    bucket,
                    key_hash,
                )
        raise
