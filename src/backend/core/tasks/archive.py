"""Archive extraction celery tasks."""

from __future__ import annotations

from logging import getLogger

from drive.celery_app import app

from core.archive.extract import (
    extract_archive_to_drive,
    get_archive_extraction_job_status,
    set_archive_extraction_job_status,
)

logger = getLogger(__name__)


@app.task(bind=True, name="core.archive.extract_archive_to_drive")
def extract_archive_to_drive_task(self, **kwargs):
    kwargs = dict(kwargs)
    job_id = kwargs.pop("job_id", None) or self.request.id
    try:
        return extract_archive_to_drive(job_id=job_id, **kwargs)
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
