"""Direct tests for archive zip helper contracts."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from django.core.cache import cache

import pytest
from lasuite.drf.models.choices import RoleChoices

from core import factories, models
from core.archive.zip_create import (
    _iter_zip_entries_for_item,
    _safe_component,
    _unique_entry_path,
    archive_zip_job_cache_key,
    get_archive_zip_job_status,
    set_archive_zip_job_status,
    start_archive_zip_job,
)

pytestmark = pytest.mark.django_db


def test_archive_zip_job_cache_key_and_missing_status_are_stable():
    job_id = "zip-job-missing"
    cache.delete(archive_zip_job_cache_key(job_id))

    assert archive_zip_job_cache_key(job_id) == "archive_zip_job:zip-job-missing"
    assert get_archive_zip_job_status(job_id) == {
        "state": "unknown",
        "progress": {
            "files_done": 0,
            "total": 0,
            "bytes_done": 0,
            "bytes_total": 0,
        },
        "skipped_symlinks_count": 0,
        "skipped_unsafe_paths_count": 0,
        "errors": [],
    }


def test_archive_zip_job_status_roundtrip_and_start_payload():
    payload = {"state": "running", "errors": [], "progress": {"total": 2}}
    set_archive_zip_job_status("zip-job-roundtrip", payload)
    assert get_archive_zip_job_status("zip-job-roundtrip") == payload

    assert (
        start_archive_zip_job(
            job_id="zip-job-start",
            source_item_ids=["file-1", "file-2"],
            destination_folder_id="folder-1",
            user_id="user-1",
            archive_name="bundle.zip",
        )
        == "zip-job-start"
    )

    assert get_archive_zip_job_status("zip-job-start") == {
        "state": "queued",
        "progress": {
            "files_done": 0,
            "total": 0,
            "bytes_done": 0,
            "bytes_total": 0,
        },
        "skipped_symlinks_count": 0,
        "skipped_unsafe_paths_count": 0,
        "errors": [],
        "source_item_ids": ["file-1", "file-2"],
        "destination_folder_id": "folder-1",
        "archive_name": "bundle.zip",
        "user_id": "user-1",
    }


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (" report.txt ", "report.txt"),
        ("folder/name", "folder_name"),
        ("folder\\name", "folder_name"),
        ("", "_"),
        ("   ", "_"),
    ],
)
def test_safe_component_sanitizes_archive_components(name, expected):
    assert _safe_component(name) == expected


def test_unique_entry_path_keeps_first_and_suffixes_duplicates():
    used_paths = set()

    assert _unique_entry_path("Folder/report.txt", used_paths) == "Folder/report.txt"
    assert _unique_entry_path("Folder/report.txt", used_paths) == "Folder/report_01.txt"
    assert _unique_entry_path("Folder/report.txt", used_paths) == "Folder/report_02.txt"
    assert _unique_entry_path("report", used_paths) == "report"
    assert _unique_entry_path("report", used_paths) == "report_01"


def test_iter_zip_entries_for_file_root_returns_single_safe_component():
    user = factories.UserFactory()
    file_item = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FILE,
        title="Ignored title",
        filename="hello/world.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"hello",
        upload_bytes__filename="hello/world.txt",
        users=[(user, RoleChoices.OWNER)],
    )

    assert _iter_zip_entries_for_item(root=file_item, user=user) == [(file_item, "hello_world.txt")]


def test_iter_zip_entries_for_folder_root_returns_files_under_folder_prefix():
    user = factories.UserFactory()
    root = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
        title="My/Folder",
        users=[(user, RoleChoices.OWNER)],
    )
    child_folder = factories.ItemFactory(
        creator=user,
        parent=root,
        type=models.ItemTypeChoices.FOLDER,
        title="Sub\\Dir",
        users=[(user, RoleChoices.OWNER)],
    )
    leaf = factories.ItemFactory(
        creator=user,
        parent=child_folder,
        type=models.ItemTypeChoices.FILE,
        title="leaf.txt",
        filename="leaf.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"leaf",
        upload_bytes__filename="leaf.txt",
        users=[(user, RoleChoices.OWNER)],
    )

    sibling_leaf = factories.ItemFactory(
        creator=user,
        parent=root,
        type=models.ItemTypeChoices.FILE,
        title="secret.txt",
        filename="secret.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"secret",
        upload_bytes__filename="secret.txt",
        users=[(user, RoleChoices.OWNER)],
    )

    entries = _iter_zip_entries_for_item(root=root, user=user)

    assert [path for _, path in entries] == [
        "My_Folder/Sub_Dir/leaf.txt",
        "My_Folder/secret.txt",
    ]
    assert [item for item, _ in entries] == [leaf, sibling_leaf]
