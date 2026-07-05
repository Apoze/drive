"""Direct tests for archive extraction runtime helper contracts."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from types import SimpleNamespace

from django.core.cache import cache

from core import models
from core.archive.extract import (
    _default_root_folder_title,
    archive_job_cache_key,
    get_archive_extraction_job_status,
    is_supported_archive_for_server_extraction,
    set_archive_extraction_job_status,
    start_archive_extraction_job,
)


def test_archive_job_cache_key_and_missing_status_are_stable():
    job_id = "extract-job-missing"
    cache.delete(archive_job_cache_key(job_id))

    assert archive_job_cache_key(job_id) == "archive_extraction_job:extract-job-missing"
    assert get_archive_extraction_job_status(job_id) == {
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


def test_archive_extraction_job_status_roundtrip_and_start_payload():
    payload = {"state": "running", "errors": [], "progress": {"total": 2}}
    set_archive_extraction_job_status("extract-job-roundtrip", payload)
    assert get_archive_extraction_job_status("extract-job-roundtrip") == payload

    assert (
        start_archive_extraction_job(
            job_id="extract-job-start",
            archive_item_id="archive-1",
            destination_folder_id="folder-1",
            user_id="user-1",
            mode="selection",
            selection_paths=["folder/"],
            collision_policy="skip",
            create_root_folder=True,
        )
        == "extract-job-start"
    )

    assert get_archive_extraction_job_status("extract-job-start") == {
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
        "archive_item_id": "archive-1",
        "destination_folder_id": "folder-1",
        "user_id": "user-1",
        "mode": "selection",
        "selection_paths": ["folder/"],
        "collision_policy": "skip",
        "create_root_folder": True,
    }


def test_is_supported_archive_for_server_extraction_matches_file_type_and_extension():
    assert is_supported_archive_for_server_extraction(
        SimpleNamespace(type=models.ItemTypeChoices.FILE, filename="archive.zip")
    )
    assert is_supported_archive_for_server_extraction(
        SimpleNamespace(type=models.ItemTypeChoices.FILE, filename="archive.tar.gz")
    )
    assert not is_supported_archive_for_server_extraction(
        SimpleNamespace(type=models.ItemTypeChoices.FILE, filename="archive.pdf")
    )
    assert not is_supported_archive_for_server_extraction(
        SimpleNamespace(type=models.ItemTypeChoices.FOLDER, filename="archive.zip")
    )


def test_default_root_folder_title_strips_zip_suffix_and_sanitizes_segments():
    archive_item = SimpleNamespace(title=" My/Archive.zip ", filename="ignored.zip")

    assert _default_root_folder_title(archive_item) == "My_Archive"
