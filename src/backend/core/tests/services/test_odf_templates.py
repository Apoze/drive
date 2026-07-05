"""Tests for minimal ODF template generation."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from io import BytesIO
from zipfile import ZIP_STORED, ZipFile

import pytest

from core.services.odf_templates import build_minimal_odf_template_bytes


@pytest.mark.parametrize(
    ("kind", "expected_mimetype", "expected_marker"),
    [
        ("odt", "application/vnd.oasis.opendocument.text", "<office:text>"),
        (
            "ods",
            "application/vnd.oasis.opendocument.spreadsheet",
            "<office:spreadsheet>",
        ),
        (
            "odp",
            "application/vnd.oasis.opendocument.presentation",
            "<office:presentation>",
        ),
    ],
)
def test_build_minimal_odf_template_bytes_builds_valid_container(
    kind,
    expected_mimetype,
    expected_marker,
):
    mimetype, payload = build_minimal_odf_template_bytes(kind)

    assert mimetype == expected_mimetype
    assert payload[:2] == b"PK"

    with ZipFile(BytesIO(payload)) as archive:
        entries = archive.infolist()
        names = {entry.filename for entry in entries}

        assert entries[0].filename == "mimetype"
        assert entries[0].compress_type == ZIP_STORED
        assert archive.read("mimetype").decode("utf-8") == expected_mimetype
        assert {
            "mimetype",
            "content.xml",
            "styles.xml",
            "meta.xml",
            "settings.xml",
            "META-INF/manifest.xml",
        }.issubset(names)

        assert expected_marker in archive.read("content.xml").decode("utf-8")

        manifest_xml = archive.read("META-INF/manifest.xml").decode("utf-8")
        assert 'manifest:full-path="/"' in manifest_xml
        assert expected_mimetype in manifest_xml


def test_build_minimal_odf_template_bytes_rejects_unsupported_kind():
    with pytest.raises(ValueError, match="unsupported_kind"):
        build_minimal_odf_template_bytes("pdf")
