"""Test the PUT file content viewset."""

from django.http import HttpRequest
from django.core.files.storage import default_storage

import pytest
from rest_framework.test import APIClient
from rest_framework.parsers import BaseParser

from core import factories, models
from wopi.services.access import AccessUserItemService
from wopi.services.lock import LockService

pytestmark = pytest.mark.django_db


def _setup_wopi_putfile_item(*, size: int = 0, filename: str = "wopi_test.txt"):
    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
    )
    item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename=filename,
        update_upload_state=models.ItemUploadStateChoices.READY,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
        size=size,
    )
    user = factories.UserFactory()
    factories.UserItemAccessFactory(
        item=item, user=user, role=models.RoleChoices.EDITOR
    )

    service = AccessUserItemService()
    access_token, _ = service.insert_new_access(item, user)

    lock_service = LockService(item)
    lock_service.lock("1234567890")

    return item, access_token


def test_put_file_content_connected_user_with_access():
    """User having access to the item can put file content."""
    item, access_token = _setup_wopi_putfile_item(size=0)

    client = APIClient()
    assert item.size == 0
    updated_at = item.updated_at
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"new content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
            "X-WOPI-Lock": "1234567890",
        },
    )
    assert response.status_code == 200
    assert "X-WOPI-ItemVersion" in response.headers

    # Verify the content was actually updated
    s3_client = default_storage.connection.meta.client
    file = s3_client.get_object(
        Bucket=default_storage.bucket_name,
        Key=item.file_key,
    )
    assert file["Body"].read() == b"new content"
    assert response.headers.get("X-WOPI-ItemVersion") == file["VersionId"]
    item.refresh_from_db()
    assert item.size == 11  # the size should have been updated
    assert item.updated_at > updated_at


def test_put_file_content_does_not_access_request_body(monkeypatch):
    """PutFile must stream the request content without buffering Request.body."""

    def _raise_on_body(_self):
        raise AssertionError("request.body must not be accessed")

    monkeypatch.setattr(HttpRequest, "body", property(_raise_on_body))

    item, access_token = _setup_wopi_putfile_item(size=0)

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"new content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
            "X-WOPI-Lock": "1234567890",
        },
    )
    assert response.status_code == 200


def test_put_file_content_does_not_trigger_drf_parsing(monkeypatch):
    """PutFile must not invoke DRF parsers (no request.data/request.POST parsing)."""

    import wopi.viewsets as wopi_viewsets

    class ExplodingParser(BaseParser):
        media_type = "*/*"

        def parse(self, *args, **kwargs):  # noqa: ARG002
            raise AssertionError("DRF parser must not be invoked for PutFile")

    # PutFile must not access request.data; if it does, DRF will select a parser
    # and call its parse(). We inject a parser that explodes to ensure parsing
    # is never triggered, without relying on private DRF internals.
    monkeypatch.setattr(
        wopi_viewsets.WopiViewSet,
        "parser_classes",
        [ExplodingParser],
        raising=True,
    )

    item, access_token = _setup_wopi_putfile_item(size=0)

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"new content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
            "X-WOPI-Lock": "1234567890",
        },
    )
    assert response.status_code == 200


def test_put_file_content_does_not_preread_stream(monkeypatch):
    """PutFile must not read from the request stream before handing it to the streamer."""
    import wopi.viewsets as wopi_viewsets

    read_calls = 0
    original_read = HttpRequest.read

    def _counting_read(self, *args, **kwargs):
        nonlocal read_calls
        read_calls += 1
        return original_read(self, *args, **kwargs)

    monkeypatch.setattr(HttpRequest, "read", _counting_read, raising=True)

    original_streamer = wopi_viewsets.stream_to_s3_object

    def _assert_not_preread(**kwargs):
        assert read_calls == 0, "request stream was read before streaming started"
        return original_streamer(**kwargs)

    monkeypatch.setattr(wopi_viewsets, "stream_to_s3_object", _assert_not_preread)

    item, access_token = _setup_wopi_putfile_item(size=0)

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"new content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
            "X-WOPI-Lock": "1234567890",
        },
    )
    assert response.status_code == 200


def test_put_file_content_streams_in_multiple_chunks(monkeypatch):
    """PutFile should write in multiple chunks for sufficiently large payloads."""
    item, access_token = _setup_wopi_putfile_item(size=0)

    s3_client = default_storage.connection.meta.client
    upload_part_calls = 0
    original_upload_part = s3_client.upload_part

    def _counting_upload_part(*args, **kwargs):
        nonlocal upload_part_calls
        upload_part_calls += 1
        return original_upload_part(*args, **kwargs)

    monkeypatch.setattr(s3_client, "upload_part", _counting_upload_part, raising=True)

    big_payload = b"a" * (9 * 1024 * 1024)  # > 8MiB default chunk size
    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=big_payload,
        content_type="application/octet-stream",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
            "X-WOPI-Lock": "1234567890",
        },
    )
    assert response.status_code == 200
    assert upload_part_calls >= 2


def test_put_file_content_connected_user_with_access_delete_item_during_edition():
    """User should not be able to put file content if the item is deleted during the edition."""
    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
    )
    item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="wopi_test.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
    )
    user = factories.UserFactory()
    factories.UserItemAccessFactory(
        item=item, user=user, role=models.RoleChoices.EDITOR
    )

    service = AccessUserItemService()
    access_token, _ = service.insert_new_access(item, user)

    lock_service = LockService(item)
    lock_service.lock("1234567890")

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"new content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
            "X-WOPI-Lock": "1234567890",
        },
    )
    assert response.status_code == 200
    assert "X-WOPI-ItemVersion" in response.headers

    # Verify the content was actually updated
    s3_client = default_storage.connection.meta.client
    file = s3_client.get_object(
        Bucket=default_storage.bucket_name,
        Key=item.file_key,
    )
    assert file["Body"].read() == b"new content"
    assert response.headers.get("X-WOPI-ItemVersion") == file["VersionId"]

    item.soft_delete()

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"rejected content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
            "X-WOPI-Lock": "1234567890",
        },
    )
    assert response.status_code == 403

    # Verify the content was not updated
    s3_client = default_storage.connection.meta.client
    file = s3_client.get_object(
        Bucket=default_storage.bucket_name,
        Key=item.file_key,
    )
    assert (
        file["Body"].read() == b"new content"
    )  # the content should not have been updated


def test_put_file_content_connected_user_with_access_access_removed_during_edition():
    """
    User should not be able to put file content if the user loses access to the item during the
    edition.
    """
    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
    )
    item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="wopi_test.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
    )
    user = factories.UserFactory()
    access = factories.UserItemAccessFactory(
        item=item, user=user, role=models.RoleChoices.EDITOR
    )

    service = AccessUserItemService()
    access_token, _ = service.insert_new_access(item, user)

    lock_service = LockService(item)
    lock_service.lock("1234567890")

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"new content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
            "X-WOPI-Lock": "1234567890",
        },
    )
    assert response.status_code == 200
    assert "X-WOPI-ItemVersion" in response.headers

    # Verify the content was actually updated
    s3_client = default_storage.connection.meta.client
    file = s3_client.get_object(
        Bucket=default_storage.bucket_name,
        Key=item.file_key,
    )
    assert file["Body"].read() == b"new content"
    assert response.headers.get("X-WOPI-ItemVersion") == file["VersionId"]

    access.delete()

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"rejected content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
            "X-WOPI-Lock": "1234567890",
        },
    )
    assert response.status_code == 403

    # Verify the content was not updated
    s3_client = default_storage.connection.meta.client
    file = s3_client.get_object(
        Bucket=default_storage.bucket_name,
        Key=item.file_key,
    )
    assert (
        file["Body"].read() == b"new content"
    )  # the content should not have been updated


def test_put_file_content_connected_user_not_linked_to_item():
    """
    User trying to put file content of an item not linked to the access token should get a 403.
    """
    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
    )
    item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="wopi_test.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
    )
    user = factories.UserFactory()
    factories.UserItemAccessFactory(
        item=item, user=user, role=models.RoleChoices.EDITOR
    )

    other_item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="other_wopi_test.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
    )
    factories.UserItemAccessFactory(
        item=other_item, user=user, role=models.RoleChoices.EDITOR
    )

    service = AccessUserItemService()
    access_token, _ = service.insert_new_access(item, user)

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{other_item.id}/contents/",
        data=b"new content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
        },
    )
    assert response.status_code == 403


def test_put_file_content_without_override_header():
    """Request without X-WOPI-OVERRIDE header should return 404."""
    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
    )
    item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="wopi_test.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
    )
    user = factories.UserFactory()
    factories.UserItemAccessFactory(
        item=item, user=user, role=models.RoleChoices.EDITOR
    )

    service = AccessUserItemService()
    access_token, _ = service.insert_new_access(item, user)

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"new content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )
    assert response.status_code == 404


def test_put_file_content_with_invalid_lock():
    """User cannot put file content when providing an invalid lock."""
    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
    )
    item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="wopi_test.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
    )
    user = factories.UserFactory()
    factories.UserItemAccessFactory(
        item=item, user=user, role=models.RoleChoices.EDITOR
    )

    service = AccessUserItemService()
    access_token, _ = service.insert_new_access(item, user)

    lock_service = LockService(item)
    lock_service.lock("1234567890")

    client = APIClient()

    # try to put content with an invalid lock
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"new content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
            "X-WOPI-Lock": "invalid-lock",
        },
    )
    assert response.status_code == 409
    assert response.headers.get("X-WOPI-Lock") == "1234567890"


def test_put_file_content_with_no_lock_header_and_body_size_greater_than_0():
    """
    User cannot put file content when not providing a lock header and the body size
    is greater than 0.
    """
    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
    )
    item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="wopi_test.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
    )
    user = factories.UserFactory()
    factories.UserItemAccessFactory(
        item=item, user=user, role=models.RoleChoices.EDITOR
    )
    service = AccessUserItemService()
    access_token, _ = service.insert_new_access(item, user)

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"new content",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
        },
    )
    assert response.status_code == 409
    assert response.headers.get("X-WOPI-Lock") == ""


def test_put_file_content_with_no_lock_header_and_body_size_0():
    """User can put file content when not providing a lock header and the body size is 0."""
    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
    )
    item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="wopi_test.txt",
        update_upload_state=models.ItemUploadStateChoices.READY,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
    )
    user = factories.UserFactory()
    factories.UserItemAccessFactory(
        item=item, user=user, role=models.RoleChoices.EDITOR
    )
    service = AccessUserItemService()
    access_token, _ = service.insert_new_access(item, user)

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"",
        content_type="text/plain",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={
            "X-WOPI-Override": "PUT",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("X-WOPI-ItemVersion") is not None

    # Verify the content was actually updated
    s3_client = default_storage.connection.meta.client
    file = s3_client.get_object(
        Bucket=default_storage.bucket_name,
        Key=item.file_key,
    )
    assert file["Body"].read() == b""
    assert response.headers.get("X-WOPI-ItemVersion") == file["VersionId"]


def test_put_file_content_allows_lockless_body_when_creating_and_transitions_ready():
    """
    When the item is a 0-byte placeholder in CREATING state, the first PutFile may
    be sent without a lock header (create-new flow).
    """
    folder = factories.ItemFactory(type=models.ItemTypeChoices.FOLDER)
    item = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="new.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        update_upload_state=models.ItemUploadStateChoices.CREATING,
        link_reach=models.LinkReachChoices.RESTRICTED,
        link_role=models.LinkRoleChoices.EDITOR,
        size=0,
    )
    user = factories.UserFactory()
    factories.UserItemAccessFactory(
        item=item, user=user, role=models.RoleChoices.EDITOR
    )
    service = AccessUserItemService()
    access_token, _ = service.insert_new_access(item, user)

    client = APIClient()
    response = client.post(
        f"/api/v1.0/wopi/files/{item.id}/contents/",
        data=b"new content",
        content_type="application/octet-stream",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        headers={"X-WOPI-Override": "PUT"},
    )
    assert response.status_code == 200

    item.refresh_from_db()
    assert item.upload_state == models.ItemUploadStateChoices.READY
    assert item.size == len(b"new content")
