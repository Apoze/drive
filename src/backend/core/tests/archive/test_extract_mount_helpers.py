"""Direct tests for mount archive extraction helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from django.test import override_settings

import pytest

from core.archive.extract_mount import (
    _get_enabled_mount_or_404,
    get_mount_archive_extraction_job_status,
    mount_archive_job_cache_key,
    set_mount_archive_extraction_job_status,
    start_mount_archive_extraction_job,
)


def test_mount_archive_job_cache_key_is_stable():
    assert mount_archive_job_cache_key("job-123") == "mount_archive_extraction_job:job-123"


def test_mount_archive_job_status_roundtrip_and_missing_payload():
    job_id = "mount-job-status"

    assert get_mount_archive_extraction_job_status(job_id) == {
        "state": "missing",
        "errors": [],
    }

    payload = {"state": "running", "errors": ["none"], "progress": {"total": 1}}
    set_mount_archive_extraction_job_status(job_id, payload)

    assert get_mount_archive_extraction_job_status(job_id) == payload


def test_start_mount_archive_extraction_job_sets_queued_payload():
    job_id = "mount-job-start"

    start_mount_archive_extraction_job(
        job_id=job_id,
        archive_item_id="archive-1",
        mount_id="mount-1",
        destination_path="/target",
        user_id="user-1",
        mode="all",
        selection_paths=["dir/a.txt"],
    )

    assert get_mount_archive_extraction_job_status(job_id) == {
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
        "user_id": "user-1",
        "mount_id": "mount-1",
        "destination_path": "/target",
        "archive_item_id": "archive-1",
        "mode": "all",
        "selection_paths": ["dir/a.txt"],
    }


@override_settings(
    MOUNTS_REGISTRY=[
        {"mount_id": "disabled", "enabled": False},
        {"mount_id": "enabled", "enabled": True, "label": "Mount A"},
    ]
)
def test_get_enabled_mount_or_404_returns_only_enabled_mount():
    assert _get_enabled_mount_or_404("enabled") == {
        "mount_id": "enabled",
        "enabled": True,
        "label": "Mount A",
    }


@override_settings(
    MOUNTS_REGISTRY=[
        {"mount_id": "disabled", "enabled": False},
    ]
)
def test_get_enabled_mount_or_404_raises_for_missing_or_disabled_mount():
    with pytest.raises(KeyError, match="mount.not_found"):
        _get_enabled_mount_or_404("disabled")

    with pytest.raises(KeyError, match="mount.not_found"):
        _get_enabled_mount_or_404("unknown")
