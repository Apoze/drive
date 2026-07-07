"""Tests for the OnlyOffice conversion backend."""

# pylint: disable=missing-function-docstring

from unittest import mock

import pytest

from core import factories
from wopi.conversion.backends.onlyoffice import OnlyOfficeConversionBackend
from wopi.conversion.exceptions import ConversionProviderError


def _response(*, json_data=None, chunks=(), headers=None):
    response = mock.Mock()
    response.ok = True
    response.headers = headers or {}
    response.json.return_value = json_data or {}
    response.iter_content.return_value = iter(chunks)
    return response


def test_convert_posts_signed_payload_and_streams_download(settings):
    settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET = "secret"
    settings.WOPI_ONLYOFFICE_CONVERT_DOWNLOAD_MAX_BYTES = 100
    post_response = _response(json_data={"endConvert": True, "fileUrl": "https://onlyoffice/file"})
    get_response = _response(
        chunks=[b"abc", b"def"],
        headers={"Content-Length": "6"},
    )
    item = factories.ItemFactory.build(filename="REPORT.DOC")

    with (
        mock.patch("wopi.conversion.backends.onlyoffice.requests.post") as post,
        mock.patch("wopi.conversion.backends.onlyoffice.requests.get") as get,
    ):
        post.return_value = post_response
        get.return_value = get_response

        converted = OnlyOfficeConversionBackend("https://onlyoffice/converter").convert(
            item,
            "https://drive.example/source",
            "docx",
        )

    assert converted.read() == b"abcdef"
    assert converted.size == 6
    assert converted.name == "converted.docx"
    assert "token" in post.call_args.kwargs["json"]
    assert post.call_args.kwargs["json"]["token"] != "secret"
    assert get.call_args.kwargs["stream"] is True
    post_response.close.assert_called_once()
    get_response.close.assert_called_once()


def test_download_rejects_too_large_content_length(settings):
    settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET = "secret"
    settings.WOPI_ONLYOFFICE_CONVERT_DOWNLOAD_MAX_BYTES = 5
    backend = OnlyOfficeConversionBackend("https://onlyoffice/converter")
    response = _response(headers={"Content-Length": "6"})

    with mock.patch("wopi.conversion.backends.onlyoffice.requests.get", return_value=response):
        with pytest.raises(ConversionProviderError, match="too large"):
            backend._download("https://onlyoffice/file", "docx")  # pylint: disable=protected-access

    response.close.assert_called_once()


def test_download_rejects_too_large_stream(settings):
    settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET = "secret"
    settings.WOPI_ONLYOFFICE_CONVERT_DOWNLOAD_MAX_BYTES = 5
    backend = OnlyOfficeConversionBackend("https://onlyoffice/converter")
    response = _response(chunks=[b"abc", b"def"], headers={})

    with mock.patch("wopi.conversion.backends.onlyoffice.requests.get", return_value=response):
        with pytest.raises(ConversionProviderError, match="too large"):
            backend._download("https://onlyoffice/file", "docx")  # pylint: disable=protected-access

    response.close.assert_called_once()
