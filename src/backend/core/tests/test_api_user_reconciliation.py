"""Tests for the ReconciliationConfirmView API view."""

import uuid

from django.conf import settings

import pytest
from rest_framework.test import APIClient

from core import factories, models

pytestmark = pytest.mark.django_db


def _create_reconciliation(active, inactive, **kwargs):
    """Create a reconciliation entry with email sending bypassed."""
    return models.UserReconciliation.objects.create(
        active_email=active.email,
        inactive_email=inactive.email,
        active_user=active,
        inactive_user=inactive,
        active_email_checked=kwargs.pop("active_email_checked", False),
        inactive_email_checked=kwargs.pop("inactive_email_checked", False),
        status="ready",
        **kwargs,
    )


def test_api_reconciliation_confirm_active():
    """Confirming the active link sets active_email_checked."""
    active = factories.UserFactory(email="active@example.com")
    inactive = factories.UserFactory(email="inactive@example.com")
    reconciliation = _create_reconciliation(active, inactive)

    url = (
        f"/api/{settings.API_VERSION}/user-reconciliations/active/"
        f"{reconciliation.active_email_confirmation_id}/"
    )
    response = APIClient().get(url)

    assert response.status_code == 200
    assert response.json() == {"detail": "Confirmation received"}

    reconciliation.refresh_from_db()
    assert reconciliation.active_email_checked is True
    assert reconciliation.inactive_email_checked is False
    assert reconciliation.status == "ready"
    active.refresh_from_db()
    inactive.refresh_from_db()
    assert active.is_active is True
    assert inactive.is_active is True


def test_api_reconciliation_confirm_inactive():
    """Confirming the inactive link sets inactive_email_checked."""
    active = factories.UserFactory(email="active@example.com")
    inactive = factories.UserFactory(email="inactive@example.com")
    reconciliation = _create_reconciliation(active, inactive)

    url = (
        f"/api/{settings.API_VERSION}/user-reconciliations/inactive/"
        f"{reconciliation.inactive_email_confirmation_id}/"
    )
    response = APIClient().get(url)

    assert response.status_code == 200
    assert response.json() == {"detail": "Confirmation received"}
    reconciliation.refresh_from_db()
    assert reconciliation.inactive_email_checked is True
    assert reconciliation.active_email_checked is False


def test_api_reconciliation_confirm_requires_both_links_and_admin_processing():
    """Public confirmations do not process accounts before the admin action."""
    active = factories.UserFactory(email="active@example.com")
    inactive = factories.UserFactory(email="inactive@example.com")
    reconciliation = _create_reconciliation(active, inactive)
    client = APIClient()

    client.get(
        f"/api/{settings.API_VERSION}/user-reconciliations/active/"
        f"{reconciliation.active_email_confirmation_id}/"
    )
    client.get(
        f"/api/{settings.API_VERSION}/user-reconciliations/inactive/"
        f"{reconciliation.inactive_email_confirmation_id}/"
    )

    reconciliation.refresh_from_db()
    active.refresh_from_db()
    inactive.refresh_from_db()
    assert reconciliation.active_email_checked is True
    assert reconciliation.inactive_email_checked is True
    assert reconciliation.status == "ready"
    assert active.is_active is True
    assert inactive.is_active is True


@pytest.mark.parametrize(
    "user_type, confirmation_id, expected_status",
    [
        ("other", uuid.uuid4(), 400),
        ("active", "not-a-uuid", 400),
        ("active", uuid.uuid4(), 404),
    ],
)
def test_api_reconciliation_confirm_invalid_link_is_generic(
    user_type,
    confirmation_id,
    expected_status,
):
    """Invalid public links return a generic response without account details."""
    active = factories.UserFactory(email="active@example.com")
    inactive = factories.UserFactory(email="inactive@example.com")
    _create_reconciliation(active, inactive)

    url = f"/api/{settings.API_VERSION}/user-reconciliations/{user_type}/{confirmation_id}/"
    response = APIClient().get(url)

    assert response.status_code == expected_status
    assert response.json() == {"detail": "Invalid confirmation link"}
    assert active.email not in response.content.decode()
    assert inactive.email not in response.content.decode()
