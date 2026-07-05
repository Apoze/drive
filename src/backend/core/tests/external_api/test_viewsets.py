"""Direct contract tests for resource-server viewset wrappers."""

from __future__ import annotations

from django.test import override_settings

from rest_framework.permissions import AND

from core.api.permissions import (
    InvitationPermission,
    IsSelf,
    ItemAccessPermission,
    ItemPermission,
)
from core.external_api.authentication import DriveResourceServerAuthentication
from core.external_api.permissions import ResourceServerClientPermission
from core.external_api.viewsets import (
    ResourceServerInvitationViewSet,
    ResourceServerItemAccessViewSet,
    ResourceServerItemViewSet,
    ResourceServerUserViewSet,
)


@override_settings(
    EXTERNAL_API={
        "items": {"enabled": True, "actions": ["list", "retrieve"]},
        "item_access": {"enabled": True, "actions": ["list"]},
        "item_invitation": {"enabled": True, "actions": ["create"]},
        "users": {"enabled": True, "actions": ["get_me"]},
    }
)
def test_resource_server_viewsets_derive_actions_from_settings():
    """Each wrapper viewset resolves its configured action allowlist from settings."""

    assert ResourceServerItemViewSet().resource_server_actions == ["list", "retrieve"]
    assert ResourceServerItemAccessViewSet().resource_server_actions == ["list"]
    assert ResourceServerInvitationViewSet().resource_server_actions == ["create"]
    assert ResourceServerUserViewSet().resource_server_actions == ["get_me"]


def test_resource_server_viewsets_wire_authentication_and_permissions():
    """The wrapper viewsets keep the resource-server auth/permission composition."""

    item_permission = ResourceServerItemViewSet.permission_classes[0]
    user_permission = ResourceServerUserViewSet.permission_classes[0]
    item_access_permission = ResourceServerItemAccessViewSet.permission_classes[0]
    invitation_permission = ResourceServerInvitationViewSet.permission_classes[0]

    assert ResourceServerItemViewSet.authentication_classes == [DriveResourceServerAuthentication]
    assert ResourceServerUserViewSet.authentication_classes == [DriveResourceServerAuthentication]
    assert ResourceServerItemAccessViewSet.authentication_classes == [
        DriveResourceServerAuthentication
    ]
    assert ResourceServerInvitationViewSet.authentication_classes == [
        DriveResourceServerAuthentication
    ]

    assert item_permission.operator_class is AND
    assert item_permission.op1_class is ResourceServerClientPermission
    assert item_permission.op2_class is ItemPermission

    assert user_permission.operator_class is AND
    assert user_permission.op1_class is ResourceServerClientPermission
    assert user_permission.op2_class is IsSelf

    assert item_access_permission.operator_class is AND
    assert item_access_permission.op1_class is ResourceServerClientPermission
    assert item_access_permission.op2_class is ItemAccessPermission

    assert invitation_permission.operator_class is AND
    assert invitation_permission.op1_class is ResourceServerClientPermission
    assert invitation_permission.op2_class is InvitationPermission
