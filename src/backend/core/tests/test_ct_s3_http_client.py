"""Direct tests for CT-S3 std-lib HTTP transport."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

import socket
import urllib.error
from unittest import mock

import pytest

from core.ct_s3.http_client import HttpClientError, HttpResponse, http_request


def test_http_request_success_returns_minimal_response_and_lowercase_headers():
    response = mock.Mock()
    response.status = 204
    response.headers.items.return_value = [("X-Amz-Request-Id", "abc123")]
    response.read.return_value = b"ok"

    urlopen_cm = mock.Mock()
    urlopen_cm.__enter__ = mock.Mock(return_value=response)
    urlopen_cm.__exit__ = mock.Mock(return_value=False)

    with mock.patch("urllib.request.urlopen", return_value=urlopen_cm):
        result = http_request(
            url="http://s3.example.test/object",
            method="GET",
            headers={"X-Test": "1"},
            timeout_s=1.5,
        )

    assert result == HttpResponse(
        status_code=204,
        headers={"x-amz-request-id": "abc123"},
        body_len=2,
    )


def test_http_request_http_error_returns_response_without_raising():
    error = urllib.error.HTTPError(
        url="http://s3.example.test/object",
        code=403,
        msg="Forbidden",
        hdrs={"X-Request-Id": "req-1"},
        fp=None,
    )

    with mock.patch("urllib.request.urlopen", side_effect=error):
        result = http_request(url="http://s3.example.test/object", method="GET")

    assert result == HttpResponse(
        status_code=403,
        headers={"x-request-id": "req-1"},
        body_len=0,
    )


@pytest.mark.parametrize(
    ("reason", "expected_kind"),
    [
        (socket.gaierror(), "dns_failure"),
        (TimeoutError(), "connect_timeout"),
        (ConnectionRefusedError(), "connect_refused"),
        (OSError("other"), "url_error"),
    ],
)
def test_http_request_maps_urlerror_reasons_to_http_client_error(reason, expected_kind):
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError(reason)):
        with pytest.raises(HttpClientError) as exc_info:
            http_request(url="http://s3.example.test/object", method="GET")

    assert exc_info.value.kind == expected_kind
