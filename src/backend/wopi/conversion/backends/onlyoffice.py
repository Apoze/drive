"""OnlyOffice server-to-server conversion backend."""

from tempfile import SpooledTemporaryFile
from uuid import uuid4

from django.conf import settings
from django.core.files.base import File

import jwt
import requests

from wopi.conversion.exceptions import ConversionProviderError


class SizedFile(File):
    """File wrapper with a trusted size for spooled conversion downloads."""

    def __init__(self, file, *, name: str, size: int):
        super().__init__(file, name=name)
        self._conversion_size = size

    @property
    def size(self):
        return self._conversion_size


class OnlyOfficeConversionBackend:
    """Run a synchronous OnlyOffice conversion through the /converter endpoint."""

    download_chunk_size = 64 * 1024

    def __init__(
        self,
        convert_service_url,
        http_timeout=None,
        download_timeout=None,
    ):
        self.convert_service_url = convert_service_url
        self.jwt_secret = settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET
        self.http_timeout = http_timeout or (
            settings.WOPI_ONLYOFFICE_CONVERT_HTTP_CONNECT_TIMEOUT,
            settings.WOPI_ONLYOFFICE_CONVERT_HTTP_READ_TIMEOUT,
        )
        self.download_timeout = download_timeout or (
            settings.WOPI_ONLYOFFICE_CONVERT_DOWNLOAD_CONNECT_TIMEOUT,
            settings.WOPI_ONLYOFFICE_CONVERT_DOWNLOAD_READ_TIMEOUT,
        )

    def _request(self, method, url, label, **kwargs):
        """Issue an HTTP request and translate transport/HTTP errors."""
        try:
            response = getattr(requests, method)(url, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise ConversionProviderError(str(exc)) from exc

        if not response.ok:
            response.close()
            raise ConversionProviderError(
                f"OnlyOffice {label} returned status {response.status_code}"
            )
        return response

    def _post_convert(self, payload, headers, key):
        """Call /converter and return the parsed completion payload."""
        response = self._request(
            "post",
            self.convert_service_url,
            label="/converter",
            params={"shardkey": key},
            json=payload,
            headers=headers,
            timeout=self.http_timeout,
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise ConversionProviderError("OnlyOffice returned a non-JSON body") from exc
        finally:
            response.close()

        if data.get("error"):
            raise ConversionProviderError(f"OnlyOffice error code {data['error']}")
        if not data.get("endConvert") or not data.get("fileUrl"):
            raise ConversionProviderError("OnlyOffice did not report a completed conversion")
        return data

    def _download(self, file_url, target_extension):
        """Stream the converted file into a spooled file with an explicit size cap."""
        max_bytes = int(settings.WOPI_ONLYOFFICE_CONVERT_DOWNLOAD_MAX_BYTES)
        response = self._request(
            "get",
            file_url,
            label="file download",
            timeout=self.download_timeout,
            stream=True,
        )
        try:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise ConversionProviderError("OnlyOffice converted file is too large")

            total = 0
            spooled = SpooledTemporaryFile(
                max_size=int(settings.WOPI_ONLYOFFICE_CONVERT_DOWNLOAD_SPOOL_MEMORY_BYTES)
            )
            try:
                for chunk in response.iter_content(chunk_size=self.download_chunk_size):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise ConversionProviderError("OnlyOffice converted file is too large")
                    spooled.write(chunk)
                spooled.seek(0)
            except Exception:
                spooled.close()
                raise

            return SizedFile(
                spooled,
                name=f"converted.{target_extension}",
                size=total,
            )
        finally:
            response.close()

    def convert(self, item, source_url, target_extension):
        """Convert the item via OnlyOffice and return the converted bytes."""
        key = f"{item.id}-{uuid4()}"
        payload = {
            "async": False,
            "filetype": (item.extension or "").lower(),
            "outputtype": target_extension,
            "key": key,
            "title": item.filename,
            "url": source_url,
        }
        headers = {"Accept": "application/json"}
        if self.jwt_secret:
            token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
            payload = {"token": token}

        data = self._post_convert(payload, headers, key)
        return self._download(data["fileUrl"], target_extension)
