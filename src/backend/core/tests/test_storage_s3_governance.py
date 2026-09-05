"""One real S3 scenario covers admission, publication, copying and capability replay."""

from datetime import timedelta
from io import BytesIO, StringIO
from unittest.mock import patch
from urllib.parse import urlsplit

from django.core.files.storage import default_storage
from django.core.management import call_command
from django.utils import timezone

import pytest
from rest_framework.test import APIClient

from core import factories, models
from core.api.views_storage_upload import upload_url
from core.services import storage_quota as quota
from core.services.regular_storage_copy import copy_regular_storage_object
from core.services.s3_streaming import stream_to_s3_object
from core.services.storage_inventory import initialize_items
from core.services.storage_recovery import reconcile_operation
from core.tasks.item import rename_file


@pytest.mark.django_db(transaction=True)
# pylint: disable-next=too-many-statements
def test_s3_governance_publication_quota_and_single_use(settings):  # noqa: PLR0915
    """Rejected growth preserves the old version; successful writes count once."""
    settings.STORAGE_GOVERNANCE_ENABLED = True
    actor = factories.UserFactory()
    item = factories.ItemFactory(
        creator=actor,
        type="file",
        filename="governed.txt",
        upload_state=models.ItemUploadStateChoices.PENDING,
        size=0,
    )
    initialize_items()
    account = f"user:{actor.pk}"
    quota.apply_policy({account: {"limit_bytes": 5}}, revision="test")
    client = default_storage.connection.meta.client
    bucket = default_storage.bucket_name
    common = {
        "s3_client": client,
        "bucket": bucket,
        "key": item.file_key,
        "content_type": "text/plain",
    }
    with pytest.raises(quota.StorageQuotaExceeded):
        stream_to_s3_object(**common, body_stream=BytesIO(b"too long"))
    url = urlsplit(upload_url(item))
    api = APIClient()
    response = api.put(
        url.path, b"hello", content_type="text/plain", HTTP_X_DRIVE_UPLOAD_TOKEN=url.fragment
    )
    assert response.status_code == 200
    assert (
        api.put(
            url.path, b"oops", content_type="text/plain", HTTP_X_DRIVE_UPLOAD_TOKEN=url.fragment
        ).status_code
        == 409
    )
    assert (
        api.put(
            url.path, b"oops", content_type="text/plain", HTTP_X_DRIVE_UPLOAD_TOKEN="invalid"
        ).status_code
        == 403
    )
    item.refresh_from_db()
    assert item.size == 5
    usage = models.StorageQuota.objects.get(key=account)
    assert (usage.used_bytes, usage.reserved_bytes) == (5, 0)
    with pytest.raises(quota.StorageQuotaExceeded):
        stream_to_s3_object(**common, body_stream=BytesIO(b"longer"))
    with default_storage.open(item.file_key) as content:
        assert content.read() == b"hello"
    copy = factories.ItemFactory(
        creator=actor,
        type="file",
        filename="copy.txt",
        size=5,
        upload_state=models.ItemUploadStateChoices.DUPLICATING,
    )
    with pytest.raises(quota.StorageQuotaExceeded):
        copy_regular_storage_object(
            s3_client=client, bucket=bucket, source_key=item.file_key, destination_key=copy.file_key
        )
    quota.apply_policy({account: {"limit_bytes": 10}}, revision="raised")
    copy_regular_storage_object(
        s3_client=client, bucket=bucket, source_key=item.file_key, destination_key=copy.file_key
    )
    usage.refresh_from_db()
    assert (usage.used_bytes, usage.reserved_bytes) == (10, 0)
    quota.apply_policy({account: {"limit_bytes": 3}}, revision="lowered")
    stream_to_s3_object(**common, body_stream=BytesIO(b"hi"))
    usage.refresh_from_db()
    assert (usage.used_bytes, usage.reserved_bytes) == (7, 0)
    call_command("storage_inventory", "--check", "--verify-items", stdout=StringIO())
    item.refresh_from_db()
    item.upload_state = models.ItemUploadStateChoices.READY
    item.save()
    previous_key = item.file_key
    with patch(
        "core.services.storage_s3_write.StorageS3Write.completed",
        side_effect=RuntimeError("Interrupted"),
    ):
        with pytest.raises(RuntimeError, match="Interrupted"):
            rename_file(item.pk, "renamed")
    item.refresh_from_db()
    assert item.file_key == previous_key
    with pytest.raises(quota.StorageWriteConflict):
        item.soft_delete()
    item.refresh_from_db()
    with default_storage.open(item.file_key) as content:
        assert content.read() == b"hi"
    operation = models.StorageReservation.objects.get(
        resource_key=quota.resource_key(f"item:{item.pk}"), state="publishing"
    )
    operation.expires_at = timezone.now() - timedelta(seconds=1)
    operation.save()
    assert reconcile_operation(operation.pk) == "committed"
    item.refresh_from_db()
    assert item.filename == "renamed.txt"
    with default_storage.open(item.file_key) as content:
        assert content.read() == b"hi"
    usage.refresh_from_db()
    assert (usage.used_bytes, usage.reserved_bytes) == (7, 0)
