"""Direct tests for CT-S3 safe header shaping."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from core.ct_s3.safe import pick_headers


def test_pick_headers_keeps_allowlisted_headers_only_and_lowercases_keys():
    headers = {
        "Host": "s3.example.test",
        "X-Amz-Request-Id": "req-1",
        "Authorization": "secret",
    }

    assert pick_headers(headers, {"host", "x-amz-request-id"}) == {
        "host": "s3.example.test",
        "x-amz-request-id": "req-1",
    }
