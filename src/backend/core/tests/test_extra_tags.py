"""Direct contract tests for core template base64 helpers."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from core.templatetags.extra_tags import base64_static, image_to_base64

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_image_to_base64_reads_image_from_path(tmp_path):
    """File paths are encoded into a data URI when the image is readable."""

    image_path = tmp_path / "pixel.png"
    image_path.write_bytes(PNG_BYTES)

    result = image_to_base64(Path(image_path).as_posix())

    assert result.startswith("data:image/png;base64, ")


def test_image_to_base64_repositions_open_file_objects(tmp_path):
    """Open file objects are rewound for reading, then restored to their position."""

    image_path = tmp_path / "pixel.png"
    image_path.write_bytes(PNG_BYTES)

    with image_path.open("rb") as image_file:
        image_file.seek(5)
        original_position = image_file.tell()

        result = image_to_base64(image_file)

        assert result.startswith("data:image/png;base64, ")
        assert image_file.tell() == original_position


def test_image_to_base64_returns_empty_on_error_or_empty_content(tmp_path):
    """Unreadable paths and empty payloads return the documented empty string."""

    missing_path = tmp_path / "missing.png"

    assert image_to_base64(missing_path.as_posix()) == ""
    assert image_to_base64(BytesIO(b"")) == ""


def test_base64_static_uses_finders(monkeypatch, tmp_path):
    """`base64_static` resolves the static path then delegates to `image_to_base64`."""

    image_path = tmp_path / "pixel.png"
    image_path.write_bytes(PNG_BYTES)
    monkeypatch.setattr("core.templatetags.extra_tags.finders.find", lambda path: str(image_path))

    result = base64_static("core/pixel.png")

    assert result.startswith("data:image/png;base64, ")
