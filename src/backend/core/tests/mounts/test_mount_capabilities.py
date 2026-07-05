"""Tests for centralized mount capability / IO resolution helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

from datetime import datetime, timezone

from core.mounts.providers.base import (
    MountBrowserStreamCapabilities,
    MountEntry,
)
from core.services.mount_capabilities import (
    MOUNT_DOWNLOAD_UNAVAILABLE,
    MOUNT_WOPI_UNAVAILABLE,
    MountEndpointUnavailableError,
    MountEntryNotAFileError,
    build_mount_entry_abilities,
    classify_mount_preview_kind,
    resolve_enabled_mount,
    resolve_mount_preview_contract,
    resolve_mount_provider_context,
    resolve_mount_provider_io_capabilities,
    resolve_mount_wopi_target,
)


class _ProviderWithExplicitStreamCapabilities:
    def stat(self, **_kwargs):
        return None

    def open_read(self, **_kwargs):
        return None

    def get_browser_stream_capabilities(self, *, mount: dict):
        _ = mount
        return MountBrowserStreamCapabilities(
            browser_stream_mode="proxy",
            supports_random_access=True,
            supports_head_metadata=True,
            supports_stable_version=False,
        )


class _ProviderWithoutReadSupport:
    def stat(self, **_kwargs):
        return None


class _WritableProvider(_ProviderWithExplicitStreamCapabilities):
    def open_write(self, **_kwargs):
        return None

    def rename(self, **_kwargs):
        return None

    def remove(self, **_kwargs):
        return None


def test_resolve_mount_provider_io_capabilities_prefers_explicit_stream_contract():
    io = resolve_mount_provider_io_capabilities(
        provider=_ProviderWithExplicitStreamCapabilities(),
        mount={"mount_id": "alpha"},
    )

    assert io.stat is True
    assert io.open_read is True
    assert io.open_write is False
    assert io.rename is False
    assert io.remove is False
    assert io.mkdirs is False
    assert io.range_reads is True
    assert io.browser_stream_mode == "proxy"
    assert io.head_metadata is True
    assert io.stable_version is False


def test_resolve_mount_provider_io_capabilities_falls_back_to_no_stream_without_open_read():
    io = resolve_mount_provider_io_capabilities(
        provider=_ProviderWithoutReadSupport(),
        mount={"mount_id": "alpha"},
    )

    assert io.stat is True
    assert io.open_read is False
    assert io.range_reads is False
    assert io.browser_stream_mode == "none"
    assert io.head_metadata is True
    assert io.stable_version is True


def test_resolve_mount_provider_context_returns_provider_and_io(monkeypatch):
    provider = _ProviderWithExplicitStreamCapabilities()
    monkeypatch.setattr(
        "core.services.mount_capabilities.get_mount_provider",
        lambda _provider_name: provider,
    )

    resolved = resolve_mount_provider_context(
        mount={"mount_id": "alpha", "provider": "stub"},
        unavailable_spec=MOUNT_DOWNLOAD_UNAVAILABLE,
    )

    assert resolved.provider is provider
    assert resolved.io_capabilities.open_read is True
    assert resolved.io_capabilities.browser_stream_mode == "proxy"


def test_resolve_mount_provider_context_raises_unavailable_for_missing_required_io(monkeypatch):
    provider = _ProviderWithoutReadSupport()
    monkeypatch.setattr(
        "core.services.mount_capabilities.get_mount_provider",
        lambda _provider_name: provider,
    )

    try:
        resolve_mount_provider_context(
            mount={"mount_id": "alpha", "provider": "stub"},
            unavailable_spec=MOUNT_DOWNLOAD_UNAVAILABLE,
        )
    except MountEndpointUnavailableError as exc:
        assert exc.spec.public_code == "mount.download.unavailable"
        assert exc.spec.public_message == "Download is not available for this mount."
    else:  # pragma: no cover - defensive
        raise AssertionError("expected MountEndpointUnavailableError")


def test_resolve_enabled_mount_filters_disabled_mounts(settings):
    settings.MOUNTS_REGISTRY = [
        {"mount_id": "disabled", "enabled": False},
        {"mount_id": "enabled", "enabled": True},
    ]

    assert resolve_enabled_mount("disabled") is None
    assert resolve_enabled_mount("enabled") == {"mount_id": "enabled", "enabled": True}


def test_resolve_mount_wopi_target_returns_shared_contract(monkeypatch):
    provider = _WritableProvider()
    entry = MountEntry(
        entry_type="file",
        normalized_path="/hello.txt",
        name="hello.txt",
        size=7,
        modified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        "core.services.mount_capabilities.get_mount_provider",
        lambda _provider_name: provider,
    )
    monkeypatch.setattr(provider, "stat", lambda **_kwargs: entry, raising=True)

    resolved = resolve_mount_wopi_target(
        mount={"mount_id": "alpha", "provider": "stub"},
        mount_id="alpha",
        normalized_path="/hello.txt",
    )

    assert resolved.mount == {"mount_id": "alpha", "provider": "stub"}
    assert resolved.provider is provider
    assert resolved.io_capabilities.supports(*MOUNT_WOPI_UNAVAILABLE.required_io) is True
    assert resolved.entry == entry
    assert resolved.version.startswith("m1-")


def test_resolve_mount_wopi_target_rejects_non_file_entry(monkeypatch):
    provider = _WritableProvider()
    monkeypatch.setattr(
        "core.services.mount_capabilities.get_mount_provider",
        lambda _provider_name: provider,
    )
    monkeypatch.setattr(
        provider,
        "stat",
        lambda **_kwargs: MountEntry(
            entry_type="folder",
            normalized_path="/docs",
            name="docs",
            size=None,
            modified_at=None,
        ),
        raising=True,
    )

    try:
        resolve_mount_wopi_target(
            mount={"mount_id": "alpha", "provider": "stub"},
            mount_id="alpha",
            normalized_path="/docs",
        )
    except MountEntryNotAFileError as exc:
        assert exc.normalized_path == "/docs"
    else:  # pragma: no cover - defensive
        raise AssertionError("expected MountEntryNotAFileError")


def test_build_mount_entry_abilities_keeps_folder_actions_capability_driven():
    entry = MountEntry(
        entry_type="folder",
        normalized_path="/projects",
        name="projects",
        size=None,
        modified_at=None,
    )
    io = resolve_mount_provider_io_capabilities(
        provider=_ProviderWithExplicitStreamCapabilities(),
        mount={"mount_id": "alpha"},
    )

    abilities = build_mount_entry_abilities(
        entry=entry,
        mount_capabilities={
            "mount.create_folder": True,
            "mount.move": True,
            "mount.rename": True,
            "mount.delete": True,
            "mount.upload": True,
            "mount.duplicate": True,
            "mount.preview": True,
            "mount.wopi": True,
            "mount.share_link": False,
        },
        io_capabilities=io,
        preview_candidate=False,
        wopi_supported=False,
    )

    assert abilities == {
        "children_list": True,
        "create_folder": False,
        "move": False,
        "rename": False,
        "destroy": False,
        "upload": False,
        "duplicate": False,
        "download": False,
        "preview": False,
        "wopi": False,
        "share_link_create": False,
    }


def test_build_mount_entry_abilities_keeps_file_preview_and_wopi_contract_exact():
    entry = MountEntry(
        entry_type="file",
        normalized_path="/doc.docx",
        name="doc.docx",
        size=123,
        modified_at=None,
    )
    io = resolve_mount_provider_io_capabilities(
        provider=_WritableProvider(),
        mount={"mount_id": "alpha"},
    )

    abilities = build_mount_entry_abilities(
        entry=entry,
        mount_capabilities={
            "mount.create_folder": True,
            "mount.move": True,
            "mount.rename": True,
            "mount.delete": True,
            "mount.upload": True,
            "mount.duplicate": True,
            "mount.preview": True,
            "mount.wopi": True,
            "mount.share_link": True,
        },
        io_capabilities=io,
        preview_candidate=True,
        wopi_supported=True,
    )

    assert abilities == {
        "children_list": False,
        "create_folder": False,
        "move": True,
        "rename": True,
        "destroy": True,
        "upload": False,
        "duplicate": True,
        "download": True,
        "preview": True,
        "wopi": True,
        "share_link_create": True,
    }


def test_classify_mount_preview_kind_prefers_wopi_before_inline_media():
    assert (
        classify_mount_preview_kind(
            mimetype="image/png",
            is_wopi_supported=True,
            can_inline_preview=True,
        )
        == "wopi"
    )


def test_resolve_mount_preview_contract_keeps_text_editable_when_wopi_not_preferred():
    resolved = resolve_mount_preview_contract(
        filename="notes.md",
        mimetype="text/markdown",
        can_inline_preview=True,
        is_wopi_supported=True,
        can_download=True,
        can_edit_text=True,
        text_supported=True,
    )

    assert resolved.preview_kind == "text"
    assert resolved.is_wopi_supported is True
    assert resolved.can_download is True
    assert resolved.can_edit_text is True
    assert resolved.has_inline_url is False
    assert resolved.needs_stream_ticket is False
    assert resolved.stream_purpose is None


def test_resolve_mount_preview_contract_prefers_wopi_for_txt_without_edit_flag():
    resolved = resolve_mount_preview_contract(
        filename="notes.txt",
        mimetype="text/plain",
        can_inline_preview=True,
        is_wopi_supported=True,
        can_download=True,
        can_edit_text=True,
        text_supported=True,
    )

    assert resolved.preview_kind == "wopi"
    assert resolved.can_edit_text is False
    assert resolved.needs_stream_ticket is False


def test_resolve_mount_preview_contract_marks_archive_for_ticket_without_inline_url():
    resolved = resolve_mount_preview_contract(
        filename="bundle.tar.gz",
        mimetype="application/gzip",
        can_inline_preview=True,
        is_wopi_supported=False,
        can_download=True,
        can_edit_text=False,
        text_supported=False,
    )

    assert resolved.preview_kind == "archive"
    assert resolved.can_edit_text is False
    assert resolved.has_inline_url is False
    assert resolved.needs_stream_ticket is True
    assert resolved.stream_purpose == "archive"
