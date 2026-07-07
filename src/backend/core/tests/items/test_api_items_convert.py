"""Tests for the /items/<id>/convert/ endpoint."""

from unittest import mock

import pytest
from rest_framework.test import APIClient

from core import factories, models

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _disable_debug_toolbar(settings):
    # The dev docker-compose runs tests with the Development settings, which
    # enables the Django debug toolbar. Disable it for these API tests to avoid
    # staticfiles manifest lookups during response post-processing.
    settings.DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: False}


def _configure_conversion(settings):
    settings.WOPI_SRC_BASE_URL = "https://drive.example"
    settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET = "test-jwt-secret"
    settings.WOPI_CLIENTS_CONFIGURATION = {
        "onlyoffice": {
            "options": {
                "ForceConvertExtensions": ["doc"],
                "ConvertServiceUrl": "https://onlyoffice/converter",
            },
        }
    }


def _build_user_and_item():
    user = factories.UserFactory()
    parent = factories.ItemFactory(
        users=[(user, models.RoleChoices.EDITOR)],
        type=models.ItemTypeChoices.FOLDER,
    )
    item = factories.ItemFactory(
        parent=parent,
        users=[(user, models.RoleChoices.EDITOR)],
        type=models.ItemTypeChoices.FILE,
        filename="document.doc",
        mimetype="application/msword",
        update_upload_state=models.ItemUploadStateChoices.READY,
    )
    return user, item


def test_convert_endpoint_creates_placeholder_and_queues_task(settings):
    _configure_conversion(settings)
    user, item = _build_user_and_item()
    client = APIClient()
    client.force_login(user)

    with mock.patch("core.api.viewsets.convert_file.delay") as delay_mock:
        response = client.post(f"/api/v1.0/items/{item.id}/convert/")

    assert response.status_code == 201
    body = response.json()
    placeholder = models.Item.objects.get(id=body["id"])
    assert placeholder.upload_state == models.ItemUploadStateChoices.CONVERTING
    assert placeholder.filename == "document (converted).docx"
    assert placeholder.parent().id == item.parent().id
    delay_mock.assert_called_once_with(
        source_item_id=str(item.id),
        converted_item_id=str(placeholder.id),
        user_id=str(user.id),
    )


def test_convert_endpoint_is_hidden_until_conversion_is_fully_configured(settings):
    settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET = "test-jwt-secret"
    settings.WOPI_CLIENTS_CONFIGURATION = {
        "onlyoffice": {"options": {"ForceConvertExtensions": ["doc"]}}
    }
    user, item = _build_user_and_item()
    client = APIClient()
    client.force_login(user)

    with mock.patch("core.api.viewsets.convert_file.delay") as delay_mock:
        response = client.post(f"/api/v1.0/items/{item.id}/convert/")

    assert response.status_code == 403
    assert not models.Item.objects.filter(
        upload_state=models.ItemUploadStateChoices.CONVERTING
    ).exists()
    delay_mock.assert_not_called()


def test_convert_endpoint_returns_403_when_user_cannot_update_item(settings):
    _configure_conversion(settings)
    _user, item = _build_user_and_item()
    other_user = factories.UserFactory()
    client = APIClient()
    client.force_login(other_user)

    with mock.patch("core.api.viewsets.convert_file.delay") as delay_mock:
        response = client.post(f"/api/v1.0/items/{item.id}/convert/")

    assert response.status_code == 403
    assert not models.Item.objects.filter(
        upload_state=models.ItemUploadStateChoices.CONVERTING
    ).exists()
    delay_mock.assert_not_called()


def test_convert_endpoint_rejects_unsupported_extension(settings):
    _configure_conversion(settings)
    user = factories.UserFactory()
    item = factories.ItemFactory(
        users=[(user, models.RoleChoices.EDITOR)],
        type=models.ItemTypeChoices.FILE,
        filename="image.png",
        update_upload_state=models.ItemUploadStateChoices.READY,
    )
    client = APIClient()
    client.force_login(user)

    with mock.patch("core.api.viewsets.convert_file.delay") as delay_mock:
        response = client.post(f"/api/v1.0/items/{item.id}/convert/")

    assert response.status_code == 403
    delay_mock.assert_not_called()


def test_default_wopi_opening_is_preserved_without_conversion_config(settings):
    settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET = None
    settings.WOPI_CLIENTS_CONFIGURATION = {
        "onlyoffice": {"options": {}},
    }
    user = factories.UserFactory()
    item = factories.ItemFactory(
        users=[(user, models.RoleChoices.EDITOR)],
        type=models.ItemTypeChoices.FILE,
        filename="document.doc",
        mimetype="application/msword",
        update_upload_state=models.ItemUploadStateChoices.READY,
    )

    abilities = item.get_abilities(user)

    assert abilities["wopi"] is True
    assert abilities["convert"] is False
