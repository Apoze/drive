"""Direct contract tests for small DRF support helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

import core.api as api_module


def test_exception_handler_converts_django_validation_error_to_drf_validation_error(monkeypatch):
    captured = {}

    def _fake_drf_exception_handler(exc, context):
        captured["exc"] = exc
        captured["context"] = context
        return "handled"

    monkeypatch.setattr(api_module, "drf_exception_handler", _fake_drf_exception_handler)

    exc = DjangoValidationError({"field": ["Invalid value."]})
    context = {"view": "dummy-view"}

    response = api_module.exception_handler(exc, context)

    assert response == "handled"
    assert isinstance(captured["exc"], drf_exceptions.ValidationError)
    assert captured["exc"].detail == {"field": ["Invalid value."]}
    assert captured["context"] == context


def test_exception_handler_delegates_other_exceptions_as_is(monkeypatch):
    captured = {}

    def _fake_drf_exception_handler(exc, context):
        captured["exc"] = exc
        captured["context"] = context
        return "delegated"

    monkeypatch.setattr(api_module, "drf_exception_handler", _fake_drf_exception_handler)

    exc = RuntimeError("boom")
    context = {"request_id": "abc"}

    response = api_module.exception_handler(exc, context)

    assert response == "delegated"
    assert captured["exc"] is exc
    assert captured["context"] == context


def test_get_frontend_configuration_merges_language_code_and_frontend_configuration(settings):
    settings.LANGUAGE_CODE = "fr-fr"
    settings.FRONTEND_CONFIGURATION = {
        "SOME_FLAG": True,
        "DEFAULT_THEME": "blue",
    }

    request = APIRequestFactory().get("/api/v1.0/config/")
    response = api_module.get_frontend_configuration(request)

    assert isinstance(response, Response)
    assert response.data == {
        "LANGUAGE_CODE": "fr-fr",
        "SOME_FLAG": True,
        "DEFAULT_THEME": "blue",
    }
