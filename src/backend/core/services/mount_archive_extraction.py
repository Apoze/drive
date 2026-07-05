"""Preflight helpers for mount archive extraction jobs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, NoReturn

from core import models
from core.entitlements import get_entitlements_backend
from core.mounts.paths import (
    MountPathNormalizationError,
    normalize_mount_path,
)
from core.mounts.providers.base import MountEntry, MountProviderError
from core.mounts.registry import get_mount_provider
from core.services.mount_capabilities import resolve_mount_provider_io_capabilities
from core.services.mount_security import (
    MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT_PUBLIC_MESSAGE,
    mounts_safe_for_archive_extract,
)

MountArchiveExtractionErrorKind = Literal[
    "permission_denied",
    "validation_error",
    "not_found",
]


@dataclass(frozen=True, slots=True)
class MountArchiveExtractionStartRequest:
    """Validated request payload for mount archive extraction preflight."""

    archive_item_id: str
    destination_path: str
    mode: str
    selection_paths: list[str]


@dataclass(frozen=True, slots=True)
class ResolvedMountArchiveExtractionJob:
    """Resolved job payload after mount archive extraction preflight."""

    archive_item_id: str
    mount_id: str
    destination_path: str
    user_id: str
    mode: str
    selection_paths: list[str]

    def as_task_kwargs(self) -> dict[str, object]:
        """Return the stable Celery/start payload for one extraction job."""

        return {
            "archive_item_id": self.archive_item_id,
            "mount_id": self.mount_id,
            "destination_path": self.destination_path,
            "user_id": self.user_id,
            "mode": self.mode,
            "selection_paths": list(self.selection_paths),
        }


@dataclass(frozen=True, slots=True)
class ResolvedMountArchiveDestination:
    """Resolved destination mount context for archive extraction."""

    mount: dict
    provider: Any
    normalized_destination_path: str
    destination_entry: MountEntry


@dataclass(frozen=True, slots=True)
class MountArchiveExtractionPreflightError(Exception):
    """Internal preflight error translated to DRF at the API seam."""

    error_kind: MountArchiveExtractionErrorKind
    public_message: str
    public_code: str | None = None


def _raise_preflight_error(
    *,
    error_kind: MountArchiveExtractionErrorKind,
    public_message: str,
    public_code: str | None = None,
) -> NoReturn:
    raise MountArchiveExtractionPreflightError(
        error_kind=error_kind,
        public_message=public_message,
        public_code=public_code,
    )


def ensure_mount_archive_extract_hardening() -> None:
    """Fail closed when mount archive extraction hardening is disabled."""

    if not mounts_safe_for_archive_extract():
        _raise_preflight_error(
            error_kind="permission_denied",
            public_message=MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT_PUBLIC_MESSAGE,
            public_code="mount.archive_extract.unsafe",
        )


def validate_mount_archive_source_item(
    *,
    user,
    archive_item: models.Item,
) -> models.Item:
    """Validate one source archive item against the shared extraction contract."""

    if archive_item.type != models.ItemTypeChoices.FILE:
        _raise_preflight_error(
            error_kind="validation_error",
            public_message="Item must be a file.",
            public_code="item.not_a_file",
        )

    if archive_item.effective_upload_state() != models.ItemUploadStateChoices.READY:
        _raise_preflight_error(
            error_kind="validation_error",
            public_message="Item is not ready.",
            public_code="item.not_ready",
        )

    if archive_item.upload_state == models.ItemUploadStateChoices.SUSPICIOUS:
        _raise_preflight_error(
            error_kind="permission_denied",
            public_message="Suspicious items cannot be extracted.",
            public_code="archive.extract.suspicious",
        )

    if not archive_item.get_abilities(user).get("retrieve", False):
        _raise_preflight_error(
            error_kind="permission_denied",
            public_message="Not allowed.",
            public_code="item.retrieve.forbidden",
        )

    if not bool(str(archive_item.filename or "").lower().endswith(".zip")):
        _raise_preflight_error(
            error_kind="validation_error",
            public_message="Unsupported archive format for mount extraction.",
            public_code="archive.extract.unsupported_for_mount",
        )

    return archive_item


def get_mount_archive_source_item_or_error(*, archive_item_id: str) -> models.Item:
    """Load one source archive item or raise the stable preflight not-found error."""

    try:
        return models.Item.objects.get(pk=archive_item_id)
    except models.Item.DoesNotExist:
        _raise_preflight_error(
            error_kind="not_found",
            public_message="Item not found.",
            public_code="item.not_found",
        )


def resolve_mount_archive_destination(
    *,
    mount: dict,
    destination_path: str,
) -> ResolvedMountArchiveDestination:
    """Resolve and validate the destination mount folder for extraction."""

    provider = get_mount_provider(str(mount.get("provider") or ""))
    io = resolve_mount_provider_io_capabilities(provider=provider, mount=mount)
    if not io.supports("stat", "open_write", "rename", "remove", "mkdirs"):
        _raise_preflight_error(
            error_kind="validation_error",
            public_message="Extraction is not available for this mount.",
            public_code="mount.archive_extract.unavailable",
        )

    try:
        normalized_destination_path = normalize_mount_path(destination_path)
    except MountPathNormalizationError:
        _raise_preflight_error(
            error_kind="validation_error",
            public_message="Invalid mount path.",
            public_code="mount.path.invalid",
        )

    try:
        destination_entry = provider.stat(mount=mount, normalized_path=normalized_destination_path)
    except MountProviderError as exc:
        if exc.public_code == "mount.path.not_found":
            _raise_preflight_error(
                error_kind="not_found",
                public_message="Mount path not found.",
                public_code="mount.path.not_found",
            )
        _raise_preflight_error(
            error_kind="validation_error",
            public_message=exc.public_message,
            public_code=exc.public_code,
        )

    if destination_entry.entry_type != "folder":
        _raise_preflight_error(
            error_kind="validation_error",
            public_message="Mount path is not a folder.",
            public_code="mount.path.not_a_folder",
        )

    return ResolvedMountArchiveDestination(
        mount=mount,
        provider=provider,
        normalized_destination_path=normalized_destination_path,
        destination_entry=destination_entry,
    )


def resolve_mount_archive_extraction_job(
    *,
    user,
    mount_id: str,
    mount: dict,
    start_request: MountArchiveExtractionStartRequest,
) -> ResolvedMountArchiveExtractionJob:
    """Resolve the preflight contract for one mount archive extraction job."""

    ensure_mount_archive_extract_hardening()

    entitlements_backend = get_entitlements_backend()
    can_upload = entitlements_backend.can_upload(user)
    if not can_upload.get("result"):
        _raise_preflight_error(
            error_kind="permission_denied",
            public_message=can_upload.get("message", "Upload not allowed."),
        )

    archive_item = get_mount_archive_source_item_or_error(
        archive_item_id=start_request.archive_item_id,
    )
    validate_mount_archive_source_item(
        user=user,
        archive_item=archive_item,
    )
    destination = resolve_mount_archive_destination(
        mount=mount,
        destination_path=start_request.destination_path,
    )

    return ResolvedMountArchiveExtractionJob(
        archive_item_id=start_request.archive_item_id,
        mount_id=mount_id,
        destination_path=destination.normalized_destination_path,
        user_id=str(user.id),
        mode=start_request.mode,
        selection_paths=list(start_request.selection_paths),
    )
