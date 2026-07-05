"""Direct contract tests for DRF permission helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from django.core import exceptions
from django.http import Http404
from django.utils import timezone

import pytest

from core.api.permissions import (
    CreateWithPriviliegedRolesMixin,
    InvitationPermission,
    IsAuthenticated,
    IsAuthenticatedOrSafe,
    IsOwnedOrPublic,
    IsSelf,
    ItemAccessPermission,
    ItemPermission,
)
from core.models import RoleChoices


class _User:
    def __init__(self, *, is_authenticated):
        self.is_authenticated = is_authenticated


def _request(*, method="GET", auth=None, user=None, data=None):
    if user is None:
        user = _User(is_authenticated=False)
    return SimpleNamespace(method=method, auth=auth, user=user, data=data or {})


def test_is_authenticated_accepts_auth_token_or_authenticated_user():
    permission = IsAuthenticated()

    assert permission.has_permission(_request(auth="token"), None) is True
    assert (
        permission.has_permission(
            _request(user=_User(is_authenticated=True)),
            None,
        )
        is True
    )
    assert permission.has_permission(_request(), None) is False


def test_is_authenticated_or_safe_allows_safe_methods_for_anonymous_only():
    permission = IsAuthenticatedOrSafe()

    assert permission.has_permission(_request(method="GET"), None) is True
    assert permission.has_permission(_request(method="HEAD"), None) is True
    assert permission.has_permission(_request(method="POST"), None) is False


def test_is_self_only_allows_object_permission_for_current_user():
    user = _User(is_authenticated=True)
    permission = IsSelf()

    assert permission.has_object_permission(_request(user=user), None, user) is True
    assert (
        permission.has_object_permission(
            _request(user=user),
            None,
            _User(is_authenticated=True),
        )
        is False
    )


def test_is_owned_or_public_handles_owner_public_safe_and_related_user_fallback():
    user = _User(is_authenticated=True)
    other = _User(is_authenticated=True)
    permission = IsOwnedOrPublic()

    owned = SimpleNamespace(owner=user, user=other)
    public_object = SimpleNamespace(owner=None, user=other)
    related = SimpleNamespace(owner=other, user=user)

    assert (
        permission.has_object_permission(_request(user=user, method="PATCH"), None, owned) is True
    )
    assert (
        permission.has_object_permission(_request(user=user, method="GET"), None, public_object)
        is True
    )
    assert (
        permission.has_object_permission(_request(user=user, method="PATCH"), None, related) is True
    )


def test_is_owned_or_public_returns_false_when_related_user_lookup_fails():
    user = _User(is_authenticated=True)
    permission = IsOwnedOrPublic()

    class _BrokenObject:
        owner = _User(is_authenticated=True)

        @property
        def user(self):
            raise exceptions.ObjectDoesNotExist

    assert (
        permission.has_object_permission(_request(user=user, method="PATCH"), None, _BrokenObject())
        is False
    )


def test_create_with_privilieged_roles_mixin_requires_privileged_role_on_create(monkeypatch):
    monkeypatch.setattr("core.api.permissions.PRIVILEGED_ROLES", {RoleChoices.ADMIN})

    class DummyPermission(CreateWithPriviliegedRolesMixin, IsAuthenticated):
        resources = "widgets"

    permission = DummyPermission()
    user = _User(is_authenticated=True)

    allowed_view = SimpleNamespace(
        action="create",
        resource_field_name="resource",
        resource=SimpleNamespace(get_role=lambda _user: RoleChoices.ADMIN),
    )
    forbidden_view = SimpleNamespace(
        action="create",
        resource_field_name="resource",
        resource=SimpleNamespace(get_role=lambda _user: RoleChoices.READER),
    )
    read_view = SimpleNamespace(action="list", resource_field_name="resource", resource=None)

    assert permission.has_permission(_request(user=user), allowed_view) is True
    with pytest.raises(exceptions.PermissionDenied, match="manage widgets"):
        permission.has_permission(_request(user=user), forbidden_view)
    assert permission.has_permission(_request(user=user), read_view) is True


def test_invitation_permission_uses_object_abilities_for_action():
    permission = InvitationPermission()
    request = _request(user=_User(is_authenticated=True))
    view = SimpleNamespace(action="retrieve")
    obj = SimpleNamespace(get_abilities=lambda _user: {"retrieve": True, "destroy": False})

    assert permission.has_object_permission(request, view, obj) is True
    view.action = "destroy"
    assert permission.has_object_permission(request, view, obj) is False


def test_item_access_permission_checks_requested_role_against_set_role_to():
    permission = ItemAccessPermission()
    request = _request(
        user=_User(is_authenticated=True),
        data={"role": RoleChoices.ADMIN},
    )
    view = SimpleNamespace(action="update")
    obj = SimpleNamespace(
        get_abilities=lambda _user: {
            "update": True,
            "set_role_to": [RoleChoices.READER, RoleChoices.EDITOR],
        }
    )

    assert permission.has_object_permission(request, view, obj) is False

    request.data["role"] = RoleChoices.EDITOR
    assert permission.has_object_permission(request, view, obj) is True


def test_item_permission_has_permission_covers_auth_specific_actions():
    permission = ItemPermission()
    anonymous = _User(is_authenticated=False)
    authenticated = _User(is_authenticated=True)

    assert (
        permission.has_permission(_request(user=authenticated), SimpleNamespace(action="list"))
        is True
    )
    assert (
        permission.has_permission(_request(user=anonymous), SimpleNamespace(action="list")) is False
    )
    assert (
        permission.has_permission(_request(user=anonymous), SimpleNamespace(action="create"))
        is False
    )
    assert (
        permission.has_permission(_request(user=anonymous), SimpleNamespace(action="retrieve"))
        is True
    )


def test_item_permission_has_object_permission_raises_404_after_trashbin_cutoff(monkeypatch):
    permission = ItemPermission()
    deleted_at = timezone.now() - timedelta(days=30)

    def _cutoff():
        return timezone.now()

    monkeypatch.setattr("core.api.permissions.get_trashbin_cutoff", _cutoff)
    obj = SimpleNamespace(
        ancestors_deleted_at=deleted_at,
        get_abilities=lambda _user: {"retrieve": True},
        user_roles=[RoleChoices.OWNER],
    )

    with pytest.raises(Http404):
        permission.has_object_permission(
            _request(user=_User(is_authenticated=True)),
            SimpleNamespace(action="retrieve"),
            obj,
        )


def test_item_permission_maps_action_by_http_method_and_enforces_owner_on_deleted_tree(monkeypatch):
    permission = ItemPermission()

    def _cutoff():
        return timezone.now() - timedelta(days=1)

    monkeypatch.setattr(
        "core.api.permissions.get_trashbin_cutoff",
        _cutoff,
    )
    request = _request(method="GET", user=_User(is_authenticated=True))
    view = SimpleNamespace(action="children")
    obj = SimpleNamespace(
        ancestors_deleted_at=None,
        get_abilities=lambda _user: {"children_list": True},
        user_roles=[RoleChoices.OWNER],
    )

    assert permission.has_object_permission(request, view, obj) is True

    obj.ancestors_deleted_at = timezone.now()
    obj.user_roles = [RoleChoices.READER]
    with pytest.raises(Http404):
        permission.has_object_permission(request, view, obj)
