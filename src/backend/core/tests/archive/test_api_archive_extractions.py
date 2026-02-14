"""
Tests for archive extraction API endpoints.
"""

from io import BytesIO
import zipfile

import pytest
from django.core.files.storage import default_storage
from lasuite.drf.models.choices import RoleChoices
from rest_framework.test import APIClient

from core import factories, models


pytestmark = pytest.mark.django_db


def _make_zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_api_archive_extractions_zip_ok():
    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )

    zip_bytes = _make_zip_bytes(
        {
            "folder/hello.txt": b"hello",
            "root.txt": b"root",
        }
    )
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="test.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=zip_bytes,
        upload_bytes__filename="test.zip",
    )

    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/v1.0/archive-extractions/",
        {
            "item_id": str(archive.id),
            "destination_folder_id": str(destination.id),
            "mode": "all",
        },
        format="json",
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    status_response = client.get(f"/api/v1.0/archive-extractions/{job_id}/")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["state"] in {"done", "running", "queued"}

    # In eager mode, extraction should be completed synchronously.
    assert payload["state"] == "done"
    assert payload["progress"]["files_done"] == 2
    assert payload["progress"]["total"] == 2

    extracted_files = list(
        models.Item.objects.filter(path__descendants=destination.path)
        .exclude(id__in=[destination.id, archive.id])
        .filter(type=models.ItemTypeChoices.FILE)
    )
    assert len(extracted_files) == 2

    by_filename = {item.filename: item for item in extracted_files}
    assert "hello.txt" in by_filename
    assert "root.txt" in by_filename

    raw = default_storage.open(by_filename["hello.txt"].file_key, "rb").read()
    assert raw == b"hello"


def test_api_archive_extractions_zip_slip_is_blocked():
    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )
    zip_bytes = _make_zip_bytes({"../evil.txt": b"nope"})
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="slip.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=zip_bytes,
        upload_bytes__filename="slip.zip",
    )

    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/v1.0/archive-extractions/",
        {
            "item_id": str(archive.id),
            "destination_folder_id": str(destination.id),
            "mode": "all",
        },
        format="json",
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    status_response = client.get(f"/api/v1.0/archive-extractions/{job_id}/")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["state"] == "failed"

    extracted_files = list(
        models.Item.objects.filter(path__descendants=destination.path)
        .exclude(id__in=[destination.id, archive.id])
        .filter(type=models.ItemTypeChoices.FILE)
    )
    assert extracted_files == []
