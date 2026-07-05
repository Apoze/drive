"""Direct contract tests for public share link serializers."""
# pylint: disable=missing-function-docstring,missing-class-docstring,line-too-long

from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote

from django.test import override_settings
from django.utils import timezone

import pytest

from core import factories, models
from core.api.serializers_share_links import PublicShareItemSerializer

pytestmark = pytest.mark.django_db


@override_settings(
    MEDIA_BASE_URL="http://testserver",
    MEDIA_URL="/media/",
    MEDIA_URL_PREVIEW="/media/preview/",
    ITEM_UPLOAD_PENDING_TTL_SECONDS=60,
)
def test_public_share_item_serializer_adds_share_token_and_quotes_file_key_for_ready_previewable_file():
    item = factories.ItemFactory(
        type=models.ItemTypeChoices.FILE,
        title="Quarterly Report #1.png",
        mimetype="image/png",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"image-bytes",
        upload_bytes__filename="Quarterly Report #1.png",
    )

    serializer = PublicShareItemSerializer(
        instance=item,
        context={"share_token": "tok+en/?"},
    )

    expected_key = quote(item.file_key)
    expected_query = "share_token=tok%2Ben%2F%3F"

    assert serializer.data["upload_state"] == models.ItemUploadStateChoices.READY
    assert serializer.data["url"] == f"http://testserver/media/{expected_key}?{expected_query}"
    assert serializer.data["url_preview"] == (
        f"http://testserver/media/preview/{expected_key}?{expected_query}"
    )


@override_settings(
    MEDIA_BASE_URL="http://testserver",
    MEDIA_URL="/media/",
    MEDIA_URL_PREVIEW="/media/preview/",
    ITEM_UPLOAD_PENDING_TTL_SECONDS=60,
)
def test_public_share_item_serializer_uses_effective_upload_state_and_hides_urls_for_pending_or_expired():
    pending_item = factories.ItemFactory(
        type=models.ItemTypeChoices.FILE,
        mimetype="image/png",
        update_upload_state=models.ItemUploadStateChoices.PENDING,
        upload_bytes=b"image-bytes",
        upload_bytes__filename="pending.png",
    )
    pending_item.upload_started_at = timezone.now()
    pending_item.save(update_fields=["upload_started_at", "updated_at"])

    expired_item = factories.ItemFactory(
        type=models.ItemTypeChoices.FILE,
        mimetype="image/png",
        update_upload_state=models.ItemUploadStateChoices.PENDING,
        upload_bytes=b"image-bytes",
        upload_bytes__filename="expired.png",
    )
    expired_item.upload_started_at = timezone.now() - timedelta(seconds=120)
    expired_item.save(update_fields=["upload_started_at", "updated_at"])

    pending_payload = PublicShareItemSerializer(
        instance=pending_item, context={"share_token": "share-token"}
    ).data
    expired_payload = PublicShareItemSerializer(
        instance=expired_item, context={"share_token": "share-token"}
    ).data

    assert pending_payload["upload_state"] == models.ItemUploadStateChoices.PENDING
    assert pending_payload["url"] is None
    assert pending_payload["url_preview"] is None
    assert expired_payload["upload_state"] == models.ItemUploadStateChoices.EXPIRED
    assert expired_payload["url"] is None
    assert expired_payload["url_preview"] is None


@override_settings(
    MEDIA_BASE_URL="http://testserver",
    MEDIA_URL="/media/",
    MEDIA_URL_PREVIEW="/media/preview/",
)
def test_public_share_item_serializer_hides_url_for_non_downloadable_or_non_previewable_items():
    folder_item = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
        title="Shared folder",
    )
    binary_file = factories.ItemFactory(
        type=models.ItemTypeChoices.FILE,
        title="firmware.bin",
        mimetype="application/octet-stream",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"binary",
        upload_bytes__filename="firmware.bin",
    )

    folder_payload = PublicShareItemSerializer(
        instance=folder_item, context={"share_token": "share-token"}
    ).data
    binary_payload = PublicShareItemSerializer(
        instance=binary_file, context={"share_token": "share-token"}
    ).data

    assert folder_payload["url"] is None
    assert folder_payload["url_preview"] is None
    assert (
        binary_payload["url"]
        == f"http://testserver/media/{quote(binary_file.file_key)}?share_token=share-token"
    )
    assert binary_payload["url_preview"] is None
