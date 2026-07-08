"""Tests for regular S3-compatible copy helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

import io

from botocore.exceptions import ClientError

from core.services.regular_storage_copy import copy_regular_storage_object


class _CloseTrackingBody(io.BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.was_closed = False

    def close(self):
        self.was_closed = True
        super().close()


class _FakeS3Client:
    def __init__(self, *, fail_copy: bool = False):
        self.fail_copy = fail_copy
        self.calls: list[tuple[str, dict]] = []
        self.body = _CloseTrackingBody(b"abcdefghij")

    def copy_object(self, **kwargs):
        self.calls.append(("copy_object", kwargs))
        if self.fail_copy:
            raise ClientError(
                {"Error": {"Code": "NotImplemented", "Message": "copy unsupported"}},
                "CopyObject",
            )
        return {"VersionId": "copy-v1"}

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        return {
            "VersionId": "source-v1",
            "ContentType": "text/plain",
            "ContentDisposition": "inline",
            "Metadata": {"foo": "bar"},
        }

    def get_object(self, **kwargs):
        self.calls.append(("get_object", kwargs))
        return {"Body": self.body}

    def create_multipart_upload(self, **kwargs):
        self.calls.append(("create_multipart_upload", kwargs))
        return {"UploadId": "upload-v1"}

    def upload_part(self, **kwargs):
        self.calls.append(("upload_part", kwargs))
        return {"ETag": f"etag-{kwargs['PartNumber']}"}

    def complete_multipart_upload(self, **kwargs):
        self.calls.append(("complete_multipart_upload", kwargs))
        return {"VersionId": "fallback-v1"}

    def delete_object(self, **kwargs):
        self.calls.append(("delete_object", kwargs))
        return {}


def test_regular_storage_copy_uses_copy_object():
    s3_client = _FakeS3Client()

    result = copy_regular_storage_object(
        s3_client=s3_client,
        bucket="drive-bucket",
        source_key="item/source.txt",
        destination_key="item/destination.txt",
        metadata_directive="COPY",
    )

    assert result.version_id == "copy-v1"
    assert result.bytes_written is None
    assert result.used_streaming_fallback is False
    assert [call[0] for call in s3_client.calls] == ["copy_object"]
    assert s3_client.calls[0][1]["CopySource"] == {
        "Bucket": "drive-bucket",
        "Key": "item/source.txt",
    }


def test_regular_storage_copy_streams_fallback_and_closes_source_body():
    s3_client = _FakeS3Client(fail_copy=True)

    result = copy_regular_storage_object(
        s3_client=s3_client,
        bucket="drive-bucket",
        source_key="item/source.txt",
        destination_key="item/destination.txt",
        metadata_directive="COPY",
        source_version_id="source-v1",
    )

    assert result.version_id == "fallback-v1"
    assert result.bytes_written == 10
    assert result.used_streaming_fallback is True
    assert result.copy_error_code == "NotImplemented"
    assert s3_client.body.was_closed is True
    assert [call[0] for call in s3_client.calls] == [
        "copy_object",
        "head_object",
        "get_object",
        "create_multipart_upload",
        "upload_part",
        "complete_multipart_upload",
    ]
    create_upload_call = s3_client.calls[3][1]
    assert create_upload_call["ContentType"] == "text/plain"
    assert create_upload_call["ContentDisposition"] == "inline"
    assert create_upload_call["Metadata"] == {"foo": "bar"}
    assert s3_client.calls[0][1]["CopySource"]["VersionId"] == "source-v1"


def test_regular_storage_copy_replaces_metadata_and_deletes_source_version():
    s3_client = _FakeS3Client()

    result = copy_regular_storage_object(
        s3_client=s3_client,
        bucket="drive-bucket",
        source_key="item/source.txt",
        destination_key="item/destination.txt",
        metadata_directive="REPLACE",
        source_head={
            "VersionId": "source-v2",
            "ContentType": "text/plain",
            "ContentDisposition": "attachment",
            "Metadata": {"old": "value"},
        },
        content_type="application/pdf",
        metadata={"new": "value"},
        delete_source=True,
    )

    assert result.version_id == "copy-v1"
    assert [call[0] for call in s3_client.calls] == ["copy_object", "delete_object"]
    copy_call = s3_client.calls[0][1]
    assert copy_call["MetadataDirective"] == "REPLACE"
    assert copy_call["ContentType"] == "application/pdf"
    assert copy_call["ContentDisposition"] == "attachment"
    assert copy_call["Metadata"] == {"new": "value"}
    assert s3_client.calls[1][1] == {
        "Bucket": "drive-bucket",
        "Key": "item/source.txt",
        "VersionId": "source-v2",
    }
