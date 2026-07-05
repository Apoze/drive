"""Direct contract tests for the generate document template shell."""

from __future__ import annotations

from django import forms
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.test import RequestFactory


class _GenerateDocumentForm(forms.Form):
    title = forms.CharField()


def test_generate_document_template_renders_form_csrf_and_button():
    """The template keeps its expected form shell and submit affordance."""

    request = RequestFactory().get("/generate-document/")
    csrf_token = get_token(request)

    html = render_to_string(
        "core/generate_document.html",
        {"form": _GenerateDocumentForm()},
        request=request,
    )

    assert '<form method="post" enctype="multipart/form-data">' in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert "Generate PDF" in html
    assert "<h2>Generate item</h2>" in html
    assert csrf_token not in html  # masked token is rendered, not the raw canonical token
