"""Tests for legacy conversion policy helpers."""

# pylint: disable=missing-function-docstring

from django.conf import settings

from core import factories
from wopi.conversion.policy import is_forced_conversion, target_extension_for


def _item(filename="document.doc", mimetype="application/msword"):
    return factories.ItemFactory.build(filename=filename, mimetype=mimetype)


def test_target_extension_for_known_legacy_formats():
    assert target_extension_for("doc") == "docx"
    assert target_extension_for("xls") == "xlsx"
    assert target_extension_for("ppt") == "pptx"


def test_target_extension_for_is_case_insensitive():
    assert target_extension_for("DOC") == "docx"
    assert target_extension_for("Xls") == "xlsx"


def test_target_extension_for_unknown_format_returns_none():
    assert target_extension_for("docx") is None
    assert target_extension_for("") is None
    assert target_extension_for(None) is None


def test_legacy_conversion_targets_only_lists_legacy_formats():
    assert set(settings.WOPI_LEGACY_CONVERSION_TARGETS) == {"doc", "xls", "ppt"}


def test_is_forced_conversion_true_when_extension_listed():
    options = {"ForceConvertExtensions": ["doc", "xls", "ppt"]}
    assert is_forced_conversion(_item(filename="document.doc"), options) is True


def test_is_forced_conversion_true_when_mimetype_listed():
    options = {"ForceConvertMimetypes": ["application/msword"]}
    item = _item(filename="document.unknown", mimetype="application/msword")
    assert is_forced_conversion(item, options) is True


def test_is_forced_conversion_false_when_neither_matches():
    options = {
        "ForceConvertExtensions": ["doc"],
        "ForceConvertMimetypes": ["application/msword"],
    }
    item = _item(filename="document.docx", mimetype="application/vnd.openxmlformats")
    assert is_forced_conversion(item, options) is False


def test_is_forced_conversion_false_when_options_missing():
    assert is_forced_conversion(_item(), {}) is False
    assert is_forced_conversion(_item(), None) is False


def test_is_forced_conversion_extension_check_is_case_insensitive():
    assert is_forced_conversion(
        _item(filename="REPORT.DOC"),
        {"ForceConvertExtensions": ["doc"]},
    )
    assert is_forced_conversion(
        _item(filename="document.doc"),
        {"ForceConvertExtensions": ["DOC"]},
    )
