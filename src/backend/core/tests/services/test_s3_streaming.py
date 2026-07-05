"""Tests for streaming-safe S3 upload helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

import io

import pytest

from core.services.s3_streaming import stream_to_s3_object


class FakeS3Client:
    """Minimal in-memory S3 client spy for multipart helper tests."""

    def __init__(
        self,
        *,
        complete_version_id: str | None = "complete-v1",
        head_version_id: str | None = "head-v1",
        put_version_id: str | None = "put-v1",
        fail_on: str | None = None,
    ):
        self.complete_version_id = complete_version_id
        self.head_version_id = head_version_id
        self.put_version_id = put_version_id
        self.fail_on = fail_on
        self.calls: list[tuple[str, dict]] = []

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))
        return {"VersionId": self.put_version_id}

    def create_multipart_upload(self, **kwargs):
        self.calls.append(("create_multipart_upload", kwargs))
        return {"UploadId": "upload-1"}

    def upload_part(self, **kwargs):
        self.calls.append(("upload_part", kwargs))
        if self.fail_on == "upload_part":
            raise RuntimeError("upload-failed")
        return {"ETag": f"etag-{kwargs['PartNumber']}"}

    def complete_multipart_upload(self, **kwargs):
        self.calls.append(("complete_multipart_upload", kwargs))
        if self.fail_on == "complete_multipart_upload":
            raise RuntimeError("complete-failed")
        return (
            {"VersionId": self.complete_version_id} if self.complete_version_id is not None else {}
        )

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        return {"VersionId": self.head_version_id}

    def abort_multipart_upload(self, **kwargs):
        self.calls.append(("abort_multipart_upload", kwargs))
        return {}


def test_stream_to_s3_object_uses_simple_put_when_body_stream_is_none():
    s3_client = FakeS3Client()

    version_id, bytes_written = stream_to_s3_object(
        s3_client=s3_client,
        bucket="drive-bucket",
        key="items/demo.txt",
        body_stream=None,
        content_type="text/plain",
    )

    assert (version_id, bytes_written) == ("put-v1", 0)
    assert [call[0] for call in s3_client.calls] == ["put_object"]
    assert s3_client.calls[0][1]["Body"] == b""


def test_stream_to_s3_object_falls_back_to_put_object_for_empty_stream():
    s3_client = FakeS3Client()

    version_id, bytes_written = stream_to_s3_object(
        s3_client=s3_client,
        bucket="drive-bucket",
        key="items/empty.txt",
        body_stream=io.BytesIO(b""),
        content_type="text/plain",
    )

    assert (version_id, bytes_written) == ("put-v1", 0)
    assert [call[0] for call in s3_client.calls] == [
        "create_multipart_upload",
        "put_object",
    ]
    assert s3_client.calls[1][1]["Body"] == b""


def test_stream_to_s3_object_uploads_parts_by_chunks_and_returns_complete_version():
    s3_client = FakeS3Client()

    version_id, bytes_written = stream_to_s3_object(
        s3_client=s3_client,
        bucket="drive-bucket",
        key="items/archive.bin",
        body_stream=io.BytesIO(b"abcdefghij"),
        content_type="application/octet-stream",
        chunk_size=4,
    )

    part_calls = [kwargs for name, kwargs in s3_client.calls if name == "upload_part"]
    complete_call = next(
        kwargs for name, kwargs in s3_client.calls if name == "complete_multipart_upload"
    )

    assert (version_id, bytes_written) == ("complete-v1", 10)
    assert [call["PartNumber"] for call in part_calls] == [1, 2, 3]
    assert [call["Body"] for call in part_calls] == [b"abcd", b"efgh", b"ij"]
    assert complete_call["MultipartUpload"]["Parts"] == [
        {"ETag": "etag-1", "PartNumber": 1},
        {"ETag": "etag-2", "PartNumber": 2},
        {"ETag": "etag-3", "PartNumber": 3},
    ]


def test_stream_to_s3_object_uses_head_object_when_complete_response_has_no_version_id():
    s3_client = FakeS3Client(complete_version_id=None, head_version_id="head-v2")

    version_id, bytes_written = stream_to_s3_object(
        s3_client=s3_client,
        bucket="drive-bucket",
        key="items/archive.bin",
        body_stream=io.BytesIO(b"abcdef"),
        content_type="application/octet-stream",
        chunk_size=3,
    )

    assert (version_id, bytes_written) == ("head-v2", 6)
    assert [call[0] for call in s3_client.calls][-1] == "head_object"


def test_stream_to_s3_object_aborts_multipart_upload_on_error():
    s3_client = FakeS3Client(fail_on="upload_part")

    with pytest.raises(RuntimeError, match="upload-failed"):
        stream_to_s3_object(
            s3_client=s3_client,
            bucket="drive-bucket",
            key="items/archive.bin",
            body_stream=io.BytesIO(b"abcdef"),
            content_type="application/octet-stream",
            chunk_size=3,
        )

    assert [call[0] for call in s3_client.calls] == [
        "create_multipart_upload",
        "upload_part",
        "abort_multipart_upload",
    ]
