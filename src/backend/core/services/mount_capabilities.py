"""Mount capability keys and normalization helpers (contract-level)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

from core.mounts.providers.base import (
    BrowserStreamMode,
    MountEntry,
    get_browser_stream_capabilities,
)
from core.mounts.registry import get_mount_provider
from wopi.utils import compute_mount_entry_version

MOUNT_CAPABILITY_KEYS: tuple[str, ...] = (
    "mount.create_folder",
    "mount.move",
    "mount.rename",
    "mount.delete",
    "mount.upload",
    "mount.duplicate",
    "mount.preview",
    "mount.wopi",
    "mount.share_link",
)

DEFAULT_MOUNT_CAPABILITIES: dict[str, bool] = {
    # Mounts are filesystem-like backends; by default we expose core actions
    # and allow operators to explicitly disable them via params.capabilities.
    "mount.create_folder": True,
    "mount.move": True,
    "mount.rename": True,
    "mount.delete": True,
    "mount.upload": True,
    "mount.duplicate": True,
    "mount.preview": True,
    "mount.wopi": True,
    # Sharing is more sensitive; keep it opt-in.
    "mount.share_link": False,
}

MOUNT_INLINE_PREVIEW_KINDS = frozenset({"image", "video", "audio", "pdf"})
MOUNT_STREAMED_PREVIEW_KINDS = frozenset({"image", "video", "audio", "pdf", "archive"})
MOUNT_ARCHIVE_PREVIEW_MIMETYPES = frozenset({"application/zip", "application/x-tar"})
MOUNT_ARCHIVE_MULTI_EXTENSIONS = (
    "tar.gz",
    "tgz",
    "tar.bz2",
    "tbz",
    "tbz2",
    "tar.xz",
    "txz",
)
MOUNT_ARCHIVE_CONTAINER_EXTENSIONS = frozenset({"zip", "tar"})
MOUNT_ARCHIVE_SINGLE_COMPRESSION_EXTENSIONS = frozenset({"gz", "bz2", "xz"})


@dataclass(frozen=True, slots=True)
class MountProviderIoCapabilities:
    """Resolved provider IO/browser-stream contract for mount endpoints."""

    # pylint: disable=too-many-instance-attributes

    stat: bool
    open_read: bool
    open_write: bool
    rename: bool
    remove: bool
    mkdirs: bool
    range_reads: bool
    browser_stream_mode: BrowserStreamMode
    head_metadata: bool
    stable_version: bool

    def supports(self, *capability_names: str) -> bool:
        """Return True only when all requested IO capabilities are enabled."""

        return all(
            bool(getattr(self, capability_name, False)) for capability_name in capability_names
        )

    def as_dict(self) -> dict[str, bool | str]:
        """Compatibility mapping for legacy call sites."""

        return {
            "stat": self.stat,
            "open_read": self.open_read,
            "open_write": self.open_write,
            "rename": self.rename,
            "remove": self.remove,
            "mkdirs": self.mkdirs,
            "range_reads": self.range_reads,
            "browser_stream_mode": self.browser_stream_mode,
            "head_metadata": self.head_metadata,
            "stable_version": self.stable_version,
        }


@dataclass(frozen=True, slots=True)
class MountEndpointUnavailableSpec:
    """Deterministic endpoint unavailable contract for shared mount guards."""

    log_name: str
    required_io: tuple[str, ...]
    failure_class: str
    next_action_hint: str
    public_message: str
    public_code: str


@dataclass(frozen=True, slots=True)
class ResolvedMountProviderContext:
    """Resolved provider + IO capabilities for one mount endpoint guard."""

    provider: Any
    io_capabilities: MountProviderIoCapabilities


@dataclass(frozen=True, slots=True)
class ResolvedMountWopiTarget:
    """Resolved mount-backed WOPI target without HTTP-specific concerns."""

    mount: dict[str, Any]
    provider: Any
    io_capabilities: MountProviderIoCapabilities
    entry: MountEntry
    version: str


@dataclass(frozen=True, slots=True)
class MountEndpointUnavailableError(Exception):
    """Internal sentinel used by endpoint guards before HTTP translation."""

    spec: MountEndpointUnavailableSpec


@dataclass(frozen=True, slots=True)
class MountEntryNotAFileError(Exception):
    """Internal sentinel for mount flows that require a file target."""

    normalized_path: str


@dataclass(frozen=True, slots=True)
class ResolvedMountPreviewContract:
    """Resolved preview semantics independent from HTTP payload wiring."""

    preview_kind: str
    is_wopi_supported: bool
    can_download: bool
    can_edit_text: bool
    has_inline_url: bool
    needs_stream_ticket: bool
    stream_purpose: str | None


MOUNT_CREATE_FOLDER_UNAVAILABLE = MountEndpointUnavailableSpec(
    log_name="mount_create_folder",
    required_io=("mkdirs", "stat"),
    failure_class="mount.create_folder.unavailable",
    next_action_hint=(
        "Enable mount folder creation or configure a provider that supports directory creation"
    ),
    public_message="Folder creation is not available for this mount.",
    public_code="mount.create_folder.unavailable",
)

MOUNT_MOVE_UNAVAILABLE = MountEndpointUnavailableSpec(
    log_name="mount_move",
    required_io=("rename", "stat"),
    failure_class="mount.move.unavailable",
    next_action_hint="Enable mount move or configure a provider that supports intra-mount move",
    public_message="Move is not available for this mount.",
    public_code="mount.move.unavailable",
)

MOUNT_RENAME_UNAVAILABLE = MountEndpointUnavailableSpec(
    log_name="mount_rename",
    required_io=("rename",),
    failure_class="mount.rename.unavailable",
    next_action_hint="Enable mount rename or configure a provider that supports rename",
    public_message="Rename is not available for this mount.",
    public_code="mount.rename.unavailable",
)

MOUNT_DELETE_UNAVAILABLE = MountEndpointUnavailableSpec(
    log_name="mount_delete",
    required_io=("remove",),
    failure_class="mount.delete.unavailable",
    next_action_hint="Enable mount delete or configure a provider that supports delete",
    public_message="Delete is not available for this mount.",
    public_code="mount.delete.unavailable",
)

MOUNT_UPLOAD_UNAVAILABLE = MountEndpointUnavailableSpec(
    log_name="mount_upload",
    required_io=("open_write", "rename", "remove"),
    failure_class="mount.upload.unavailable",
    next_action_hint="Enable mount upload or configure a provider that supports upload",
    public_message="Upload is not available for this mount.",
    public_code="mount.upload.unavailable",
)

MOUNT_DUPLICATE_UNAVAILABLE = MountEndpointUnavailableSpec(
    log_name="mount_duplicate",
    required_io=("stat", "open_read", "open_write", "rename", "remove"),
    failure_class="mount.duplicate.unavailable",
    next_action_hint=(
        "Enable mount duplicate or configure a provider that supports streaming duplicate"
    ),
    public_message="Duplicate is not available for this mount.",
    public_code="mount.duplicate.unavailable",
)

MOUNT_PREVIEW_UNAVAILABLE = MountEndpointUnavailableSpec(
    log_name="mount_preview",
    required_io=("open_read",),
    failure_class="mount.preview.unavailable",
    next_action_hint="Enable mount preview or configure a provider that supports preview",
    public_message="Preview is not available for this mount.",
    public_code="mount.preview.unavailable",
)

MOUNT_TEXT_UNAVAILABLE = MountEndpointUnavailableSpec(
    log_name="mount_text",
    required_io=("open_read",),
    failure_class="mount.text.unavailable",
    next_action_hint="Configure a provider that supports text preview reads",
    public_message="Text preview is not available for this mount.",
    public_code="mount.text.unavailable",
)

MOUNT_STREAM_UNAVAILABLE = MountEndpointUnavailableSpec(
    log_name="mount_stream",
    required_io=("open_read",),
    failure_class="mount.stream.unavailable",
    next_action_hint="Configure a provider that supports stream reads",
    public_message="Stream is not available for this mount.",
    public_code="mount.stream.unavailable",
)

MOUNT_WOPI_UNAVAILABLE = MountEndpointUnavailableSpec(
    log_name="mount_wopi",
    required_io=("open_read", "open_write"),
    failure_class="mount.wopi.unavailable",
    next_action_hint="Configure a provider that supports WOPI",
    public_message="Online editing is not available for this mount.",
    public_code="mount.wopi.unavailable",
)

MOUNT_DOWNLOAD_UNAVAILABLE = MountEndpointUnavailableSpec(
    log_name="mount_download",
    required_io=("open_read",),
    failure_class="mount.download.unavailable",
    next_action_hint="Configure a provider that supports download",
    public_message="Download is not available for this mount.",
    public_code="mount.download.unavailable",
)


def normalize_mount_capabilities(raw: Any) -> dict[str, bool]:
    """
    Normalize a raw capabilities object into a contract-level capability map.

    - Keys are enforced to the documented constants.
    - Values must be booleans; anything else is treated as `False`.
    """

    src = raw if isinstance(raw, dict) else {}

    normalized: dict[str, bool] = dict(DEFAULT_MOUNT_CAPABILITIES)
    for key in MOUNT_CAPABILITY_KEYS:
        value = src.get(key, DEFAULT_MOUNT_CAPABILITIES.get(key, False))
        normalized[key] = value if isinstance(value, bool) else normalized[key]
    return normalized


def resolve_enabled_mount(mount_id: str) -> dict[str, Any] | None:
    """Return the enabled mount registry entry for the given mount id."""

    mounts = list(getattr(settings, "MOUNTS_REGISTRY", []) or [])
    for mount in mounts:
        if not bool(mount.get("enabled", True)):
            continue
        if mount.get("mount_id") == mount_id:
            return mount
    return None


def should_prefer_wopi_text(filename: str | None) -> bool:
    """Return whether WOPI should win over text preview for this filename."""

    lower = str(filename or "").strip().lower()
    if "." not in lower:
        return False
    return lower.rsplit(".", 1)[-1] == "txt"


def is_archive_filename(filename: str | None) -> bool:
    """Return whether the filename is an archive container handled by preview."""

    lower = str(filename or "").strip().lower()
    if not lower:
        return False
    for ext in MOUNT_ARCHIVE_MULTI_EXTENSIONS:
        if lower.endswith(f".{ext}"):
            return True
    if "." not in lower:
        return False
    ext = lower.rsplit(".", 1)[-1]
    if ext in MOUNT_ARCHIVE_CONTAINER_EXTENSIONS:
        return True
    if ext in MOUNT_ARCHIVE_SINGLE_COMPRESSION_EXTENSIONS:
        return False
    return False


def classify_mount_preview_kind(
    *,
    mimetype: str,
    is_wopi_supported: bool,
    can_inline_preview: bool,
) -> str:
    """Classify direct preview kind for one mount file."""

    normalized = str(mimetype or "").split(";", 1)[0].strip().lower()
    if is_wopi_supported:
        return "wopi"
    if not can_inline_preview:
        return "unsupported"
    if normalized.startswith("image/"):
        return "image"
    if normalized.startswith("video/"):
        return "video"
    if normalized.startswith("audio/"):
        return "audio"
    return "pdf" if normalized == "application/pdf" else "unsupported"


def resolve_mount_preview_contract(  # noqa: PLR0913  # pylint: disable=too-many-arguments
    *,
    filename: str | None,
    mimetype: str | None,
    can_inline_preview: bool,
    is_wopi_supported: bool,
    can_download: bool,
    can_edit_text: bool,
    text_supported: bool,
) -> ResolvedMountPreviewContract:
    """Resolve the preview contract for one mount file without HTTP concerns."""

    normalized_mimetype = str(mimetype or "").split(";", 1)[0].strip().lower()
    preview_kind = classify_mount_preview_kind(
        mimetype=normalized_mimetype,
        is_wopi_supported=is_wopi_supported,
        can_inline_preview=can_inline_preview,
    )
    resolved_can_edit_text = False

    if text_supported:
        preview_kind = "wopi" if is_wopi_supported and should_prefer_wopi_text(filename) else "text"
        resolved_can_edit_text = preview_kind == "text" and can_edit_text
    elif (
        can_inline_preview
        and can_download
        and (
            is_archive_filename(filename) or normalized_mimetype in MOUNT_ARCHIVE_PREVIEW_MIMETYPES
        )
    ):
        preview_kind = "archive"

    has_inline_url = can_inline_preview and preview_kind in MOUNT_INLINE_PREVIEW_KINDS
    needs_stream_ticket = preview_kind in MOUNT_STREAMED_PREVIEW_KINDS
    stream_purpose = (
        "archive" if preview_kind == "archive" else "preview" if needs_stream_ticket else None
    )
    return ResolvedMountPreviewContract(
        preview_kind=preview_kind,
        is_wopi_supported=is_wopi_supported,
        can_download=can_download,
        can_edit_text=resolved_can_edit_text,
        has_inline_url=has_inline_url,
        needs_stream_ticket=needs_stream_ticket,
        stream_purpose=stream_purpose,
    )


def resolve_mount_provider_io_capabilities(
    *, provider, mount: dict[str, Any]
) -> MountProviderIoCapabilities:
    """Resolve provider IO/browser-stream support behind a stable contract."""

    stream_capabilities = get_browser_stream_capabilities(provider=provider, mount=mount)
    return MountProviderIoCapabilities(
        stat=hasattr(provider, "stat"),
        open_read=hasattr(provider, "open_read"),
        open_write=hasattr(provider, "open_write"),
        rename=hasattr(provider, "rename"),
        remove=hasattr(provider, "remove"),
        mkdirs=hasattr(provider, "mkdirs"),
        range_reads=stream_capabilities.supports_random_access,
        browser_stream_mode=stream_capabilities.browser_stream_mode,
        head_metadata=stream_capabilities.supports_head_metadata,
        stable_version=stream_capabilities.supports_stable_version,
    )


def resolve_mount_provider_context(
    *,
    mount: dict[str, Any],
    unavailable_spec: MountEndpointUnavailableSpec | None = None,
) -> ResolvedMountProviderContext:
    """Resolve provider + IO contract and optionally enforce a required IO guard."""

    provider = get_mount_provider(str(mount.get("provider") or ""))
    io_capabilities = resolve_mount_provider_io_capabilities(provider=provider, mount=mount)
    if unavailable_spec and not io_capabilities.supports(*unavailable_spec.required_io):
        raise MountEndpointUnavailableError(unavailable_spec)
    return ResolvedMountProviderContext(provider=provider, io_capabilities=io_capabilities)


def resolve_mount_wopi_target(
    *,
    mount: dict[str, Any],
    mount_id: str,
    normalized_path: str,
) -> ResolvedMountWopiTarget:
    """Resolve the shared mount-backed WOPI file contract."""

    _ = mount_id
    resolved = resolve_mount_provider_context(
        mount=mount,
        unavailable_spec=MOUNT_WOPI_UNAVAILABLE,
    )
    entry = resolved.provider.stat(mount=mount, normalized_path=normalized_path)

    if entry.entry_type != "file":
        raise MountEntryNotAFileError(normalized_path=normalized_path)

    return ResolvedMountWopiTarget(
        mount=mount,
        provider=resolved.provider,
        io_capabilities=resolved.io_capabilities,
        entry=entry,
        version=compute_mount_entry_version(entry),
    )


def build_mount_entry_abilities(
    *,
    entry: MountEntry,
    mount_capabilities: dict[str, bool],
    io_capabilities: MountProviderIoCapabilities,
    preview_candidate: bool,
    wopi_supported: bool,
) -> dict[str, bool]:
    """Compute entry abilities from normalized mount capabilities + provider IO support."""

    can_download = entry.entry_type == "file" and io_capabilities.open_read
    can_preview = (
        entry.entry_type == "file"
        and bool(mount_capabilities.get("mount.preview", False))
        and io_capabilities.open_read
        and (preview_candidate or wopi_supported)
    )
    can_upload = (
        entry.entry_type == "folder"
        and bool(mount_capabilities.get("mount.upload", False))
        and io_capabilities.supports("open_write", "rename", "remove")
    )
    can_create_folder = (
        entry.entry_type == "folder"
        and bool(mount_capabilities.get("mount.create_folder", False))
        and io_capabilities.supports("mkdirs", "stat")
    )
    can_move = (
        entry.normalized_path != "/"
        and bool(mount_capabilities.get("mount.move", False))
        and io_capabilities.supports("rename", "stat")
    )
    can_rename = (
        entry.normalized_path != "/"
        and bool(mount_capabilities.get("mount.rename", False))
        and io_capabilities.rename
    )
    can_destroy = (
        entry.normalized_path != "/"
        and bool(mount_capabilities.get("mount.delete", False))
        and io_capabilities.remove
    )
    can_duplicate = (
        entry.entry_type == "file"
        and bool(mount_capabilities.get("mount.duplicate", False))
        and io_capabilities.supports("stat", "open_read", "open_write", "rename", "remove")
    )
    can_wopi = (
        entry.entry_type == "file"
        and bool(mount_capabilities.get("mount.wopi", False))
        and io_capabilities.supports("open_read", "open_write")
        and wopi_supported
    )

    return {
        "children_list": entry.entry_type == "folder",
        "create_folder": can_create_folder,
        "move": can_move,
        "rename": can_rename,
        "destroy": can_destroy,
        "upload": can_upload,
        "duplicate": can_duplicate,
        "download": can_download,
        "preview": can_preview,
        "wopi": can_wopi,
        "share_link_create": bool(mount_capabilities.get("mount.share_link", False)),
    }
