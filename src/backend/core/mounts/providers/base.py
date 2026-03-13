"""MountProvider base contracts."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Literal, Protocol

EntryType = Literal["file", "folder"]
BrowserStreamMode = Literal["proxy", "native", "none"]


@dataclasses.dataclass(frozen=True, slots=True)
class MountEntry:
    """Provider-agnostic mount entry (contract-level)."""

    entry_type: EntryType
    normalized_path: str
    name: str
    size: int | None = None
    modified_at: datetime | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class MountProviderError(Exception):
    """Deterministic provider error (no-leak) with guidance."""

    failure_class: str
    next_action_hint: str
    public_message: str
    public_code: str


@dataclasses.dataclass(frozen=True, slots=True)
class MountBrowserStreamCapabilities:
    """Provider browser-stream capabilities exposed to the core layer."""

    browser_stream_mode: BrowserStreamMode
    supports_random_access: bool
    supports_head_metadata: bool
    supports_stable_version: bool


class MountProvider(Protocol):
    """Mount provider contract (v1: browse only)."""

    def stat(self, *, mount: dict, normalized_path: str) -> MountEntry:
        """Return metadata for the target path; raises MountProviderError."""

    def list_children(self, *, mount: dict, normalized_path: str) -> list[MountEntry]:
        """List immediate children entries for a folder path; raises MountProviderError."""


def get_browser_stream_capabilities(
    *, provider, mount: dict
) -> MountBrowserStreamCapabilities:
    """Resolve browser-stream capabilities for a provider with sane fallbacks."""

    explicit = getattr(provider, "get_browser_stream_capabilities", None)
    if callable(explicit):
        capabilities = explicit(mount=mount)
        if isinstance(capabilities, MountBrowserStreamCapabilities):
            return capabilities

    supports_range_reads = False
    try:
        supports_range_reads = bool(
            getattr(provider, "supports_range_reads", lambda **_: False)(mount=mount)
        )
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        supports_range_reads = False

    has_stat = hasattr(provider, "stat")
    has_open_read = hasattr(provider, "open_read")
    if not has_open_read:
        return MountBrowserStreamCapabilities(
            browser_stream_mode="none",
            supports_random_access=False,
            supports_head_metadata=has_stat,
            supports_stable_version=has_stat,
        )

    return MountBrowserStreamCapabilities(
        browser_stream_mode="proxy",
        supports_random_access=supports_range_reads,
        supports_head_metadata=has_stat,
        supports_stable_version=has_stat,
    )
