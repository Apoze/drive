"""Direct tests for archive task wrappers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from unittest import mock

import pytest

from core.tasks import archive as archive_tasks


@pytest.mark.parametrize(
    ("task_obj", "extract_patch", "get_patch", "set_patch"),
    [
        (
            archive_tasks.extract_archive_to_drive_task,
            "core.tasks.archive.extract_archive_to_drive",
            "core.tasks.archive.get_archive_extraction_job_status",
            "core.tasks.archive.set_archive_extraction_job_status",
        ),
        (
            archive_tasks.extract_archive_to_mount_task,
            "core.tasks.archive.extract_archive_to_mount",
            "core.tasks.archive.get_mount_archive_extraction_job_status",
            "core.tasks.archive.set_mount_archive_extraction_job_status",
        ),
        (
            archive_tasks.create_zip_from_items_task,
            "core.tasks.archive.create_zip_from_items",
            "core.tasks.archive.get_archive_zip_job_status",
            "core.tasks.archive.set_archive_zip_job_status",
        ),
    ],
)
def test_archive_task_wrappers_persist_failed_status_best_effort(
    task_obj,
    extract_patch,
    get_patch,
    set_patch,
):
    with (
        mock.patch(extract_patch, side_effect=ValueError("boom")),
        mock.patch(get_patch, return_value={}),
        mock.patch(set_patch) as mock_set_status,
        mock.patch("core.tasks.archive.logger.exception"),
    ):
        with pytest.raises(ValueError, match="boom"):
            task_obj.run(job_id="job-1", user_id="user-1")

    mock_set_status.assert_called_once()
    job_id, payload = mock_set_status.call_args.args
    assert job_id == "job-1"
    assert payload["state"] == "failed"
    assert payload["errors"] == [{"detail": "boom"}]
    assert payload["user_id"] == "user-1"
