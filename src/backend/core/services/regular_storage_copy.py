"""Regular S3-compatible object copy helpers."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Literal

from botocore.exceptions import ClientError

from core.services.s3_streaming import stream_to_s3_object

MetadataDirective = Literal["COPY", "REPLACE"]


@dataclass(frozen=True, slots=True)
class RegularStorageCopyResult:
    """Result of one regular-storage object copy operation."""

    version_id: str | None
    bytes_written: int | None
    used_streaming_fallback: bool
    copy_error_code: str | None = None


def get_s3_client_error_code(exc: BaseException) -> str:
    """Return a stable, non-sensitive error code for S3/botocore exceptions."""

    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code") or exc.__class__.__name__)
    return exc.__class__.__name__


def _source_descriptor(
    *,
    bucket: str,
    source_key: str,
    source_version_id: str | None,
) -> dict[str, str]:
    copy_source = {"Bucket": bucket, "Key": source_key}
    if source_version_id:
        copy_source["VersionId"] = source_version_id
    return copy_source


def _head_object(
    *,
    s3_client,
    bucket: str,
    source_key: str,
    source_version_id: str | None,
) -> dict:
    head_kwargs = {"Bucket": bucket, "Key": source_key}
    if source_version_id:
        head_kwargs["VersionId"] = source_version_id
    return s3_client.head_object(**head_kwargs)


def _get_object_body(
    *,
    s3_client,
    bucket: str,
    source_key: str,
    source_version_id: str | None,
):
    get_kwargs = {"Bucket": bucket, "Key": source_key}
    if source_version_id:
        get_kwargs["VersionId"] = source_version_id
    return s3_client.get_object(**get_kwargs).get("Body")


def _delete_source_object(
    *,
    s3_client,
    bucket: str,
    source_key: str,
    source_version_id: str | None,
) -> None:
    delete_kwargs = {"Bucket": bucket, "Key": source_key}
    if source_version_id:
        delete_kwargs["VersionId"] = source_version_id
    s3_client.delete_object(**delete_kwargs)


def copy_regular_storage_object(  # noqa: PLR0913
    *,
    s3_client,
    bucket: str,
    source_key: str,
    destination_key: str,
    metadata_directive: MetadataDirective = "COPY",
    source_head: dict | None = None,
    source_version_id: str | None = None,
    content_type: str | None = None,
    metadata: dict | None = None,
    content_disposition: str | None = None,
    acl: str | None = "private",
    delete_source: bool = False,
) -> RegularStorageCopyResult:
    """
    Copy one regular Drive S3 object, falling back to streaming GET->PUT.

    Callers own product policy, item state transitions, permissions, retry
    decisions, and error-to-response mapping. This helper owns only the reusable
    S3-compatible copy mechanics.
    """

    if metadata_directive not in {"COPY", "REPLACE"}:
        raise ValueError("metadata_directive must be COPY or REPLACE")

    effective_source_head = source_head
    if effective_source_head is not None and source_version_id is None:
        source_version_id = effective_source_head.get("VersionId")

    copy_kwargs = {
        "Bucket": bucket,
        "CopySource": _source_descriptor(
            bucket=bucket,
            source_key=source_key,
            source_version_id=source_version_id,
        ),
        "Key": destination_key,
        "MetadataDirective": metadata_directive,
    }
    if metadata_directive == "REPLACE":
        if effective_source_head is None:
            effective_source_head = _head_object(
                s3_client=s3_client,
                bucket=bucket,
                source_key=source_key,
                source_version_id=source_version_id,
            )
        replacement_content_type = content_type or effective_source_head.get("ContentType")
        if replacement_content_type:
            copy_kwargs["ContentType"] = replacement_content_type
        copy_kwargs["Metadata"] = (
            metadata if isinstance(metadata, dict) else effective_source_head.get("Metadata", {})
        )
        replacement_content_disposition = content_disposition or effective_source_head.get(
            "ContentDisposition"
        )
        if replacement_content_disposition:
            copy_kwargs["ContentDisposition"] = replacement_content_disposition

    try:
        copy_response = s3_client.copy_object(**copy_kwargs)
    except ClientError as copy_error:
        if effective_source_head is None:
            effective_source_head = _head_object(
                s3_client=s3_client,
                bucket=bucket,
                source_key=source_key,
                source_version_id=source_version_id,
            )

        fallback_content_type = (
            content_type
            if metadata_directive == "REPLACE" and content_type
            else effective_source_head.get("ContentType")
        )
        fallback_metadata = (
            metadata
            if metadata_directive == "REPLACE" and isinstance(metadata, dict)
            else effective_source_head.get("Metadata", {})
        )
        fallback_content_disposition = (
            content_disposition
            if metadata_directive == "REPLACE" and content_disposition
            else effective_source_head.get("ContentDisposition")
        )

        body = _get_object_body(
            s3_client=s3_client,
            bucket=bucket,
            source_key=source_key,
            source_version_id=source_version_id,
        )
        try:
            version_id, bytes_written = stream_to_s3_object(
                s3_client=s3_client,
                bucket=bucket,
                key=destination_key,
                body_stream=body,
                content_type=str(fallback_content_type or "application/octet-stream"),
                metadata=fallback_metadata,
                content_disposition=fallback_content_disposition,
                acl=acl,
            )
        finally:
            with contextlib.suppress(Exception):
                body.close()

        if delete_source:
            _delete_source_object(
                s3_client=s3_client,
                bucket=bucket,
                source_key=source_key,
                source_version_id=source_version_id,
            )
        return RegularStorageCopyResult(
            version_id=version_id,
            bytes_written=bytes_written,
            used_streaming_fallback=True,
            copy_error_code=get_s3_client_error_code(copy_error),
        )

    if delete_source:
        _delete_source_object(
            s3_client=s3_client,
            bucket=bucket,
            source_key=source_key,
            source_version_id=source_version_id,
        )
    return RegularStorageCopyResult(
        version_id=copy_response.get("VersionId"),
        bytes_written=None,
        used_streaming_fallback=False,
    )
