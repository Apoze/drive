"""Tests for title collision helper contracts."""
# pylint: disable=missing-function-docstring,missing-class-docstring

import re
from dataclasses import dataclass

import pytest

from core.utils.item_title import (
    _extract_number_from_title,
    _get_next_available_number,
    manage_unique_title,
)


@dataclass(frozen=True)
class _Item:
    title: str
    deleted: bool = False


class _ValuesListResult:
    def __init__(self, titles):
        self._titles = list(titles)

    def __iter__(self):
        return iter(self._titles)

    def __bool__(self):
        return bool(self._titles)


class _FilteredQuerySet:
    def __init__(self, items):
        self._items = list(items)

    def exists(self):
        return bool(self._items)

    def values_list(self, field_name, flat=False):
        assert field_name == "title"
        assert flat is True
        return _ValuesListResult(item.title for item in self._items)


class _FakeQuerySet:
    def __init__(self, items):
        self._items = list(items)

    def filter_non_deleted(self, **criteria):
        filtered = [item for item in self._items if not item.deleted]

        exact_title = criteria.get("title")
        if exact_title is not None:
            filtered = [item for item in filtered if item.title == exact_title]

        title_regex = criteria.get("title__regex")
        if title_regex is not None:
            pattern = re.compile(title_regex)
            filtered = [item for item in filtered if pattern.match(item.title)]

        return _FilteredQuerySet(filtered)


@pytest.mark.parametrize(
    ("title", "expected_number"),
    [
        ("Document_07.odt", 7),
        ("Document.odt", 0),
        ("Document_final.txt", 0),
        ("Folder_123", 123),
    ],
)
def test_extract_number_from_title_handles_numbered_and_plain_titles(
    title,
    expected_number,
):
    assert _extract_number_from_title(title) == expected_number


def test_get_next_available_number_starts_at_01_without_existing_suffix():
    queryset = _FakeQuerySet([_Item("Report.odt")])

    assert _get_next_available_number(queryset, "Report", ".odt") == "01"


def test_get_next_available_number_returns_next_highest_with_zero_padding():
    queryset = _FakeQuerySet(
        [
            _Item("Report_01.odt"),
            _Item("Report_02.odt"),
            _Item("Report_10.odt"),
            _Item("Report_03.odt", deleted=True),
        ]
    )

    assert _get_next_available_number(queryset, "Report", ".odt") == "11"


def test_manage_unique_title_returns_original_when_no_collision():
    queryset = _FakeQuerySet([_Item("Another file.odt")])

    assert manage_unique_title(queryset, "Report.odt") == "Report.odt"


def test_manage_unique_title_appends_number_and_preserves_extension():
    queryset = _FakeQuerySet(
        [
            _Item("Report.odt"),
            _Item("Report_01.odt"),
            _Item("Report_02.odt"),
            _Item("Report_09.odt"),
        ]
    )

    assert manage_unique_title(queryset, "Report.odt") == "Report_10.odt"


def test_manage_unique_title_handles_titles_without_extension():
    queryset = _FakeQuerySet(
        [
            _Item("Folder"),
            _Item("Folder_01"),
        ]
    )

    assert manage_unique_title(queryset, "Folder") == "Folder_02"
