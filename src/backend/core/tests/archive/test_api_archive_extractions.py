"""
Tests for archive extraction API endpoints.
"""

import zipfile
from io import BytesIO
import stat

from django.core.files.storage import default_storage

import pytest
from lasuite.drf.models.choices import RoleChoices
from rest_framework.test import APIClient

from core import factories, models

pytestmark = pytest.mark.django_db


def _make_zip_bytes(entries: dict[str, bytes]) -> bytes:
    """Build a zip file (as bytes) from a mapping of path -> content."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _make_zip_with_symlink_entry() -> bytes:
    """Build a zip file containing a symlink entry (Info-ZIP style external_attr)."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo("link")
        info.create_system = 3  # Unix
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, "target")
        zf.writestr("ok.txt", b"ok")
    return buf.getvalue()


def test_api_archive_extractions_zip_ok():
    """Extracting a normal zip creates children in the destination folder."""
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
    """Zip-slip entries are rejected and do not create files outside destination."""
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
    assert not extracted_files


def test_api_archive_extractions_zip_symlink_is_ignored():
    """Symlink entries in zip archives are ignored (never created server-side)."""

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )
    zip_bytes = _make_zip_with_symlink_entry()
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="symlink.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=zip_bytes,
        upload_bytes__filename="symlink.zip",
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
    assert payload["state"] == "done"
    assert payload["progress"]["files_done"] == 1

    extracted_files = list(
        models.Item.objects.filter(path__descendants=destination.path)
        .exclude(id__in=[destination.id, archive.id])
        .filter(type=models.ItemTypeChoices.FILE)
    )
    assert len(extracted_files) == 1
    assert extracted_files[0].filename == "ok.txt"
    raw = default_storage.open(extracted_files[0].file_key, "rb").read()
    assert raw == b"ok"


def test_api_archive_extractions_zip_symlink_strict_fails(monkeypatch):
    """When ARCHIVE_FS_STRICT is enabled, symlink entries make the job fail closed."""

    monkeypatch.setenv("ARCHIVE_FS_STRICT", "1")

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )
    zip_bytes = _make_zip_with_symlink_entry()
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="symlink.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=zip_bytes,
        upload_bytes__filename="symlink.zip",
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
    payload = status_response.json()
    assert payload["state"] == "failed"


def test_api_archive_extractions_collision_skip():
    """When collision_policy=skip, existing files are preserved and no new file is created."""

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )

    existing = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="root.txt",
        mimetype="text/plain",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"old",
        upload_bytes__filename="root.txt",
    )

    zip_bytes = _make_zip_bytes({"root.txt": b"new"})
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="skip.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=zip_bytes,
        upload_bytes__filename="skip.zip",
    )

    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/v1.0/archive-extractions/",
        {
            "item_id": str(archive.id),
            "destination_folder_id": str(destination.id),
            "mode": "all",
            "collision_policy": "skip",
        },
        format="json",
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    status_response = client.get(f"/api/v1.0/archive-extractions/{job_id}/")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["state"] == "done"

    extracted_files = list(
        models.Item.objects.filter(path__descendants=destination.path)
        .exclude(id__in=[destination.id, archive.id])
        .filter(type=models.ItemTypeChoices.FILE)
    )
    assert {i.id for i in extracted_files} == {existing.id}

    raw = default_storage.open(existing.file_key, "rb").read()
    assert raw == b"old"


def test_api_archive_extractions_collision_overwrite():
    """When collision_policy=overwrite, existing files are overwritten in place."""

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )

    existing = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="root.txt",
        mimetype="text/plain",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"old",
        upload_bytes__filename="root.txt",
    )

    zip_bytes = _make_zip_bytes({"root.txt": b"new"})
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="overwrite.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=zip_bytes,
        upload_bytes__filename="overwrite.zip",
    )

    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/v1.0/archive-extractions/",
        {
            "item_id": str(archive.id),
            "destination_folder_id": str(destination.id),
            "mode": "all",
            "collision_policy": "overwrite",
        },
        format="json",
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    status_response = client.get(f"/api/v1.0/archive-extractions/{job_id}/")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["state"] == "done"

    extracted_files = list(
        models.Item.objects.filter(path__descendants=destination.path)
        .exclude(id__in=[destination.id, archive.id])
        .filter(type=models.ItemTypeChoices.FILE)
    )
    assert {i.id for i in extracted_files} == {existing.id}

    raw = default_storage.open(existing.file_key, "rb").read()
    assert raw == b"new"


def test_api_archive_extractions_create_root_folder_default_name():
    """When create_root_folder=true, extraction happens inside a new folder named after the archive."""

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )

    zip_bytes = _make_zip_bytes({"root.txt": b"root"})
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="archiveA.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=zip_bytes,
        upload_bytes__filename="archiveA.zip",
    )

    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/v1.0/archive-extractions/",
        {
            "item_id": str(archive.id),
            "destination_folder_id": str(destination.id),
            "mode": "all",
            "create_root_folder": True,
        },
        format="json",
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    status_response = client.get(f"/api/v1.0/archive-extractions/{job_id}/")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["state"] == "done"

    created_folder = (
        models.Item.objects.children(destination.path)
        .filter(
            type=models.ItemTypeChoices.FOLDER,
            title="archiveA",
            deleted_at__isnull=True,
            hard_deleted_at__isnull=True,
            ancestors_deleted_at__isnull=True,
        )
        .first()
    )
    assert created_folder is not None

    extracted = (
        models.Item.objects.filter(path__descendants=created_folder.path)
        .exclude(id=created_folder.id)
        .filter(type=models.ItemTypeChoices.FILE, filename="root.txt")
        .first()
    )
    assert extracted is not None
    raw = default_storage.open(extracted.file_key, "rb").read()
    assert raw == b"root"


def test_api_archive_extractions_limits_max_files(monkeypatch):
    """Extraction fails when max files limit is exceeded."""

    monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_FILES", "1")

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )

    zip_bytes = _make_zip_bytes({"a.txt": b"a", "b.txt": b"b"})
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="too_many.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=zip_bytes,
        upload_bytes__filename="too_many.zip",
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
    payload = status_response.json()
    assert payload["state"] == "failed"


def test_api_archive_extractions_limits_max_total_size(monkeypatch):
    """Extraction fails when max total uncompressed size limit is exceeded."""

    monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_TOTAL_SIZE", "3")

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )

    zip_bytes = _make_zip_bytes({"a.txt": b"aa", "b.txt": b"bb"})
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="too_big.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=zip_bytes,
        upload_bytes__filename="too_big.zip",
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
    payload = status_response.json()
    assert payload["state"] == "failed"


def test_api_archive_extractions_limits_compression_ratio(monkeypatch):
    """Extraction fails when compression ratio looks suspicious."""

    monkeypatch.setenv("ARCHIVE_EXTRACT_MAX_COMPRESSION_RATIO", "5")

    user = factories.UserFactory()
    destination = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, RoleChoices.OWNER)],
    )

    # Highly compressible payload: should exceed ratio limit when env is low.
    zip_bytes = _make_zip_bytes({"bomb.txt": b"0" * 50_000})
    archive = factories.ItemFactory(
        creator=user,
        parent=destination,
        type=models.ItemTypeChoices.FILE,
        title="ratio.zip",
        mimetype="application/zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=zip_bytes,
        upload_bytes__filename="ratio.zip",
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
    payload = status_response.json()
    assert payload["state"] == "failed"
