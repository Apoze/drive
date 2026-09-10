"""
Services for WOPI access
https://learn.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/rest/concepts#access-token
"""

from dataclasses import dataclass, field
from datetime import timedelta
from secrets import token_urlsafe
from uuid import UUID, uuid4

from django.conf import settings
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.core.cache import cache
from django.utils import timezone

from suite_identity.access import delegation_proof, validate_delegation

from core.models import Item, User
from core.mounts.paths import MountPathNormalizationError, normalize_mount_path


class AccessError(Exception):
    """Base exception for access errors."""


class AccessUserItemNotFoundError(AccessError):
    """Exception for when a user or item is not found."""


class AccessUserItemInvalidDataError(AccessError):
    """Exception for when a user or item has invalid data."""


class AccessUserItemNotAllowed(AccessError):
    """Exception for when a user is not allowed to access an item."""


class AccessUserMountEntryNotAllowed(AccessError):
    """Exception for when a user is not allowed to access a mount entry."""


@dataclass
class AccessUserItem:
    """Service for accessing a user item"""

    item: Item
    user: AbstractUser
    identity_proof: dict | None = None

    def to_dict(self):
        """Convert the access user item to a dictionary"""
        return {
            "item": str(self.item.id),
            "user": str(self.user.id) if not self.user.is_anonymous else None,
            **({"suite_identity": self.identity_proof} if self.identity_proof else {}),
            **(
                {
                    "storage_location": [
                        str(self.item.storage_backend_id),
                        str(self.item.storage_space_id),
                        self.item.storage_key_prefix,
                    ]
                }
                if self.item.storage_backend_id
                else {}
            ),
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Convert a dictionary to an access user item"""
        try:
            result = cls(
                item=Item.objects.get(id=UUID(data["item"])),
                user=User.objects.get(id=UUID(data["user"])) if data["user"] else AnonymousUser(),
                identity_proof=data.get("suite_identity"),
            )
            validate_delegation(result.user, result.identity_proof)
            if (
                result.item.storage_backend_id
                and data.get("storage_location") != result.to_dict()["storage_location"]
            ):
                raise AccessUserItemNotAllowed(
                    "This editing session belongs to an earlier storage location."
                )
            return result
        except (Item.DoesNotExist, User.DoesNotExist) as error:
            raise AccessUserItemNotFoundError("Resource not found") from error
        except (KeyError, ValueError) as error:
            raise AccessUserItemInvalidDataError("Invalid data") from error


class AccessUserItemService:
    """Service managing the access token for WOPI."""

    @staticmethod
    def generate_token():
        """Generate a random access token"""
        return token_urlsafe()

    def insert_new_access(
        self, item: Item, user: AbstractUser, ttl: int | None = None
    ) -> tuple[str, int]:
        """
        Insert a new access token for the user and item. Return an access_token and access_token_ttl
        access_token_ttl must be a timestamp in milliseconds.

        ttl overrides the default WOPI_ACCESS_TOKEN_TIMEOUT lifetime. Pass a short
        ttl for one-shot uses such as server-to-server conversion source download.
        """
        abilities = item.get_abilities(user)
        if not abilities["retrieve"]:
            raise AccessUserItemNotAllowed()
        effective_ttl = ttl if ttl is not None else settings.WOPI_ACCESS_TOKEN_TIMEOUT
        token = self.generate_token()
        access_user_item = AccessUserItem(
            item=item, user=user, identity_proof=delegation_proof(user)
        )
        token_eol = timezone.now() + timedelta(seconds=effective_ttl)
        cache.set(
            token,
            access_user_item.to_dict(),
            timeout=effective_ttl,
        )
        return token, int(round(token_eol.timestamp())) * 1000

    def get_access_user_item(self, token: str) -> AccessUserItem:
        """Get the access user item for the token"""
        data = cache.get(token)
        if data is None:
            raise AccessUserItemNotFoundError("Resource not found")
        return AccessUserItem.from_dict(data)


@dataclass
# Session identity, observed file metadata and fixed expiry travel together.
# pylint: disable-next=too-many-instance-attributes
class AccessUserMountEntry:
    """Access context for mount-backed WOPI operations."""

    mount_id: str
    normalized_path: str
    user: AbstractUser
    file_id: UUID
    observed_version: str = ""
    object_identity: str = ""
    expires_at: float = 0
    cache_key: str = field(default="", repr=False, compare=False)
    identity_proof: dict | None = None

    def to_dict(self) -> dict:
        """Serialize the access context for cache storage."""
        return {
            "mount_id": str(self.mount_id),
            "normalized_path": str(self.normalized_path),
            "user": str(self.user.id) if not self.user.is_anonymous else None,
            "file_id": str(self.file_id),
            **({"suite_identity": self.identity_proof} if self.identity_proof else {}),
            **(
                {
                    "observed_version": self.observed_version,
                    "object_identity": self.object_identity,
                    "expires_at": self.expires_at,
                }
                if self.observed_version
                else {}
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AccessUserMountEntry":
        """Deserialize the access context from cache storage."""
        try:
            mount_id_raw = data["mount_id"]
            normalized_path_raw = data["normalized_path"]
            file_id_raw = data["file_id"]
            user_raw = data["user"]
        except KeyError as error:
            raise AccessUserItemInvalidDataError("Invalid data") from error

        if not isinstance(mount_id_raw, str) or not mount_id_raw.strip():
            raise AccessUserItemInvalidDataError("Invalid data")

        if not isinstance(normalized_path_raw, str):
            raise AccessUserItemInvalidDataError("Invalid data")

        try:
            normalized_path = normalize_mount_path(normalized_path_raw)
        except MountPathNormalizationError as error:
            raise AccessUserItemInvalidDataError("Invalid data") from error

        try:
            file_id = UUID(str(file_id_raw))
        except (TypeError, ValueError) as error:
            raise AccessUserItemInvalidDataError("Invalid data") from error

        try:
            user = User.objects.get(id=UUID(str(user_raw))) if user_raw else AnonymousUser()
        except (User.DoesNotExist, ValueError, TypeError) as error:
            raise AccessUserItemNotFoundError("Resource not found") from error

        validate_delegation(user, data.get("suite_identity"))
        return cls(
            mount_id=mount_id_raw.strip(),
            normalized_path=normalized_path,
            user=user,
            file_id=file_id,
            observed_version=data.get("observed_version", ""),
            object_identity=data.get("object_identity", ""),
            expires_at=data.get("expires_at", 0),
            identity_proof=data.get("suite_identity"),
        )


class AccessUserMountEntryService:
    """Service managing access tokens for mount-backed WOPI."""

    @staticmethod
    def generate_token() -> str:
        """Generate a random access token."""
        return token_urlsafe()

    # The issuer already resolved the native metadata; avoid a second storage read.
    # pylint: disable-next=too-many-arguments
    def insert_new_access(
        self,
        *,
        mount_id: str,
        normalized_path: str,
        user: AbstractUser,
        observed_version: str = "",
        object_identity: str = "",
    ) -> tuple[str, int, UUID]:
        """Create a short-lived WOPI access token bound to a mount entry."""
        if getattr(user, "is_anonymous", True):
            raise AccessUserMountEntryNotAllowed()

        token = self.generate_token()
        file_id = uuid4()
        token_eol = timezone.now() + timedelta(seconds=settings.WOPI_ACCESS_TOKEN_TIMEOUT)
        access_user_mount = AccessUserMountEntry(
            mount_id=str(mount_id or "").strip(),
            normalized_path=normalize_mount_path(normalized_path),
            user=user,
            file_id=file_id,
            observed_version=observed_version,
            object_identity=object_identity or "",
            expires_at=token_eol.timestamp(),
            identity_proof=delegation_proof(user),
        )
        cache.set(
            token,
            access_user_mount.to_dict(),
            timeout=settings.WOPI_ACCESS_TOKEN_TIMEOUT,
        )
        return token, int(round(token_eol.timestamp())) * 1000, file_id

    def get_access_user_mount_entry(self, token: str) -> AccessUserMountEntry:
        """Resolve a mount-backed access token to its context."""
        data = cache.get(token)
        if data is None:
            raise AccessUserItemNotFoundError("Resource not found")
        result = AccessUserMountEntry.from_dict(data)
        result.cache_key = token
        return result

    @staticmethod
    def advance(context, *, version, object_identity):
        """Follow our own atomic save without extending the session's original lifetime."""
        if not context.cache_key or not context.observed_version:
            return
        remaining = int(context.expires_at - timezone.now().timestamp())
        if remaining <= 0:
            return
        current = cache.get(context.cache_key)
        if not current or current.get("observed_version") != context.observed_version:
            return
        context.observed_version = version
        context.object_identity = object_identity or ""
        cache.set(context.cache_key, context.to_dict(), timeout=remaining)
