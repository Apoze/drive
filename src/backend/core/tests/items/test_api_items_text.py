"""Test the Item text preview/editor endpoint."""

from io import BytesIO

from django.core.files.storage import default_storage

import pytest
from rest_framework.test import APIClient

from core import factories, models

pytestmark = pytest.mark.django_db


def _create_text_item(*, content: bytes, filename: str = "note.txt"):
    folder = factories.ItemFactory(type=models.ItemTypeChoices.FOLDER)
    item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename=filename,
        mimetype="text/plain",
        update_upload_state=models.ItemUploadStateChoices.READY,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
    )
    user = factories.UserFactory()
    factories.UserItemAccessFactory(
        item=item, user=user, role=models.RoleChoices.EDITOR
    )

    default_storage.save(item.file_key, BytesIO(content))
    return item, user


def test_api_items_text_get_ok():
    """Eligible text files should return content + ETag."""
    item, user = _create_text_item(content=b"hello")

    client = APIClient()
    client.force_login(user)
    response = client.get(f"/api/v1.0/items/{item.id}/text/")

    assert response.status_code == 200
    assert response.headers.get("ETag")
    payload = response.json()
    assert payload["content"] == "hello"
    assert payload["truncated"] is False
    assert payload["size"] == 5
    assert payload["etag"] == response.headers["ETag"]


def test_api_items_text_get_truncated():
    """Text previews must be truncated at 500KB and report the truncation."""
    max_bytes = 500 * 1024
    item, user = _create_text_item(content=b"a" * (max_bytes + 1))

    client = APIClient()
    client.force_login(user)
    response = client.get(f"/api/v1.0/items/{item.id}/text/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["truncated"] is True
    assert payload["size"] == max_bytes + 1
    assert len(payload["content"].encode("utf-8")) == max_bytes
    assert payload["etag"] == response.headers["ETag"]


def test_api_items_text_put_ok_and_updates_etag():
    """Saving requires If-Match and updates storage content."""
    item, user = _create_text_item(content=b"hello")

    client = APIClient()
    client.force_login(user)
    get_resp = client.get(f"/api/v1.0/items/{item.id}/text/")
    etag = get_resp.headers.get("ETag")
    assert etag

    put_resp = client.put(
        f"/api/v1.0/items/{item.id}/text/",
        data={"content": "updated"},
        format="json",
        HTTP_IF_MATCH=etag,
    )
    assert put_resp.status_code == 200
    assert put_resp.headers.get("ETag")

    get_resp2 = client.get(f"/api/v1.0/items/{item.id}/text/")
    assert get_resp2.json()["content"] == "updated"


def test_api_items_text_put_etag_mismatch_returns_412():
    """If-Match mismatch must return 412 to prevent lost updates."""
    item, user = _create_text_item(content=b"hello")

    client = APIClient()
    client.force_login(user)
    get_resp = client.get(f"/api/v1.0/items/{item.id}/text/")
    etag = get_resp.headers.get("ETag")
    assert etag

    # External change
    default_storage.connection.meta.client.put_object(
        Bucket=default_storage.bucket_name,
        Key=item.file_key,
        Body=b"external",
        ContentType="text/plain",
    )

    put_resp = client.put(
        f"/api/v1.0/items/{item.id}/text/",
        data={"content": "updated"},
        format="json",
        HTTP_IF_MATCH=etag,
    )
    assert put_resp.status_code == 412
    data = put_resp.json()
    assert data["errors"][0]["code"] in {
        "item.text.changed",
        "precondition_failed",
    }


def test_api_items_text_put_requires_update_permission():
    """Users without update ability must not be able to save."""
    folder = factories.ItemFactory(type=models.ItemTypeChoices.FOLDER)
    item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="note.txt",
        mimetype="text/plain",
        update_upload_state=models.ItemUploadStateChoices.READY,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.READER,
    )
    user = factories.UserFactory()
    factories.UserItemAccessFactory(
        item=item, user=user, role=models.RoleChoices.READER
    )

    default_storage.save(item.file_key, BytesIO(b"hello"))

    client = APIClient()
    client.force_login(user)
    get_resp = client.get(f"/api/v1.0/items/{item.id}/text/")
    etag = get_resp.headers.get("ETag") or '"missing"'

    put_resp = client.put(
        f"/api/v1.0/items/{item.id}/text/",
        data={"content": "updated"},
        format="json",
        HTTP_IF_MATCH=etag,
    )
    assert put_resp.status_code == 403


def test_api_items_text_put_large_file_refused():
    """Large files are read-only in the text editor endpoint."""
    max_bytes = 500 * 1024
    item, user = _create_text_item(content=b"a" * (max_bytes + 1))

    client = APIClient()
    client.force_login(user)
    get_resp = client.get(f"/api/v1.0/items/{item.id}/text/")
    etag = get_resp.headers.get("ETag")
    assert etag

    put_resp = client.put(
        f"/api/v1.0/items/{item.id}/text/",
        data={"content": "small"},
        format="json",
        HTTP_IF_MATCH=etag,
    )
    assert put_resp.status_code == 400
    assert put_resp.json()["errors"][0]["code"] == "item.text.too_large_to_edit"
