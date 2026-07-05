"""Direct contract tests for refs-only configuration helpers."""
# pylint: disable=unused-argument

from __future__ import annotations

from pathlib import Path

import pytest

from core.utils.secret_refs import SecretRefValue


def _setup_secret_ref(
    *,
    environ_name: str = "TEST_SECRET",
    default: str | None = None,
):
    value = SecretRefValue(
        default,
        environ_name=environ_name,
        environ_prefix=None,
        late_binding=True,
    )
    return value.setup("ignored_setting_name")


def test_secret_ref_value_rejects_direct_env_without_leaking_secret(monkeypatch):
    """Direct secret material in `{NAME}` is rejected deterministically."""

    monkeypatch.setenv("TEST_SECRET", "raw-top-secret")

    with pytest.raises(ValueError) as excinfo:
        _setup_secret_ref()

    message = str(excinfo.value)
    assert "config.secret.direct_value_forbidden" in message
    assert "'TEST_SECRET_FILE'" in message
    assert "'TEST_SECRET_ENV'" in message
    assert "raw-top-secret" not in message


def test_secret_ref_value_reads_secret_from_file(monkeypatch, tmp_path):
    """`*_FILE` takes precedence and strips one trailing newline."""

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("file-secret\n", encoding="utf-8")
    monkeypatch.setenv("TEST_SECRET_FILE", str(secret_file))
    monkeypatch.setenv("TEST_SECRET_ENV", "REFERENCED_SECRET")
    monkeypatch.setenv("REFERENCED_SECRET", "env-secret")

    resolved = _setup_secret_ref()

    assert resolved == "file-secret"


def test_secret_ref_value_reads_secret_from_env_reference(monkeypatch):
    """`*_ENV` resolves the referenced env var value."""

    monkeypatch.setenv("TEST_SECRET_ENV", "REFERENCED_SECRET")
    monkeypatch.setenv("REFERENCED_SECRET", "env-secret")

    resolved = _setup_secret_ref()

    assert resolved == "env-secret"


def test_secret_ref_value_uses_default_when_no_ref_is_set(monkeypatch):
    """Default values still apply when no refs are configured."""

    resolved = _setup_secret_ref(default="fallback-secret")

    assert resolved == "fallback-secret"


def test_secret_ref_value_reports_missing_file_without_leaking_path(monkeypatch, tmp_path):
    """Missing file failures stay deterministic and no-leak."""

    missing = Path(tmp_path / "top-secret-path").as_posix()
    monkeypatch.setenv("TEST_SECRET_FILE", missing)

    with pytest.raises(ValueError) as excinfo:
        _setup_secret_ref()

    message = str(excinfo.value)
    assert "config.secret.file_missing" in message
    assert "TEST_SECRET_FILE" in message
    assert missing not in message
    assert "top-secret-path" not in message


def test_secret_ref_value_reports_unreadable_file_without_leaking_path(monkeypatch, tmp_path):
    """Unreadable file failures stay deterministic and no-leak."""

    secret_file = tmp_path / "raw-secret.txt"
    secret_file.write_text("file-secret\n", encoding="utf-8")
    monkeypatch.setenv("TEST_SECRET_FILE", str(secret_file))

    def raise_permission_error(*args, **kwargs):
        raise PermissionError("permission denied for raw-secret.txt")

    monkeypatch.setattr("builtins.open", raise_permission_error)

    with pytest.raises(ValueError) as excinfo:
        _setup_secret_ref()

    message = str(excinfo.value)
    assert "config.secret.file_unreadable" in message
    assert "TEST_SECRET_FILE" in message
    assert str(secret_file) not in message
    assert "raw-secret.txt" not in message


def test_secret_ref_value_reports_missing_env_reference_without_leaking_value(monkeypatch):
    """Missing referenced env vars fail deterministically and no-leak."""

    monkeypatch.setenv("TEST_SECRET_ENV", "MISSING_SECRET")

    with pytest.raises(ValueError) as excinfo:
        _setup_secret_ref()

    message = str(excinfo.value)
    assert "config.secret.env_ref_missing" in message
    assert "TEST_SECRET_ENV" in message
    assert "MISSING_SECRET" not in message
