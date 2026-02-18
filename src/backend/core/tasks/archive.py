"""Archive celery tasks."""

from __future__ import annotations

from logging import getLogger

from core.archive.extract import (
    extract_archive_to_drive,
    get_archive_extraction_job_status,
    set_archive_extraction_job_status,
)
from core.archive.extract_mount import (
    extract_archive_to_mount,
    get_mount_archive_extraction_job_status,
    set_mount_archive_extraction_job_status,
)
from core.archive.zip_create import (
    create_zip_from_items,
    get_archive_zip_job_status,
    set_archive_zip_job_status,
)

from drive.celery_app import app

logger = getLogger(__name__)


@app.task(bind=True, name="core.archive.extract_archive_to_drive")
def extract_archive_to_drive_task(self, **kwargs):
    """Celery task wrapper to run `extract_archive_to_drive` and persist status on failure."""

    kwargs = dict(kwargs)
    job_id = kwargs.pop("job_id", None) or self.request.id
    try:
        return extract_archive_to_drive(job_id=job_id, **kwargs)  # pylint: disable=missing-kwoa
    except Exception as exc:  # pylint: disable=broad-exception-caught
        status = get_archive_extraction_job_status(job_id)
        if "user_id" not in status and "user_id" in kwargs:
            status["user_id"] = kwargs["user_id"]
        status.update(
            {
                "state": "failed",
                "errors": [{"detail": str(exc)}],
            }
        )
        # Keep a best-effort status for the UI.
        set_archive_extraction_job_status(job_id, status)
        logger.exception("archive_extract: failed (job_id=%s)", job_id)
        raise


@app.task(bind=True, name="core.archive.extract_archive_to_mount")
def extract_archive_to_mount_task(self, **kwargs):
    """Celery task wrapper to run `extract_archive_to_mount` and persist status on failure."""

    kwargs = dict(kwargs)
    job_id = kwargs.pop("job_id", None) or self.request.id
    try:
        return extract_archive_to_mount(job_id=job_id, **kwargs)  # pylint: disable=missing-kwoa
    except Exception as exc:  # pylint: disable=broad-exception-caught
        status = get_mount_archive_extraction_job_status(job_id)
        if "user_id" not in status and "user_id" in kwargs:
            status["user_id"] = kwargs["user_id"]
        status.update(
            {
                "state": "failed",
                "errors": [{"detail": str(exc)}],
            }
        )
        set_mount_archive_extraction_job_status(job_id, status)
        logger.exception("mount_archive_extract: failed (job_id=%s)", job_id)
        raise


@app.task(bind=True, name="core.archive.create_zip_from_items")
def create_zip_from_items_task(self, **kwargs):
    """Celery task wrapper to run `create_zip_from_items` and persist status on failure."""

    kwargs = dict(kwargs)
    job_id = kwargs.pop("job_id", None) or self.request.id
    try:
        return create_zip_from_items(job_id=job_id, **kwargs)  # pylint: disable=missing-kwoa
    except Exception as exc:  # pylint: disable=broad-exception-caught
        status = get_archive_zip_job_status(job_id)
        if "user_id" not in status and "user_id" in kwargs:
            status["user_id"] = kwargs["user_id"]
        status.update(
            {
                "state": "failed",
                "errors": [{"detail": str(exc)}],
            }
        )
        set_archive_zip_job_status(job_id, status)
        logger.exception("archive_zip: failed (job_id=%s)", job_id)
        raise
