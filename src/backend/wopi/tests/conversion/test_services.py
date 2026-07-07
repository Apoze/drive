"""Tests for the legacy conversion service layer."""

from unittest import mock

from django.core.files.base import ContentFile
from django.db import DatabaseError

import pytest

from core import factories, models
from wopi.conversion import exceptions, services
from wopi.conversion.backends.onlyoffice import OnlyOfficeConversionBackend

pytestmark = pytest.mark.django_db


class FakeBackend:
    """Conversion backend returning fixed converted content."""

    def convert(self, _item, _source_url, target_extension):
        """Return fake converted content."""
        return ContentFile(b"converted", name=f"converted.{target_extension}")


@pytest.fixture(autouse=True)
def _fake_backend(request):
    """Use a fake backend except in tests that exercise backend resolution."""
    if request.node.name.startswith("test_resolve_backend"):
        yield
        return

    with mock.patch.object(services, "resolve_backend", return_value=FakeBackend()):
        yield


def _configure_conversion(settings, *, options=None):
    """Configure legacy conversion for .doc files."""
    settings.WOPI_SRC_BASE_URL = "https://drive.example"
    settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET = "test-jwt-secret"
    settings.WOPI_CLIENTS_CONFIGURATION = {
        "onlyoffice": {
            "options": options
            or {
                "ForceConvertExtensions": ["doc"],
                "ConvertServiceUrl": "https://onlyoffice/converter",
            },
        },
    }


def _file(user, **kwargs):
    """Build a file the user can update; kwargs override defaults."""
    defaults = {
        "users": [(user, models.RoleChoices.EDITOR)],
        "type": models.ItemTypeChoices.FILE,
        "filename": "document.doc",
        "mimetype": "application/msword",
        "update_upload_state": models.ItemUploadStateChoices.READY,
    }
    defaults.update(kwargs)
    return factories.ItemFactory(**defaults)


def test_prepare_conversion_returns_placeholder_in_converting_state(settings):
    _configure_conversion(settings)
    user = factories.UserFactory()
    parent = factories.ItemFactory(
        users=[(user, models.RoleChoices.EDITOR)],
        type=models.ItemTypeChoices.FOLDER,
    )
    item = _file(user, parent=parent)

    placeholder = services.prepare_conversion(item, user)

    assert placeholder.filename == "document (converted).docx"
    assert placeholder.title == "document (converted).docx"
    assert placeholder.parent().id == parent.id
    assert placeholder.upload_state == models.ItemUploadStateChoices.CONVERTING


def test_prepare_conversion_accepts_analyzing_source(settings):
    _configure_conversion(settings)
    user = factories.UserFactory()
    item = _file(user, update_upload_state=models.ItemUploadStateChoices.ANALYZING)

    placeholder = services.prepare_conversion(item, user)

    assert placeholder.upload_state == models.ItemUploadStateChoices.CONVERTING


def test_prepare_conversion_rejects_missing_jwt_secret_before_placeholder(settings):
    _configure_conversion(settings)
    settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET = None
    user = factories.UserFactory()
    item = _file(user)

    with pytest.raises(
        exceptions.ConversionMisconfigured,
        match="Missing WOPI_ONLYOFFICE_CONVERT_JWT_SECRET",
    ):
        services.prepare_conversion(item, user)

    assert not models.Item.objects.filter(
        upload_state=models.ItemUploadStateChoices.CONVERTING
    ).exists()


def test_prepare_conversion_rejects_missing_convert_service_before_placeholder(settings):
    _configure_conversion(settings, options={"ForceConvertExtensions": ["doc"]})
    user = factories.UserFactory()
    item = _file(user)

    with pytest.raises(
        exceptions.ConversionMisconfigured,
        match="Missing OnlyOffice ConvertServiceUrl",
    ):
        services.prepare_conversion(item, user)

    assert not models.Item.objects.filter(
        upload_state=models.ItemUploadStateChoices.CONVERTING
    ).exists()


def test_perform_conversion_saves_regular_storage_and_marks_ready(settings):
    _configure_conversion(settings)
    user = factories.UserFactory()
    source = _file(user)
    placeholder = factories.ItemFactory(
        users=[(user, models.RoleChoices.EDITOR)],
        type=models.ItemTypeChoices.FILE,
        filename="document (converted).docx",
        update_upload_state=models.ItemUploadStateChoices.CONVERTING,
    )

    with (
        mock.patch.object(services, "build_source_url", return_value="https://source"),
        mock.patch.object(services.default_storage, "save") as save_mock,
    ):
        converted = services.perform_conversion(source, placeholder, user)

    save_mock.assert_called_once()
    assert save_mock.call_args.args[0] == placeholder.file_key
    converted.refresh_from_db()
    assert converted.upload_state == models.ItemUploadStateChoices.READY
    assert converted.size == len(b"converted")


def test_perform_conversion_deletes_saved_file_and_closes_stream_on_db_error(settings):
    _configure_conversion(settings)
    user = factories.UserFactory()
    source = _file(user)
    placeholder = factories.ItemFactory(
        users=[(user, models.RoleChoices.EDITOR)],
        type=models.ItemTypeChoices.FILE,
        filename="document (converted).docx",
        update_upload_state=models.ItemUploadStateChoices.CONVERTING,
    )
    converted_file = mock.Mock(size=9)
    converted_file.read.return_value = b"converted"

    with (
        mock.patch.object(services, "build_source_url", return_value="https://source"),
        mock.patch.object(FakeBackend, "convert", return_value=converted_file),
        mock.patch.object(services.default_storage, "save") as save_mock,
        mock.patch.object(services.default_storage, "delete") as delete_mock,
        mock.patch.object(placeholder, "save", side_effect=DatabaseError("db down")),
    ):
        with pytest.raises(DatabaseError):
            services.perform_conversion(source, placeholder, user)

    save_mock.assert_called_once()
    delete_mock.assert_called_once_with(placeholder.file_key)
    converted_file.close.assert_called_once()


def test_resolve_backend_raises_when_onlyoffice_url_is_missing():
    with pytest.raises(
        exceptions.ConversionMisconfigured,
        match="Missing OnlyOffice ConvertServiceUrl",
    ):
        services.resolve_backend({})


def test_resolve_backend_uses_onlyoffice_convert_url():
    backend = services.resolve_backend({"ConvertServiceUrl": "https://onlyoffice/converter"})

    assert isinstance(backend, OnlyOfficeConversionBackend)
    assert backend.convert_service_url == "https://onlyoffice/converter"
