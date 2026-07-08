"""
Test Entitlements API endpoints.
"""

from unittest import mock

import pytest
from rest_framework.test import APIClient

from core import factories
from core.entitlements import get_entitlements_backend, normalize_entitlement_decision

pytestmark = pytest.mark.django_db


def test_normalize_entitlement_decision_uses_message_as_public_message():
    """Legacy static backend message values should become the public denial message."""
    decision = normalize_entitlement_decision(
        {"result": False, "message": "Upload denied for testing"}
    )

    assert decision.allowed is False
    assert decision.public_message == "Upload denied for testing"
    assert decision.public_message_or("fallback") == "Upload denied for testing"
    assert decision.to_public_dict() == {
        "result": False,
        "message": "Upload denied for testing",
    }


def test_normalize_entitlement_decision_uses_reason_as_public_message():
    """DeployCenter reason values should be available to enforcement callers."""
    decision = normalize_entitlement_decision({"result": False, "reason": "not_activated"})

    assert decision.allowed is False
    assert decision.public_message == "not_activated"
    assert decision.reason == "not_activated"
    assert decision.public_message_or("fallback") == "not_activated"
    assert decision.to_public_dict() == {"result": False, "reason": "not_activated"}


@pytest.mark.parametrize(
    "provider_value",
    [
        None,
        object(),
        {"result": "true", "message": "ignored"},
    ],
)
def test_normalize_entitlement_decision_fails_closed(provider_value):
    """Malformed provider responses must not grant access."""
    decision = normalize_entitlement_decision(provider_value)

    assert decision.allowed is False


def test_api_entitlements_get_entitlements_anonymous():
    """Anonymous users should not be allowed to get entitlements."""
    client = APIClient()
    response = client.get("/api/v1.0/entitlements/")
    assert response.status_code == 401
    assert response.json() == {
        "errors": [
            {
                "attr": None,
                "code": "not_authenticated",
                "detail": "Authentication credentials were not provided.",
            },
        ],
        "type": "client_error",
    }


def test_api_entitlements_get_entitlements_authenticated():
    """Authenticated users should be allowed to get entitlements."""
    client = APIClient()
    user = factories.UserFactory()
    client.force_authenticate(user)
    response = client.get("/api/v1.0/entitlements/")
    assert response.status_code == 200
    assert response.json() == {
        "can_access": {
            "result": True,
        },
        "can_upload": {
            "result": True,
        },
        "context": {},
    }


def test_api_entitlements_static_backend_reads_from_parameters(settings):
    """StaticEntitlementsBackend should return values from ENTITLEMENTS_BACKEND_PARAMETERS."""
    settings.ENTITLEMENTS_BACKEND_PARAMETERS = {
        "entitlements": {
            "can_access": {"result": False, "message": "Access denied for testing"},
            "can_upload": {"result": False, "message": "Upload denied for testing"},
        },
    }
    get_entitlements_backend.cache_clear()

    client = APIClient()
    user = factories.UserFactory()
    client.force_authenticate(user)
    response = client.get("/api/v1.0/entitlements/")

    assert response.status_code == 200
    assert response.json() == {
        "can_access": {"result": False, "message": "Access denied for testing"},
        "can_upload": {"result": False, "message": "Upload denied for testing"},
        "context": {},
    }


def test_api_entitlements_get_entitlements_entitlements_backend_returns_falsy():
    """Authenticated users should be allowed to get entitlements with a custom message."""

    real_backend = get_entitlements_backend()
    real_backend.can_access = mock.Mock(
        return_value={"result": False, "message": "You do not have access to the app"}
    )

    with mock.patch("core.api.viewsets.get_entitlements_backend", return_value=real_backend):
        client = APIClient()
        user = factories.UserFactory()
        client.force_authenticate(user)
        response = client.get("/api/v1.0/entitlements/")
        assert response.status_code == 200
        assert response.json() == {
            "can_access": {
                "result": False,
                "message": "You do not have access to the app",
            },
            "can_upload": {
                "result": True,
            },
            "context": {},
        }
