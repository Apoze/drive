"""Short-lived browser stream access tokens for mount-backed files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from secrets import token_urlsafe

from django.conf import settings
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.core.cache import cache
from django.utils import timezone

from core.models import User
from core.mounts.paths import MountPathNormalizationError, normalize_mount_path


class MountStreamAccessError(Exception):
    """Base exception for mount browser-stream access errors."""


class MountStreamAccessNotFoundError(MountStreamAccessError):
    """Raised when a stream token cannot be resolved."""


class MountStreamAccessInvalidDataError(MountStreamAccessError):
    """Raised when cached stream-token data is invalid."""


class MountStreamAccessNotAllowed(MountStreamAccessError):
    """Raised when stream-token creation is not allowed."""


# pylint: disable=too-many-instance-attributes
@dataclass
class AccessUserMountStream:
    """Access context for a mount-backed browser stream URL."""

    mount_id: str
    normalized_path: str
    user: AbstractUser
    version: str
    filename: str
    content_type: str
    content_length: int | None
    disposition: str
    purpose: str
    supports_range: bool

    def to_dict(self) -> dict:
        """Serialize the access context for cache storage."""
        return {
            "mount_id": str(self.mount_id),
            "normalized_path": str(self.normalized_path),
            "user": str(self.user.id) if not self.user.is_anonymous else None,
            "version": str(self.version),
            "filename": str(self.filename),
            "content_type": str(self.content_type),
            "content_length": self.content_length,
            "disposition": str(self.disposition),
            "purpose": str(self.purpose),
            "supports_range": bool(self.supports_range),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AccessUserMountStream":
        """Deserialize the access context from cache storage."""
        try:
            mount_id_raw = data["mount_id"]
            normalized_path_raw = data["normalized_path"]
            user_raw = data["user"]
            version_raw = data["version"]
            filename_raw = data["filename"]
            content_type_raw = data["content_type"]
            content_length_raw = data["content_length"]
            disposition_raw = data["disposition"]
            purpose_raw = data["purpose"]
            supports_range_raw = data["supports_range"]
        except KeyError as error:
            raise MountStreamAccessInvalidDataError("Invalid data") from error

        if not isinstance(mount_id_raw, str) or not mount_id_raw.strip():
            raise MountStreamAccessInvalidDataError("Invalid data")

        if not isinstance(normalized_path_raw, str):
            raise MountStreamAccessInvalidDataError("Invalid data")
        try:
            normalized_path = normalize_mount_path(normalized_path_raw)
        except MountPathNormalizationError as error:
            raise MountStreamAccessInvalidDataError("Invalid data") from error

        if not isinstance(version_raw, str) or not version_raw:
            raise MountStreamAccessInvalidDataError("Invalid data")
        if not isinstance(filename_raw, str):
            raise MountStreamAccessInvalidDataError("Invalid data")
        if not isinstance(content_type_raw, str) or not content_type_raw:
            raise MountStreamAccessInvalidDataError("Invalid data")
        if disposition_raw not in {"inline", "attachment"}:
            raise MountStreamAccessInvalidDataError("Invalid data")
        if purpose_raw not in {"preview", "download", "archive"}:
            raise MountStreamAccessInvalidDataError("Invalid data")
        if content_length_raw is not None and (
            not isinstance(content_length_raw, int) or content_length_raw < 0
        ):
            raise MountStreamAccessInvalidDataError("Invalid data")
        if not isinstance(supports_range_raw, bool):
            raise MountStreamAccessInvalidDataError("Invalid data")

        try:
            user = User.objects.get(id=user_raw) if user_raw else AnonymousUser()
        except (User.DoesNotExist, TypeError, ValueError) as error:
            raise MountStreamAccessNotFoundError("Resource not found") from error

        return cls(
            mount_id=mount_id_raw.strip(),
            normalized_path=normalized_path,
            user=user,
            version=version_raw,
            filename=filename_raw,
            content_type=content_type_raw,
            content_length=content_length_raw,
            disposition=disposition_raw,
            purpose=purpose_raw,
            supports_range=supports_range_raw,
        )


@dataclass(frozen=True)
class NewMountStreamAccess:
    """Creation payload for a short-lived mount browser-stream ticket."""

    mount_id: str
    normalized_path: str
    user: AbstractUser
    version: str
    filename: str
    content_type: str
    content_length: int | None
    disposition: str
    purpose: str
    supports_range: bool


class MountStreamAccessService:
    """Service managing access tokens for mount-backed browser streams."""

    @staticmethod
    def generate_token() -> str:
        """Generate a random access token."""
        return token_urlsafe()

    def insert_new_access(self, payload: NewMountStreamAccess) -> tuple[str, int]:
        """Create a short-lived browser stream token bound to a mount entry."""
        if getattr(payload.user, "is_anonymous", True):
            raise MountStreamAccessNotAllowed()

        token = self.generate_token()
        access_user_mount = AccessUserMountStream(
            mount_id=str(payload.mount_id or "").strip(),
            normalized_path=normalize_mount_path(payload.normalized_path),
            user=payload.user,
            version=str(payload.version),
            filename=str(payload.filename or ""),
            content_type=str(payload.content_type or "application/octet-stream"),
            content_length=(payload.content_length if payload.content_length is not None else None),
            disposition=str(payload.disposition or "inline"),
            purpose=str(payload.purpose or "preview"),
            supports_range=bool(payload.supports_range),
        )
        token_eol = timezone.now() + timedelta(seconds=settings.MOUNT_STREAM_ACCESS_TOKEN_TIMEOUT)
        cache.set(
            token,
            access_user_mount.to_dict(),
            timeout=settings.MOUNT_STREAM_ACCESS_TOKEN_TIMEOUT,
        )
        return token, int(round(token_eol.timestamp())) * 1000

    def get_access_user_mount_stream(self, token: str) -> AccessUserMountStream:
        """Resolve a mount browser-stream token to its context."""
        data = cache.get(token)
        if data is None:
            raise MountStreamAccessNotFoundError("Resource not found")
        return AccessUserMountStream.from_dict(data)
