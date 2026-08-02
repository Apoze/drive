"""Integration tests for item lifecycle activity writes."""

from django.core.exceptions import ValidationError

import pytest
from rest_framework.test import APIClient

from core import factories, models
from core.services.item_activity import record_item_activity

pytestmark = pytest.mark.django_db


def _owner_client():
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)
    return user, client


def _activity(client, item):
    response = client.get(f"/api/v1.0/items/{item.id!s}/activity/")
    assert response.status_code == 200
    return response.json()["results"]


def test_api_item_activity_records_root_and_child_folder_creation():
    """Both item creation paths emit a created event for usable folders."""
    user, client = _owner_client()

    root_response = client.post(
        "/api/v1.0/items/",
        {"title": "Root", "type": models.ItemTypeChoices.FOLDER},
        format="json",
    )
    assert root_response.status_code == 201
    root = models.Item.objects.get(pk=root_response.json()["id"])
    child_response = client.post(
        f"/api/v1.0/items/{root.id!s}/children/",
        {"title": "Child", "type": models.ItemTypeChoices.FOLDER},
        format="json",
    )
    assert child_response.status_code == 201
    child = models.Item.objects.get(pk=child_response.json()["id"])

    for item in (root, child):
        entries = _activity(client, item)
        assert len(entries) == 1
        assert entries[0]["action"] == models.ItemActivityActionChoices.CREATED
        assert entries[0]["actor"] == str(user.id)
        assert entries[0]["actor_name"] == user.full_name
        assert entries[0]["payload"] == {}


def test_api_item_activity_does_not_record_pending_file_creation():
    """An upload placeholder is not presented as a created file."""
    _user, client = _owner_client()

    response = client.post(
        "/api/v1.0/items/",
        {
            "title": "Pending",
            "type": models.ItemTypeChoices.FILE,
            "filename": "pending.txt",
        },
        format="json",
    )
    item = models.Item.objects.get(pk=response.json()["id"])

    assert response.status_code == 201
    assert item.upload_state == models.ItemUploadStateChoices.PENDING
    assert _activity(client, item) == []


def test_api_item_activity_records_rename_and_description_without_description_content():
    """A successful update records distinct safe events."""
    user, client = _owner_client()
    item = factories.ItemFactory(
        title="Old name",
        description="Old description",
        users=[(user, models.RoleChoices.OWNER)],
    )

    response = client.patch(
        f"/api/v1.0/items/{item.id!s}/",
        {"title": "New name", "description": "New description"},
        format="json",
    )

    assert response.status_code == 200
    entries = {entry["action"]: entry for entry in _activity(client, item)}
    assert entries[models.ItemActivityActionChoices.RENAMED]["payload"] == {
        "old_name": "Old name",
        "new_name": "New name",
    }
    assert entries[models.ItemActivityActionChoices.DESCRIPTION_UPDATED]["payload"] == {}
    payloads = [entry["payload"] for entry in entries.values()]
    assert "Old description" not in str(payloads)
    assert "New description" not in str(payloads)


def test_api_item_activity_records_public_link_visitor_without_user_identity():
    """An anonymous editor is represented without a fabricated user."""
    owner, owner_client = _owner_client()
    item = factories.ItemFactory(
        title="Old name",
        link_reach=models.LinkReachChoices.PUBLIC,
        link_role=models.LinkRoleChoices.EDITOR,
        users=[(owner, models.RoleChoices.OWNER)],
    )

    response = APIClient().patch(
        f"/api/v1.0/items/{item.id!s}/",
        {"title": "New name"},
        format="json",
    )

    assert response.status_code == 200
    entry = _activity(owner_client, item)[0]
    assert entry["actor"] is None
    assert entry["actor_name"] == "Visitor via link"


def test_api_item_activity_records_move_with_parent_references():
    """A successful move keeps small old and new parent references."""
    user, client = _owner_client()
    old_parent = factories.ItemFactory(
        title="Old parent",
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, models.RoleChoices.OWNER)],
    )
    new_parent = factories.ItemFactory(
        title="New parent",
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, models.RoleChoices.OWNER)],
    )
    item = factories.ItemFactory(parent=old_parent)

    response = client.post(
        f"/api/v1.0/items/{item.id!s}/move/",
        {"target_item_id": str(new_parent.id)},
        format="json",
    )

    assert response.status_code == 200
    activity = models.ItemActivity.objects.get(item=item)
    assert _activity(client, item)[0] == {
        "id": str(activity.id),
        "action": models.ItemActivityActionChoices.MOVED,
        "actor": str(user.id),
        "actor_name": user.full_name,
        "payload": {
            "old_parent_id": str(old_parent.id),
            "old_parent_name": "Old parent",
            "new_parent_id": str(new_parent.id),
            "new_parent_name": "New parent",
        },
        "created_at": activity.created_at.isoformat().replace("+00:00", "Z"),
    }


def test_api_item_activity_records_trash_and_restore():
    """Trash and restore remain visible through the same privileged endpoint."""
    user, client = _owner_client()
    item = factories.ItemFactory(users=[(user, models.RoleChoices.OWNER)])

    delete_response = client.delete(f"/api/v1.0/items/{item.id!s}/")
    restore_response = client.post(f"/api/v1.0/items/{item.id!s}/restore/")

    assert delete_response.status_code == 204
    assert restore_response.status_code == 200
    assert [entry["action"] for entry in _activity(client, item)] == [
        models.ItemActivityActionChoices.RESTORED,
        models.ItemActivityActionChoices.TRASHED,
    ]


def test_item_activity_writer_rejects_unexpected_payload_fields():
    """Internal writers cannot add fields outside the action schema."""
    user = factories.UserFactory()
    item = factories.ItemFactory()

    with pytest.raises(ValidationError) as exc_info:
        record_item_activity(
            item=item,
            actor=user,
            action=models.ItemActivityActionChoices.RENAMED,
            payload={
                "old_name": "Old",
                "new_name": "New",
                "unexpected": "value",
            },
        )

    assert exc_info.value.code == "item_activity_payload_invalid"
    assert not models.ItemActivity.objects.exists()
