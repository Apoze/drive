"""Regular Drive file creation payload and storage mechanics."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO

from django.core.files.storage import default_storage

from core import models
from core.api import utils
from core.services.odf_templates import build_minimal_odf_template_bytes
from core.services.ooxml_templates import build_minimal_ooxml_template_bytes
from wopi.utils import get_wopi_client_config_for_filename


class FileCreationStorageMode(StrEnum):
    """Storage write mode for regular Drive creation payloads."""

    DEFAULT_SAVE = "default_save"
    DIRECT_S3_IF_AVAILABLE = "direct_s3_if_available"


@dataclass(frozen=True, slots=True)
class FileCreationPayload:
    """Resolved payload for a regular Drive file creation flow."""

    mimetype: str
    payload: bytes
    upload_state: models.ItemUploadStateChoices
    storage_mode: FileCreationStorageMode = FileCreationStorageMode.DEFAULT_SAVE

    @property
    def size(self) -> int:
        """Payload size in bytes."""
        return len(self.payload)


class FileCreationTemplateReadError(Exception):
    """Raised when a configured template payload cannot be read."""

    def __init__(self, *, template_path: str) -> None:
        self.template_path = template_path
        super().__init__(template_path)


class FileCreationStorageWriteError(Exception):
    """Raised when a creation payload cannot be written to regular storage."""


def resolve_legacy_template_creation_payload(
    *,
    base_dir: str,
    extension: str,
    filename: str,
) -> FileCreationPayload:
    """Read a legacy template asset and resolve its MIME metadata."""
    template_path = os.path.join(base_dir, "assets", "file_templates", f"template.{extension}")

    try:
        with open(template_path, "rb") as template_file:
            template_content = template_file.read()
    except OSError as exc:
        raise FileCreationTemplateReadError(template_path=template_path) from exc

    return FileCreationPayload(
        mimetype=utils.detect_mimetype(template_content, filename),
        payload=template_content,
        upload_state=models.ItemUploadStateChoices.READY,
    )


def resolve_odf_creation_payload(kind: str) -> FileCreationPayload:
    """Build a generated ODF creation payload."""
    mimetype, payload = build_minimal_odf_template_bytes(kind)
    return FileCreationPayload(
        mimetype=mimetype,
        payload=payload,
        upload_state=models.ItemUploadStateChoices.READY,
        storage_mode=FileCreationStorageMode.DIRECT_S3_IF_AVAILABLE,
    )


def resolve_new_file_creation_payload(extension: str) -> FileCreationPayload:
    """Resolve payload and state metadata for the generic new-file endpoint."""
    extension = str(extension or "").strip().lower().lstrip(".")
    odf_extensions = {"odt", "ods", "odp"}
    ooxml_mimetypes = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }

    if extension in odf_extensions:
        return resolve_odf_creation_payload(extension)

    if extension in ooxml_mimetypes:
        mimetype = ooxml_mimetypes[extension]
        editnew_client = get_wopi_client_config_for_filename(
            filename=f"new.{extension}",
            mimetype=mimetype,
            action="editnew",
        )
        if editnew_client:
            return FileCreationPayload(
                mimetype=mimetype,
                payload=b"",
                upload_state=models.ItemUploadStateChoices.CREATING,
            )

        mimetype, payload = build_minimal_ooxml_template_bytes(extension)
        return FileCreationPayload(
            mimetype=mimetype,
            payload=payload,
            upload_state=models.ItemUploadStateChoices.READY,
        )

    return FileCreationPayload(
        mimetype="application/octet-stream",
        payload=b"",
        upload_state=models.ItemUploadStateChoices.READY,
    )


def write_regular_file_creation_payload(
    *,
    storage_key: str,
    creation_payload: FileCreationPayload,
    storage=default_storage,
) -> None:
    """Write a regular Drive creation payload to configured storage."""
    try:
        if creation_payload.storage_mode == FileCreationStorageMode.DIRECT_S3_IF_AVAILABLE:
            s3_client = getattr(getattr(storage, "connection", None), "meta", None)
            s3_client = getattr(s3_client, "client", None)
            bucket_name = getattr(storage, "bucket_name", None)
            if s3_client and bucket_name:
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=storage_key,
                    Body=creation_payload.payload,
                    ContentType=creation_payload.mimetype or "application/octet-stream",
                )
                return

        storage.save(storage_key, BytesIO(creation_payload.payload))
    except Exception as exc:
        raise FileCreationStorageWriteError from exc


def delete_regular_file_creation_payload(
    *,
    storage_key: str,
    storage=default_storage,
) -> None:
    """Best-effort cleanup for a regular Drive creation payload."""
    storage.delete(storage_key)
