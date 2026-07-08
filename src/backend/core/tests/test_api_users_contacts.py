"""Tests for the users contacts endpoint."""

import pytest
from rest_framework.test import APIClient

from core import factories, models

pytestmark = pytest.mark.django_db


def test_api_users_contacts_anonymous():
    """Anonymous users should not list contacts."""

    response = APIClient().get("/api/v1.0/users/contacts/")

    assert response.status_code == 401


def test_api_users_contacts_returns_visible_sharing_contacts():
    """Contacts are limited to users involved in items visible to the caller."""

    user = factories.UserFactory()
    contact = factories.UserFactory(full_name="Visible Contact")
    other_contact = factories.UserFactory(full_name="Other Contact")
    private_contact = factories.UserFactory(full_name="Private Contact")
    deleted_contact = factories.UserFactory(full_name="Deleted Contact")
    client = APIClient()
    client.force_login(user)

    shared_with_contact = factories.ItemFactory(
        users=[user],
        creator=user,
        type=models.ItemTypeChoices.FOLDER,
    )
    factories.UserItemAccessFactory(item=shared_with_contact, user=contact)
    factories.ItemFactory(
        users=[user],
        creator=contact,
        type=models.ItemTypeChoices.FOLDER,
    )
    factories.ItemFactory(
        users=[user],
        creator=other_contact,
        type=models.ItemTypeChoices.FOLDER,
    )
    factories.ItemFactory(
        users=[private_contact],
        creator=private_contact,
        type=models.ItemTypeChoices.FOLDER,
    )
    deleted_item = factories.ItemFactory(
        users=[user],
        creator=deleted_contact,
        type=models.ItemTypeChoices.FOLDER,
    )
    deleted_item.soft_delete()

    response = client.get("/api/v1.0/users/contacts/")

    assert response.status_code == 200
    payload = response.json()
    assert [contact["id"] for contact in payload] == [str(contact.id), str(other_contact.id)]
    assert all(set(contact) == {"id", "full_name", "short_name"} for contact in payload)


def test_api_users_contacts_search_by_email():
    """Contacts can be narrowed by email without exposing email in the response."""

    user = factories.UserFactory()
    contact = factories.UserFactory(email="filter-target@example.test")
    other_contact = factories.UserFactory(email="other-contact@example.test")
    client = APIClient()
    client.force_login(user)

    factories.ItemFactory(users=[user], creator=contact, type=models.ItemTypeChoices.FOLDER)
    factories.ItemFactory(users=[user], creator=other_contact, type=models.ItemTypeChoices.FOLDER)

    response = client.get("/api/v1.0/users/contacts/?q=filter-target@example.test")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(contact.id),
            "full_name": contact.full_name,
            "short_name": contact.short_name,
        }
    ]
