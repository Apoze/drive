"""Direct contract tests for item/search filter helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from django.http import QueryDict

import pytest

from core import factories, models
from core.api.filters import ListItemFilter, ScopeChoices, SearchItemFilter

pytestmark = pytest.mark.django_db


def _querydict(**values):
    querydict = QueryDict("", mutable=True)
    for key, value in values.items():
        if isinstance(value, list):
            querydict.setlist(key, value)
        else:
            querydict[key] = value
    return querydict


def test_search_item_filter_uses_not_deleted_as_default_scope():
    """Bound filters inject `scope=not_deleted` when the client omits it."""

    active = factories.ItemFactory(title="active")
    deleted = factories.ItemFactory(
        title="deleted",
        deleted_at="2024-01-01T00:00:00Z",
        ancestors_deleted_at="2024-01-01T00:00:00Z",
    )

    filterset = SearchItemFilter(
        data=QueryDict("", mutable=True), queryset=models.Item.objects.all()
    )

    assert filterset.data["scope"] == ScopeChoices.NOT_DELETED
    assert list(filterset.qs.values_list("id", flat=True)) == [active.id]
    assert deleted.id not in filterset.qs.values_list("id", flat=True)


def test_search_item_filter_workspace_bypasses_queryset_filtering():
    """Workspace filtering is delegated to the calling viewset."""

    queryset = MagicMock()
    filterset = SearchItemFilter(queryset=models.Item.objects.none())

    assert filterset.filter_workspace(queryset, "workspace", "ignored") is queryset


def test_search_item_filter_handles_all_deleted_and_not_deleted_scopes():
    """Scope filtering keeps the documented semantics for all stable values."""

    active = factories.ItemFactory(title="active")
    deleted = factories.ItemFactory(
        title="deleted",
        deleted_at="2024-01-01T00:00:00Z",
        ancestors_deleted_at="2024-01-01T00:00:00Z",
    )
    ancestor_deleted = factories.ItemFactory(
        title="ancestor-deleted",
        ancestors_deleted_at="2024-01-01T00:00:00Z",
    )
    queryset = models.Item.objects.all().order_by("title")
    filterset = SearchItemFilter(queryset=queryset)

    all_ids = set(
        filterset.filter_scope(queryset, "scope", [ScopeChoices.ALL]).values_list("id", flat=True)
    )
    deleted_ids = set(
        filterset.filter_scope(queryset, "scope", [ScopeChoices.DELETED]).values_list(
            "id", flat=True
        )
    )
    not_deleted_ids = set(
        filterset.filter_scope(queryset, "scope", [ScopeChoices.NOT_DELETED]).values_list(
            "id", flat=True
        )
    )

    assert all_ids == {active.id, deleted.id, ancestor_deleted.id}
    assert deleted_ids == {deleted.id, ancestor_deleted.id}
    assert not_deleted_ids == {active.id}


def test_list_item_filter_creator_me_uses_current_user():
    """The creator filter delegates to queryset filter/exclude on the request user."""

    user = factories.UserFactory()
    queryset = MagicMock()
    request = SimpleNamespace(user=user)
    filterset = ListItemFilter(queryset=models.Item.objects.none(), request=request)

    filterset.filter_is_creator_me(queryset, "is_creator_me", True)
    queryset.filter.assert_called_once_with(creator=user)

    queryset.reset_mock()
    filterset.filter_is_creator_me(queryset, "is_creator_me", False)
    queryset.exclude.assert_called_once_with(creator=user)


def test_list_item_filter_returns_queryset_unchanged_for_anonymous_user():
    """Anonymous callers do not trigger creator/favorite filters."""

    queryset = MagicMock()
    request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
    filterset = ListItemFilter(queryset=models.Item.objects.none(), request=request)

    assert filterset.filter_is_creator_me(queryset, "is_creator_me", True) is queryset
    assert filterset.filter_is_favorite(queryset, "is_favorite", True) is queryset
    queryset.filter.assert_not_called()
    queryset.exclude.assert_not_called()


def test_list_item_filter_favorite_uses_boolean_value():
    """Favorite filtering passes the normalized boolean to the queryset."""

    queryset = MagicMock()
    request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))
    filterset = ListItemFilter(queryset=models.Item.objects.none(), request=request)

    filterset.filter_is_favorite(queryset, "is_favorite", 0)

    queryset.filter.assert_called_once_with(is_favorite=False)
