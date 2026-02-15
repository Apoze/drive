"""
Tests for archive zip creation API endpoints.
"""

from io import BytesIO
from zipfile import ZipFile

from django.core.files.storage import default_storage

import pytest
from lasuite.drf.models.choices import RoleChoices
from rest_framework.test import APIClient

from core import factories, models

pytestmark = pytest.mark.django_db


def test_api_archive_zips_single_file_ok():
    """Zipping a single file creates a .zip in the destination folder."""

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )

    file_item = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="hello.txt",
        mimetype="text/plain",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"hello",
        upload_bytes__filename="hello.txt",
    )

    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/v1.0/archive-zips/",
        {
            "item_ids": [str(file_item.id)],
            "destination_folder_id": str(destination.id),
            "archive_name": "out.zip",
        },
        format="json",
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    status_response = client.get(f"/api/v1.0/archive-zips/{job_id}/")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["state"] == "done"

    created_zip_id = payload.get("result_item_id")
    assert created_zip_id
    created = models.Item.objects.get(pk=created_zip_id)
    assert created.type == models.ItemTypeChoices.FILE
    assert (created.filename or "").lower().endswith(".zip")

    raw = default_storage.open(created.file_key, "rb").read()
    with ZipFile(BytesIO(raw)) as zf:
        assert zf.namelist() == ["hello.txt"]
        assert zf.read("hello.txt") == b"hello"


def test_api_archive_zips_folder_ok():
    """Zipping a folder includes files under a folder prefix."""

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )

    folder = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FOLDER,
        title="MyFolder",
        users=[(user, RoleChoices.OWNER)],
    )
    factories.ItemFactory(
        creator=user,
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        title="a.txt",
        mimetype="text/plain",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"a",
        upload_bytes__filename="a.txt",
    )

    subfolder = factories.ItemFactory(
        creator=user,
        parent=folder,
        type=models.ItemTypeChoices.FOLDER,
        title="Sub",
        users=[(user, RoleChoices.OWNER)],
    )
    factories.ItemFactory(
        creator=user,
        parent=subfolder,
        type=models.ItemTypeChoices.FILE,
        title="b.txt",
        mimetype="text/plain",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"b",
        upload_bytes__filename="b.txt",
    )

    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/v1.0/archive-zips/",
        {
            "item_ids": [str(folder.id)],
            "destination_folder_id": str(destination.id),
            "archive_name": "folder.zip",
        },
        format="json",
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    status_response = client.get(f"/api/v1.0/archive-zips/{job_id}/")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["state"] == "done"

    created_zip_id = payload.get("result_item_id")
    assert created_zip_id
    created = models.Item.objects.get(pk=created_zip_id)

    raw = default_storage.open(created.file_key, "rb").read()
    with ZipFile(BytesIO(raw)) as zf:
        names = sorted(zf.namelist())
        assert names == ["MyFolder/Sub/b.txt", "MyFolder/a.txt"]
        assert zf.read("MyFolder/a.txt") == b"a"
        assert zf.read("MyFolder/Sub/b.txt") == b"b"
