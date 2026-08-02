"""Test the read-only item activity API."""

from django.core.exceptions import ValidationError

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from core import factories, models

pytestmark = pytest.mark.django_db


def _create_activity(item, *, actor=None, actor_name="Actor at event time", **kwargs):
    """Create one activity entry with safe defaults."""
    return models.ItemActivity.objects.create(
        item=item,
        actor=actor,
        actor_name=actor_name,
        action=models.ItemActivityActionChoices.CREATED,
        **kwargs,
    )


def test_api_item_activity_list_anonymous():
    """Anonymous visitors cannot read an item's activity."""
    item = factories.ItemFactory()

    response = APIClient().get(f"/api/v1.0/items/{item.id!s}/activity/")

    assert response.status_code == 401


def test_api_item_activity_list_is_empty_for_existing_items():
    """Items have no invented history before product actions create it."""
    user = factories.UserFactory()
    item = factories.ItemFactory(users=[(user, "owner")])
    client = APIClient()
    client.force_login(user)

    response = client.get(f"/api/v1.0/items/{item.id!s}/activity/")

    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert response.json()["results"] == []


@pytest.mark.parametrize("role", ["reader", "editor", None])
def test_api_item_activity_list_requires_activity_view(role):
    """Readers, editors, and unrelated users cannot read product activity."""
    user = factories.UserFactory()
    item = factories.ItemFactory(type=models.ItemTypeChoices.FOLDER)
    if role:
        factories.UserItemAccessFactory(item=item, user=user, role=role)
    _create_activity(item)

    assert item.get_abilities(user)["activity_view"] is False

    client = APIClient()
    client.force_login(user)
    response = client.get(f"/api/v1.0/items/{item.id!s}/activity/")

    assert response.status_code == 403


@pytest.mark.parametrize("role", ["owner", "administrator"])
def test_api_item_activity_list_privileged_is_direct_stable_and_paginated(role):
    """Owners and administrators get direct activity, newest first, 25 at a time."""
    user = factories.UserFactory()
    actor = factories.UserFactory()
    item = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, role)],
    )
    child = factories.ItemFactory(parent=item)
    other_item = factories.ItemFactory()
    activities = []
    for index in range(26):
        with freeze_time(f"2026-01-01 00:00:{index:02d}"):
            activities.append(
                _create_activity(
                    item,
                    actor=actor,
                    payload={"sequence": index},
                )
            )
    _create_activity(child, actor=actor)
    _create_activity(other_item, actor=actor)

    assert item.get_abilities(user)["activity_view"] is True

    client = APIClient()
    client.force_login(user)
    url = f"/api/v1.0/items/{item.id!s}/activity/"
    first_page = client.get(url)

    assert first_page.status_code == 200
    assert first_page.json()["count"] == 26
    assert len(first_page.json()["results"]) == 25
    assert [entry["id"] for entry in first_page.json()["results"]] == [
        str(activity.id) for activity in reversed(activities[1:])
    ]
    assert first_page.json()["results"][0] == {
        "id": str(activities[-1].id),
        "action": models.ItemActivityActionChoices.CREATED,
        "actor": str(actor.id),
        "actor_name": "Actor at event time",
        "payload": {"sequence": 25},
        "created_at": activities[-1].created_at.isoformat().replace("+00:00", "Z"),
    }

    second_page = client.get(f"{url}?page=2&page_size=100")
    assert second_page.status_code == 200
    assert [entry["id"] for entry in second_page.json()["results"]] == [str(activities[0].id)]


@pytest.mark.parametrize("role", ["owner", "administrator"])
def test_api_item_activity_list_available_in_trash(role):
    """Owners and administrators can still read activity while an item is trashed."""
    user = factories.UserFactory()
    item = factories.ItemFactory(users=[(user, role)])
    activity = _create_activity(item, actor=user)
    item.soft_delete()

    client = APIClient()
    client.force_login(user)
    response = client.get(f"/api/v1.0/items/{item.id!s}/activity/")

    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == str(activity.id)


def test_api_item_activity_list_uses_id_to_stabilize_equal_timestamps():
    """Equal timestamps are ordered by descending activity id."""
    user = factories.UserFactory()
    item = factories.ItemFactory(users=[(user, "owner")])
    with freeze_time("2026-01-01 00:00:00"):
        activities = [_create_activity(item), _create_activity(item)]

    client = APIClient()
    client.force_login(user)
    response = client.get(f"/api/v1.0/items/{item.id!s}/activity/")

    assert [entry["id"] for entry in response.json()["results"]] == sorted(
        (str(activity.id) for activity in activities), reverse=True
    )


def test_api_item_activity_list_keeps_actor_snapshot_after_actor_deletion():
    """Deleting an actor keeps the frozen display name readable."""
    user = factories.UserFactory()
    actor = factories.UserFactory()
    item = factories.ItemFactory(users=[(user, "owner")])
    activity = _create_activity(item, actor=actor)
    actor.delete()

    client = APIClient()
    client.force_login(user)
    response = client.get(f"/api/v1.0/items/{item.id!s}/activity/")

    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == str(activity.id)
    assert response.json()["results"][0]["actor"] is None
    assert response.json()["results"][0]["actor_name"] == "Actor at event time"


def test_api_item_activity_list_unknown_item():
    """An unknown nested item returns not found."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    response = client.get("/api/v1.0/items/00000000-0000-0000-0000-000000000000/activity/")

    assert response.status_code == 404


def test_api_item_activity_is_read_only():
    """No public activity-writing endpoint exists."""
    user = factories.UserFactory()
    item = factories.ItemFactory(users=[(user, "owner")])
    client = APIClient()
    client.force_login(user)

    response = client.post(
        f"/api/v1.0/items/{item.id!s}/activity/",
        data={"action": models.ItemActivityActionChoices.CREATED},
    )

    assert response.status_code == 405
    assert models.ItemActivity.objects.count() == 0


def test_models_item_activity_payload_must_be_an_object():
    """Internal writers cannot persist unstructured payloads."""
    item = factories.ItemFactory()

    with pytest.raises(ValidationError) as exc_info:
        _create_activity(item, payload=[])

    assert exc_info.value.error_dict["payload"][0].code == "item_activity_payload_not_object"


def test_models_item_activity_is_deleted_with_item():
    """Product activity follows the regular item's lifetime."""
    item = factories.ItemFactory()
    activity = _create_activity(item)

    item.soft_delete()
    item.delete()

    assert not models.ItemActivity.objects.filter(pk=activity.pk).exists()
