"""Direct contract tests for core admin registrations and callbacks."""
# pylint: disable=protected-access

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from django.contrib import admin as django_admin

from core import admin as core_admin
from core import models


def test_core_admin_registers_expected_models():
    """The main admin models stay registered with their expected admin classes."""

    assert isinstance(django_admin.site._registry[models.User], core_admin.UserAdmin)
    assert isinstance(django_admin.site._registry[models.Item], core_admin.ItemAdmin)
    assert isinstance(
        django_admin.site._registry[models.Invitation],
        core_admin.InvitationAdmin,
    )
    assert isinstance(
        django_admin.site._registry[models.MirrorItemTask],
        core_admin.MirrorItemTaskAdmin,
    )


def test_item_admin_trigger_file_analysis_only_schedules_files(monkeypatch):
    """The admin action only re-triggers analysis for file items."""

    analyse_file = Mock()
    monkeypatch.setattr(core_admin.malware_detection, "analyse_file", analyse_file)
    item_admin = core_admin.ItemAdmin(models.Item, django_admin.site)
    item_admin.message_user = Mock()

    file_item = SimpleNamespace(
        type=models.ItemTypeChoices.FILE,
        file_key="item/file-key",
        id="file-id",
    )
    folder_item = SimpleNamespace(
        type=models.ItemTypeChoices.FOLDER,
        file_key="item/folder-key",
        id="folder-id",
    )

    item_admin.trigger_file_analysis(request=Mock(), queryset=[file_item, folder_item])

    analyse_file.assert_called_once_with("item/file-key", item_id="file-id")
    item_admin.message_user.assert_called_once()


def test_invitation_admin_save_model_sets_issuer_from_request_user():
    """Saving an invitation through the admin stamps the request user as issuer."""

    invitation_admin = core_admin.InvitationAdmin(models.Invitation, django_admin.site)
    invitation = SimpleNamespace(issuer=None, save=Mock())
    request = SimpleNamespace(user="issuer-user")

    invitation_admin.save_model(request=request, obj=invitation, form=Mock(), change=False)

    assert invitation.issuer == "issuer-user"
    invitation.save.assert_called_once_with()
