"""Processing tasks for user reconciliation CSV imports."""

import csv
import logging
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError

from botocore.exceptions import ClientError

from core.models import UserReconciliation, UserReconciliationCsvImport

from drive.celery_app import app

logger = logging.getLogger(__name__)


def _safe_exception_message(exception):
    """Return bounded diagnostics safe for admin-visible import logs."""
    if isinstance(exception, KeyError):
        return str(exception).strip("'")
    if isinstance(exception, (csv.Error, ValidationError, ValueError, IntegrityError)):
        return str(exception)
    return type(exception).__name__


def _is_valid_email(email):
    """Return whether the provided email is syntactically valid."""
    try:
        validate_email(email)
    except (ValidationError, ValueError):
        return False
    return True


def _send_reconciliation_error_email(job, recipient_email, other_email):
    """Send an error email only when the recipient address is valid."""
    if not _is_valid_email(recipient_email):
        return
    job.send_reconciliation_error_email(
        recipient_email=recipient_email,
        other_email=other_email,
    )


def _process_row(row, job, counters):
    """Process a single row from the CSV file."""

    source_unique_id = row["id"].strip()

    # Skip entries if they already exist with this source_unique_id
    if UserReconciliation.objects.filter(source_unique_id=source_unique_id).exists():
        counters["already_processed_source_ids"] += 1
        return counters

    active_email_checked = row.get("active_email_checked", "0") == "1"
    inactive_email_checked = row.get("inactive_email_checked", "0") == "1"

    active_email = row["active_email"].strip()
    inactive_emails = [email.strip() for email in row["inactive_email"].split("|")]
    if not _is_valid_email(active_email):
        _send_reconciliation_error_email(job, inactive_emails[0], active_email)
        job.logs += "Invalid active email address in CSV row.\n"
        counters["rows_with_errors"] += 1
        return counters

    for inactive_email in inactive_emails:
        if not _is_valid_email(inactive_email):
            _send_reconciliation_error_email(job, active_email, inactive_email)
            job.logs += "Invalid inactive email address in CSV row.\n"
            counters["rows_with_errors"] += 1
            continue

        if inactive_email == active_email:
            _send_reconciliation_error_email(job, active_email, inactive_email)
            job.logs += "Same address set as both active and inactive email in CSV row.\n"
            counters["rows_with_errors"] += 1
            continue

        UserReconciliation.objects.create(
            active_email=active_email,
            inactive_email=inactive_email,
            active_email_checked=active_email_checked,
            inactive_email_checked=inactive_email_checked,
            active_email_confirmation_id=uuid.uuid4(),
            inactive_email_confirmation_id=uuid.uuid4(),
            source_unique_id=source_unique_id,
            status="pending",
        )
        counters["rec_entries_created"] += 1

    return counters


@app.task
def user_reconciliation_csv_import_job(job_id):
    """Process a UserReconciliationCsvImport job.

    Creates UserReconciliation entries from the CSV file.

    Does some sanity checks on the data:
    - active_email and inactive_email must be valid email addresses
    - active_email and inactive_email cannot be the same

    Rows with errors are logged in the job logs and skipped, but do not cause
    the entire job to fail or prevent the next rows from being processed.
    """
    try:
        job = UserReconciliationCsvImport.objects.get(id=job_id)
    except UserReconciliationCsvImport.DoesNotExist:
        logger.warning("CSV import job %s no longer exists; skipping.", job_id)
        return

    job.status = "running"
    job.save()

    counters = {
        "rec_entries_created": 0,
        "rows_with_errors": 0,
        "already_processed_source_ids": 0,
    }

    try:
        with job.file.open(mode="r") as file:
            reader = csv.DictReader(file)

            if not {"active_email", "inactive_email", "id"}.issubset(reader.fieldnames or []):
                raise KeyError("CSV is missing mandatory columns: active_email, inactive_email, id")

            for row in reader:
                counters = _process_row(row, job, counters)

        job.status = "done"
        job.logs += (
            f"Import completed successfully. {reader.line_num} rows processed."
            f" {counters['rec_entries_created']} reconciliation entries created."
            f" {counters['already_processed_source_ids']} rows were already processed."
            f" {counters['rows_with_errors']} rows had errors."
        )
    except (
        csv.Error,
        KeyError,
        ValidationError,
        ValueError,
        IntegrityError,
        OSError,
        ClientError,
    ) as exception:
        # Keep admin-visible logs bounded and free of local paths or CSV contents.
        job.status = "error"
        job.logs += f"Import failed: {_safe_exception_message(exception)}"
        logger.warning(
            "User reconciliation CSV import %s failed with %s",
            job_id,
            type(exception).__name__,
        )
    finally:
        job.save()
