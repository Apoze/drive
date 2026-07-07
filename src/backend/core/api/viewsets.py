"""API endpoints"""
# pylint: disable=too-many-lines

import contextlib
import json
import logging
import mimetypes
import os
import posixpath
import re
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import parse_qs, quote, unquote, urlparse
from uuid import UUID

from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db import models as db
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce
from django.http import HttpResponse, StreamingHttpResponse
from django.middleware.csrf import get_token
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.text import capfirst, slugify
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_exempt

import rest_framework as drf
from botocore.exceptions import ClientError
from corsheaders.middleware import (
    ACCESS_CONTROL_ALLOW_METHODS,
    ACCESS_CONTROL_ALLOW_ORIGIN,
)
from lasuite.drf.models.choices import (
    PRIVILEGED_ROLES,
    LinkReachChoices,
    get_equivalent_link_definition,
)
from lasuite.malware_detection import malware_detection
from lasuite.oidc_login.decorators import refresh_oidc_access_token
from rest_framework import response as drf_response
from rest_framework import status, viewsets
from rest_framework.exceptions import APIException
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from rest_framework_api_key.permissions import HasAPIKey

from core import enums, models
from core.archive.extract_mount import (
    get_mount_archive_extraction_job_status,
    set_mount_archive_extraction_job_status,
    start_mount_archive_extraction_job,
)
from core.entitlements import get_entitlements_backend
from core.mounts.paths import (
    MountPathNormalizationError,
    normalize_mount_path,
    parent_mount_path,
)
from core.mounts.providers.base import (
    MountEntry,
    MountProviderError,
)
from core.mounts.registry import get_mount_provider
from core.services.item_exports import (
    build_zip_stream,
    export_descendants,
    sanitize_archive_component,
)
from core.services.mount_archive_extraction import (
    MountArchiveExtractionPreflightError,
    MountArchiveExtractionStartRequest,
    resolve_mount_archive_extraction_job,
)
from core.services.mount_capabilities import (
    MOUNT_CREATE_FOLDER_UNAVAILABLE,
    MOUNT_DELETE_UNAVAILABLE,
    MOUNT_DOWNLOAD_UNAVAILABLE,
    MOUNT_DUPLICATE_UNAVAILABLE,
    MOUNT_MOVE_UNAVAILABLE,
    MOUNT_PREVIEW_UNAVAILABLE,
    MOUNT_RENAME_UNAVAILABLE,
    MOUNT_STREAM_UNAVAILABLE,
    MOUNT_TEXT_UNAVAILABLE,
    MOUNT_UPLOAD_UNAVAILABLE,
    MountEndpointUnavailableError,
    MountEndpointUnavailableSpec,
    MountEntryNotAFileError,
    MountProviderIoCapabilities,
    build_mount_entry_abilities,
    classify_mount_preview_kind,
    normalize_mount_capabilities,
    resolve_enabled_mount,
    resolve_mount_preview_contract,
    resolve_mount_provider_context,
    resolve_mount_provider_io_capabilities,
    resolve_mount_wopi_target,
)
from core.services.mount_stream_access import (
    MountStreamAccessNotAllowed,
    MountStreamAccessNotFoundError,
    MountStreamAccessService,
    NewMountStreamAccess,
)
from core.services.odf_templates import build_minimal_odf_template_bytes
from core.services.ooxml_templates import build_minimal_ooxml_template_bytes
from core.services.s3_streaming import stream_to_s3_object
from core.services.sdk_relay import SDKRelayManager
from core.services.search_indexers import (
    get_file_indexer,
    get_visited_items_ids_of,
)
from core.storage import get_storage_compute_backend
from core.tasks.archive import extract_archive_to_mount_task
from core.tasks.item import duplicate_file, process_item_purge, rename_file
from core.utils.analytics import posthog_capture
from core.utils.keyed_hash import hmac_sha256_16
from core.utils.no_leak import safe_str_hash
from core.utils.public_url import join_public_url
from core.utils.share_links import validate_item_share_token
from wopi.conversion import exceptions as conversion_exceptions
from wopi.conversion.services import prepare_conversion
from wopi.services import access as access_service
from wopi.tasks.conversion import convert_file
from wopi.utils import (
    compute_mount_entry_version,
    get_wopi_client_config,
    get_wopi_client_config_for_filename,
    is_wopi_backend_supported,
    is_wopi_deployment_enabled,
    is_wopi_discovery_configured,
    resolve_wopi_init_launch,
)

from . import permissions, serializers, utils
from .filters import (
    ItemFilter,
    ItemOrdering,
    ListItemFilter,
    OrganizationUsageMetricFilter,
    SearchItemFilter,
    UsageMetricAccountTypeChoices,
    UsageMetricFilter,
)
from .serializers_mount_archive_extraction import StartMountArchiveExtractionSerializer
from .serializers_mounts import (
    MountBrowseResponseSerializer,
    MountCreateFolderRequestSerializer,
    MountEntrySerializer,
    MountMoveRequestSerializer,
    MountPreviewInfoSerializer,
    MountRenameRequestSerializer,
    MountShareLinkCreateRequestSerializer,
    MountShareLinkCreateResponseSerializer,
    MountShareLinkPublicBrowseResponseSerializer,
    MountShareLinkPublicEntrySerializer,
    MountStreamTicketRequestSerializer,
    MountStreamTicketResponseSerializer,
)
from .serializers_share_links import PublicShareItemSerializer

logger = logging.getLogger(__name__)

ITEM_FOLDER = "item"
UUID_REGEX = r"[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}"
FILE_EXT_REGEX = '[^.\\/:*?&"<>|\r\n]+'
MEDIA_STORAGE_URL_PATTERN = re.compile(
    f"{settings.MEDIA_URL:s}(?P<preview>preview/)?"
    f"(?P<key>{ITEM_FOLDER:s}/(?P<pk>{UUID_REGEX:s})/.*{FILE_EXT_REGEX:s})$"
)

MAX_TEXT_PREVIEW_BYTES = 500 * 1024
TEXT_SNIFF_PREFIX_BYTES = 32 * 1024

TEXT_LIKE_MIMETYPES_ALLOWLIST = frozenset(
    {
        "application/json",
        "application/xml",
        "application/x-yaml",
        "application/yaml",
        "application/toml",
        "application/x-ini",
    }
)

GENERIC_MIMETYPES_FOR_TEXT_SNIFF = frozenset(
    {
        "",
        "application/octet-stream",
        "binary/octet-stream",
        "application/x-empty",
        "application/unknown",
        "application/x-unknown",
    }
)

TEXT_EXTENSIONS_DENYLIST = frozenset(
    {
        # High-risk / typically-binary extensions: extension alone must never force "text".
        "sys",
        "exe",
        "dll",
        "bin",
        "dat",
        "so",
        "dylib",
    }
)

TEXT_EXTENSIONS_WHITELIST = frozenset(
    {
        "txt",
        "md",
        "log",
        "csv",
        "tsv",
        "json",
        "yaml",
        "yml",
        "xml",
        "ini",
        "conf",
        "env",
        "inf",
        "py",
        "js",
        "jsx",
        "ts",
        "tsx",
        "sql",
        "sh",
        "bash",
        "zsh",
        "fish",
        "toml",
        "properties",
        "gitignore",
        "dockerfile",
        "makefile",
    }
)

ARCHIVE_CONTAINER_EXTENSIONS = frozenset({"zip", "tar"})
ARCHIVE_MULTI_EXTENSIONS = (
    "tar.gz",
    "tgz",
    "tar.bz2",
    "tbz",
    "tbz2",
    "tar.xz",
    "txz",
)
ARCHIVE_SINGLE_COMPRESSION_EXTENSIONS = frozenset({"gz", "bz2", "xz"})


def _decode_text_bytes_best_effort(data: bytes, *, truncated: bool) -> tuple[str, str, bool]:
    """
    Decode bytes for text preview.

    Returns: (text, encoding, editable)
    - editable is True only when the bytes are UTF-8 (optionally with UTF-8 BOM).
    - Non-UTF-8 decodes are best-effort and must be treated as read-only.
    """
    if not data:
        return "", "utf-8", True

    if data.startswith(b"\xef\xbb\xbf"):
        errors = "replace" if truncated else "strict"
        return data.decode("utf-8-sig", errors=errors), "utf-8", True

    if data.startswith(b"\xff\xfe"):
        payload = data[2:]
        if len(payload) % 2 == 1:
            payload = payload[:-1]
        return payload.decode("utf-16le", errors="replace"), "utf-16le", False

    if data.startswith(b"\xfe\xff"):
        payload = data[2:]
        if len(payload) % 2 == 1:
            payload = payload[:-1]
        return payload.decode("utf-16be", errors="replace"), "utf-16be", False

    try:
        errors = "replace" if truncated else "strict"
        return data.decode("utf-8", errors=errors), "utf-8", True
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), "cp1252", False


def _normalize_if_match_tag(v: str) -> str:
    v = v.strip()
    if v.startswith("W/"):
        v = v[2:].strip()
    return v


def _should_prefer_wopi_text(filename: str | None) -> bool:
    lower = str(filename or "").strip().lower()
    if "." not in lower:
        return False
    return lower.rsplit(".", 1)[-1] == "txt"


def _is_archive_filename(filename: str | None) -> bool:
    lower = str(filename or "").strip().lower()
    if not lower:
        return False
    for ext in ARCHIVE_MULTI_EXTENSIONS:
        if lower.endswith(f".{ext}"):
            return True
    if "." not in lower:
        return False
    ext = lower.rsplit(".", 1)[-1]
    if ext in ARCHIVE_CONTAINER_EXTENSIONS:
        return True
    if ext in ARCHIVE_SINGLE_COMPRESSION_EXTENSIONS:
        return False
    return False


def _guess_mimetype_from_filename(filename: str | None) -> str:
    guessed, _encoding = mimetypes.guess_type(str(filename or ""), strict=False)
    return str(guessed or "").split(";", 1)[0].strip().lower()


def _is_mount_filename_preview_candidate(filename: str | None) -> bool:
    lower = str(filename or "").strip().lower()
    if not lower:
        return False
    if _is_archive_filename(lower) or _should_prefer_wopi_text(lower):
        return True

    guessed = _guess_mimetype_from_filename(lower)
    direct_preview_mimetypes = (
        guessed == "application/pdf"
        or guessed.startswith("image/")
        or guessed.startswith("video/")
        or guessed.startswith("audio/")
        or guessed.startswith("text/")
        or guessed in TEXT_LIKE_MIMETYPES_ALLOWLIST
    )
    if direct_preview_mimetypes:
        return True

    text_key = lower.rsplit(".", 1)[-1] if "." in lower else lower
    return text_key in TEXT_EXTENSIONS_WHITELIST and text_key not in TEXT_EXTENSIONS_DENYLIST


class _PreconditionFailed(APIException):
    status_code = 412
    default_code = "precondition_failed"


class _MountUploadTooLarge(Exception):
    """Internal sentinel for deterministic upload abort (size limit)."""


class _MountUploadTimeout(Exception):
    """Internal sentinel for deterministic upload abort (time limit)."""


@dataclass(frozen=True)
class MountResolvedEntry:
    """Resolved mount file target used by preview and stream helpers."""

    provider: object
    mount: dict
    normalized_path: str
    io: MountProviderIoCapabilities
    entry: MountEntry


@dataclass(frozen=True)
class MountResolvedReadMetadata:
    """Resolved read metadata for one mount file."""

    target: MountResolvedEntry
    head: bytes
    mimetype: str


@dataclass(frozen=True)
class MountStreamOptions:  # pylint: disable=too-many-instance-attributes
    """HTTP response options for a mount-backed browser stream."""

    content_type: str
    disposition: str
    supports_range: bool
    range_header: str
    method: str
    etag: str | None = None
    cache_control: str | None = "private, no-store, no-transform"
    include_etag: bool = True
    include_last_modified: bool = True
    invalid_range_response: str = "plain"


@dataclass(frozen=True)
class MountStreamTicketSpec:
    """Logical intent for a mount-backed browser stream ticket."""

    disposition: str
    purpose: str
    content_type: str


# pylint: disable=too-many-ancestors


class MountShareLinkGone(APIException):
    """Public mount share link is known but no longer resolvable (410 Gone)."""

    status_code = 410
    default_detail = "Link expired or target moved."
    default_code = "mount.share_link.gone"


class NestedGenericViewSet(viewsets.GenericViewSet):
    """
    A generic Viewset aims to be used in a nested route context.
    e.g: `/api/v1.0/resource_1/<resource_1_pk>/resource_2/<resource_2_pk>/`

    It allows to define all url kwargs and lookup fields to perform the lookup.
    """

    lookup_fields: list[str] = ["pk"]
    lookup_url_kwargs: list[str] = []

    def __getattribute__(self, item):
        """
        This method is overridden to allow to get the last lookup field or lookup url kwarg
        when accessing the `lookup_field` or `lookup_url_kwarg` attribute. This is useful
        to keep compatibility with all methods used by the parent class `GenericViewSet`.
        """
        if item in ["lookup_field", "lookup_url_kwarg"]:
            return getattr(self, item + "s", [None])[-1]

        return super().__getattribute__(item)

    def get_queryset(self):
        """
        Get the list of items for this view.

        `lookup_fields` attribute is enumerated here to perform the nested lookup.
        """
        queryset = super().get_queryset()

        # The last lookup field is removed to perform the nested lookup as it corresponds
        # to the object pk, it is used within get_object method.
        lookup_url_kwargs = (
            self.lookup_url_kwargs[:-1] if self.lookup_url_kwargs else self.lookup_fields[:-1]
        )

        filter_kwargs = {}
        for index, lookup_url_kwarg in enumerate(lookup_url_kwargs):
            if lookup_url_kwarg not in self.kwargs:
                raise KeyError(
                    f"Expected view {self.__class__.__name__} to be called with a URL "
                    f'keyword argument named "{lookup_url_kwarg}". Fix your URL conf, or '
                    "set the `.lookup_fields` attribute on the view correctly."
                )

            filter_kwargs.update({self.lookup_fields[index]: self.kwargs[lookup_url_kwarg]})

        return queryset.filter(**filter_kwargs)


class SerializerPerActionMixin:
    """
    A mixin to allow to define serializer classes for each action.

    This mixin is useful to avoid to define a serializer class for each action in the
    `get_serializer_class` method.

    Example:
    ```
    class MyViewSet(SerializerPerActionMixin, viewsets.GenericViewSet):
        serializer_class = MySerializer
        list_serializer_class = MyListSerializer
        retrieve_serializer_class = MyRetrieveSerializer
    ```
    """

    def get_serializer_class(self):
        """
        Return the serializer class to use depending on the action.
        """
        if serializer_class := getattr(self, f"{self.action}_serializer_class", None):
            return serializer_class
        return super().get_serializer_class()


class Pagination(drf.pagination.PageNumberPagination):
    """Pagination to display no more than 100 objects per page sorted by creation date."""

    ordering = "-created_on"
    max_page_size = settings.MAX_PAGE_SIZE
    page_size_query_param = "page_size"


class UserListThrottleBurst(UserRateThrottle):
    """Throttle for the user list endpoint."""

    scope = "user_list_burst"


class UserListThrottleSustained(UserRateThrottle):
    """Throttle for the user list endpoint."""

    scope = "user_list_sustained"


class UserViewSet(
    SerializerPerActionMixin,
    drf.mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
    drf.mixins.ListModelMixin,
):
    """User ViewSet"""

    permission_classes = [permissions.IsSelf]
    queryset = models.User.objects.all().filter(is_active=True)
    serializer_class = serializers.UserSerializer
    get_me_serializer_class = serializers.UserMeSerializer
    contacts_serializer_class = serializers.UserLightSerializer
    pagination_class = None
    throttle_classes = []

    def get_throttles(self):
        self.throttle_classes = []
        if self.action in {"list", "contacts"}:
            self.throttle_classes = [UserListThrottleBurst, UserListThrottleSustained]

        return super().get_throttles()

    def get_queryset(self):
        """
        Limit listed users by querying the email field with a trigram similarity
        search if a query is provided.
        Limit listed users by excluding users already in the item if a item_id
        is provided.
        """
        queryset = self.queryset

        if self.action != "list":
            return queryset

        # Exclude all users already in the given item
        if item_id := self.request.query_params.get("item_id", ""):
            queryset = queryset.exclude(itemaccess__item_id=item_id)

        if not (query := self.request.query_params.get("q", "")) or len(query) < 5:
            return queryset.none()

        # For emails, match emails by Levenstein distance to prevent typing errors
        if "@" in query:
            return (
                queryset.annotate(distance=RawSQL("levenshtein(email::text, %s::text)", (query,)))
                .filter(distance__lte=3)
                .order_by("distance", "email")[: settings.API_USERS_LIST_LIMIT]
            )

        # Use trigram similarity for non-email-like queries
        # For performance reasons we filter first by similarity, which relies on an
        # index, then only calculate precise similarity scores for sorting purposes
        return (
            queryset.filter(email__trigram_word_similar=query)
            .annotate(similarity=TrigramSimilarity("email", query))
            .filter(similarity__gt=0.2)
            .order_by("-similarity", "email")[: settings.API_USERS_LIST_LIMIT]
        )

    @drf.decorators.action(
        detail=False,
        methods=["get"],
        url_name="me",
        url_path="me",
    )
    def get_me(self, request):
        """
        Return information on currently logged user
        """
        context = {"request": request}
        return drf.response.Response(self.get_serializer(request.user, context=context).data)

    @drf.decorators.action(detail=False, methods=["get"], url_path="contacts")
    def contacts(self, request):
        """
        Return users involved in visible sharing with the current user.

        Contacts either hold an access on a visible item or created a visible
        item. The base item set is restricted to live items the current user can
        access directly or through a team.
        """
        user = request.user
        shared_items = models.Item.objects.filter(
            db.Q(accesses__user=user) | db.Q(accesses__team__in=user.teams),
            hard_deleted_at__isnull=True,
            ancestors_deleted_at__isnull=True,
        )

        shared_with = db.Q(itemaccess__item_id__in=shared_items.values("pk"))
        shared_by = db.Q(pk__in=shared_items.values("creator_id"))
        created_shared = db.Q(items_created__in=shared_items)
        frequency = db.Count("itemaccess", filter=shared_with) + db.Count(
            "items_created", filter=created_shared
        )

        contacts = (
            models.User.objects.filter(is_active=True)
            .filter(shared_with | shared_by)
            .exclude(pk=user.pk)
            .annotate(frequency=frequency)
        )

        if query := request.query_params.get("q", ""):
            if "@" in query:
                contacts = contacts.annotate(
                    distance=RawSQL("levenshtein(email::text, %s::text)", (query,))
                ).filter(distance__lte=3)
                ordering = ("distance", "email")
            else:
                contacts = (
                    contacts.filter(email__trigram_word_similar=query)
                    .annotate(similarity=TrigramSimilarity("email", query))
                    .filter(similarity__gt=0.2)
                )
                ordering = ("-similarity", "email")
        else:
            ordering = ("-frequency", "email")

        contacts = contacts.order_by(*ordering)[: settings.API_USERS_LIST_LIMIT]

        return drf.response.Response(self.get_serializer(contacts, many=True).data)


class ItemMetadata(drf.metadata.SimpleMetadata):
    """Custom metadata class to add information"""

    def determine_metadata(self, request, view):
        """Add language choices only for the list endpoint."""
        simple_metadata = super().determine_metadata(request, view)

        if request.path.endswith("/items/"):
            simple_metadata["actions"]["POST"]["language"] = {
                "choices": [
                    {"value": code, "display_name": name}
                    for code, name in enums.ALL_LANGUAGES.items()
                ]
            }
        return simple_metadata


# pylint: disable=too-many-public-methods
class ItemViewSet(
    SerializerPerActionMixin,
    drf.mixins.CreateModelMixin,
    drf.mixins.DestroyModelMixin,
    drf.mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    ItemViewSet API.

    This view set provides CRUD operations and additional actions for managing items.
    Supports filtering, ordering, and annotations for enhanced querying capabilities.

    ### API Endpoints:
    1. **List**: Retrieve a paginated list of items.
       Example: GET /items/?page=2
    2. **Retrieve**: Get a specific item by its ID.
       Example: GET /items/{id}/
    3. **Create**: Create a new item.
       Example: POST /items/
    4. **Update**: Update a item by its ID.
       Example: PUT /items/{id}/
    5. **Delete**: Soft delete a item by its ID.
       Example: DELETE /items/{id}/

    ### Additional Actions:
    1. **Trashbin**: List soft deleted items for a item owner
        Example: GET /items/{id}/trashbin/

    2. **Children**: List or create child items.
        Example: GET, POST /items/{id}/children/

    3. **Favorite**: Get list of favorite items for a user. Mark or unmark
        a item as favorite.
        Examples:
        - GET /items/favorite/
        - POST, DELETE /items/{id}/favorite/

    4. **Link Configuration**: Update item link configuration.
        Example: PUT /items/{id}/link-configuration/

    5. **Media Auth**: Authorize access to item media.
        Example: GET /items/media-auth/

    ### Ordering: created_at, updated_at, is_favorite, size, title, type,
    creator__full_name

        Example:
        - Ascending: GET /api/v1.0/items/?ordering=created_at
        - Desceding: GET /api/v1.0/items/?ordering=-title

    ### Filtering:
        - `is_creator_me=true`: Returns items created by the current user.
        - `is_creator_me=false`: Returns items created by other users.
        - `is_favorite=true`: Returns items marked as favorite by the current user
        - `is_favorite=false`: Returns items not marked as favorite by the current user
        - `title=hello`: Returns items which title contains the "hello" string

        Example:
        - GET /api/v1.0/items/?is_creator_me=true&is_favorite=true
        - GET /api/v1.0/items/?is_creator_me=false&title=hello

    ### Annotations:
    1. **is_favorite**: Indicates whether the item is marked as favorite by the current user.
    2. *`*user_roles**: Roles the current user has on the item or its ancestors.

    ### Notes:
    - Only the highest ancestor in a item hierarchy is shown in list views.
    - Implements soft delete logic to retain item tree structures.
    """

    metadata_class = ItemMetadata
    ordering = ["-updated_at"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "is_favorite",
        "size",
        "title",
        "type",
        "creator__full_name",
    ]
    pagination_class = Pagination
    permission_classes = [
        permissions.ItemPermission,
    ]
    queryset = models.Item.objects.filter(hard_deleted_at__isnull=True)
    serializer_class = serializers.ItemSerializer
    list_serializer_class = serializers.ListItemSerializer
    trashbin_serializer_class = serializers.ListItemSerializer
    children_serializer_class = serializers.ListItemSerializer
    create_serializer_class = serializers.CreateItemSerializer
    tree_serializer_class = serializers.ListItemSerializer
    search_serializer_class = serializers.SearchItemSerializer
    breadcrumb_serializer_class = serializers.BreadcrumbItemSerializer
    recents_serializer_class = serializers.ListItemLightSerializer
    favorite_list_serializer_class = serializers.ListItemLightSerializer

    def _apply_deterministic_ordering(self, queryset):
        """
        Apply DRF ordering and always add a stable tie-breaker.

        Deterministic ordering is required for stable pagination boundaries.
        """
        ordering_filter = ItemOrdering()
        ordering = ordering_filter.get_ordering(self.request, queryset, self)
        if not ordering:
            ordering = getattr(self, "ordering", None) or []
        ordering = list(ordering)
        if "id" not in {field.lstrip("-") for field in ordering}:
            ordering.append("id")
        return queryset.order_by(*ordering)

    def _filter_suspicious_items(self, queryset, user):
        """
        Filter out items with SUSPICIOUS upload_state for non-creators.

        Args:
            queryset: The queryset to filter
            user: The current user

        Returns:
            Filtered queryset excluding suspicious items from non-creators
        """
        # For authenticated users, exclude suspicious items they didn't create
        # For unauthenticated users, exclude all suspicious items
        if user.is_authenticated:
            return queryset.exclude(
                db.Q(upload_state=models.ItemUploadStateChoices.SUSPICIOUS) & ~db.Q(creator=user)
            )

        return queryset.exclude(upload_state=models.ItemUploadStateChoices.SUSPICIOUS)

    def _exclude_pending_items(self, queryset):
        """Exclude items with PENDING upload_state from listing views."""
        return queryset.exclude(upload_state=models.ItemUploadStateChoices.PENDING)

    def get_queryset(self):
        """Get queryset performing all annotation and filtering on the item tree structure."""
        user = self.request.user
        queryset = super().get_queryset().select_related("creator")
        # Remove items with upload_state SUSPICIOUS for non-creators
        queryset = self._filter_suspicious_items(queryset, user)

        # Only list views need filtering and annotation
        if self.detail:
            return queryset

        if not user.is_authenticated:
            return queryset.none()

        queryset = queryset.filter(ancestors_deleted_at__isnull=True)
        queryset = self._exclude_pending_items(queryset)

        # Filter items to which the current user has access...
        access_items_ids = models.ItemAccess.objects.filter(
            db.Q(user=user) | db.Q(team__in=user.teams)
        ).values_list("item_id", flat=True)

        # ...or that were previously accessed and are not restricted
        # For this we look for all items that have a link trace for the current user
        # and that are not in the access_items_ids list.
        # and we compute the ancestors link definition for each item.
        # Then we filter out the items that are restricted.
        traced_items = models.Item.objects.filter(
            db.Q(link_traces__user=user) & ~db.Q(id__in=access_items_ids)
        ).order_by("path")
        ancestors_link_definition = self._compute_ancestors_link_definition(traced_items)
        traced_items_ids = []
        for item in traced_items:
            links = ancestors_link_definition.get(str(item.path[:-1]), [])
            item.ancestors_link_definition = get_equivalent_link_definition(links)
            if item.computed_link_reach != LinkReachChoices.RESTRICTED:
                traced_items_ids.append(item.id)

        # Among all these items remove them that are restricted
        return queryset.filter(db.Q(id__in=access_items_ids) | (db.Q(id__in=traced_items_ids)))

    @drf.decorators.action(detail=True, methods=["post"], url_path="convert")
    def convert(self, request, *args, **kwargs):
        """Queue a legacy Office file conversion for a regular Drive item."""
        source = self.get_object()
        try:
            placeholder = prepare_conversion(source, request.user)
        except conversion_exceptions.ConversionPermissionDenied as exc:
            raise drf.exceptions.PermissionDenied() from exc
        except (
            conversion_exceptions.ConversionRejected,
            conversion_exceptions.ConversionMisconfigured,
        ) as exc:
            raise drf.exceptions.ValidationError({"detail": str(exc)}) from exc

        try:
            convert_file.delay(
                source_item_id=str(source.id),
                converted_item_id=str(placeholder.id),
                user_id=str(request.user.id),
            )
        except Exception:
            placeholder.soft_delete()
            placeholder.delete()
            raise

        serializer = self.get_serializer(placeholder)
        return drf.response.Response(serializer.data, status=status.HTTP_201_CREATED)

    def get_queryset_for_descendants(self):
        """
        Filter a queryset on all top level the user has access to
        and all items that are children of the top level items.

        The queryset is not annoated to let the function caller annotate it as needed.
        """

        user = self.request.user
        queryset = self.get_queryset()

        all_accessible_paths = queryset.order_by("path").values_list("path", flat=True)

        if not all_accessible_paths:
            return queryset.none()

        # Among the results, we may have items that are ancestors/descendants
        # of each other. In this case we want to keep only the highest ancestors.
        root_paths = utils.filter_root_paths(
            all_accessible_paths,
            skip_sorting=True,
        )

        path_list = db.Q()
        for path in root_paths:
            path_list |= db.Q(path__descendants=path)

        queryset = self.queryset.select_related("creator")
        # Remove items with upload_state SUSPICIOUS for non-creators
        queryset = self._filter_suspicious_items(queryset, user)
        queryset = self._exclude_pending_items(queryset)
        queryset = queryset.filter(path_list)
        queryset = queryset.filter(ancestors_deleted_at__isnull=True)

        return queryset

    def filter_queryset(self, queryset):
        """Override to apply annotations to generic views."""
        queryset = super().filter_queryset(queryset)
        user = self.request.user
        queryset = queryset.annotate_is_favorite(user)
        queryset = queryset.annotate_user_roles(user)
        queryset = queryset.annotate_with_numchild()
        return queryset

    def get_response_for_queryset(
        self, queryset, context=None, with_ancestors_link_definition=False
    ):
        """Return paginated response for the queryset if requested."""
        context = context or self.get_serializer_context()
        page = self.paginate_queryset(queryset)
        if page is not None:
            items = list(page)
            if with_ancestors_link_definition:
                paths_links_mapping = self._compute_ancestors_link_definition(items)
                context["paths_links_mapping"] = paths_links_mapping
            serializer = self.get_serializer(items, many=True, context=context)
            result = self.get_paginated_response(serializer.data)
            return result

        items = list(queryset)
        if with_ancestors_link_definition:
            paths_links_mapping = self._compute_ancestors_link_definition(items)
            context["paths_links_mapping"] = paths_links_mapping
        serializer = self.get_serializer(items, many=True, context=context)
        return drf.response.Response(serializer.data)

    def _compute_ancestors_link_definition(self, items):
        """
        Compute ancestors link definition for the items collection.
        On the collection, we look for the deepest items, compute ancestors link definition
        for each item and aggregate them in order to inject it in the serializer context.
        """
        if not items:
            return {}

        # Find deepest items and group them by parent path
        # Items at the same depth in multiple trees (same parent path) share the same ancestors,
        items_sorted = sorted(items, key=lambda x: len(x.path), reverse=True)
        items_by_tree = {}  # Group deepest items by parent_path
        seen_paths = set()  # Track all paths we've processed

        for item in items_sorted:
            # Check if this item is a parent of any longer path we've already seen
            # A descendant path would start with the item's path followed by a dot
            item_path_prefix = f"{item.path}."
            has_descendants = any(
                seen_path.startswith(item_path_prefix) for seen_path in seen_paths
            )

            if not has_descendants:
                # Get parent path (empty string for root items)
                parent_path = str(item.path[:-1]) if item.depth > 1 else ""
                if parent_path not in items_by_tree:
                    items_by_tree[parent_path] = item

            # Add this item's path to the set for future checks (shorter paths)
            seen_paths.add(str(item.path))

        # Compute ancestors links paths mapping for one item per tree group and aggregate
        paths_links_mapping = {}
        for item in items_by_tree.values():
            item_mapping = item.compute_ancestors_links_paths_mapping()
            paths_links_mapping |= item_mapping

        # Update the serializer context with the aggregated mapping
        return paths_links_mapping

    def retrieve(self, request, *args, **kwargs):
        """
        Add a trace that the item was accessed by a user. This is used to list items
        on a user's list view even though the user has no specific role in the item (link
        access when the link reach configuration of the item allows it).
        """
        user = self.request.user
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # The `create` query generates 5 db queries which are much less efficient than an
        # `exists` query. The user will visit the item many times after the first visit
        # so that's what we should optimize for.
        if user.is_authenticated and not instance.link_traces.filter(user=user).exists():
            try:
                models.LinkTrace.objects.create(item=instance, user=request.user)
            except IntegrityError:
                pass  # Race condition: trace already created by concurrent request

        return drf.response.Response(serializer.data)

    def _create_file_from_template(self, item, extension):
        """Read template file and upload it to storage for the given item."""
        template_path = os.path.join(
            settings.BASE_DIR, "assets", "file_templates", f"template.{extension}"
        )

        try:
            with open(template_path, "rb") as template_file:
                template_content = template_file.read()
        except OSError as e:
            logger.error(
                "Error reading template file %s: %s",
                template_path,
                str(e),
            )
            raise drf.exceptions.ValidationError(
                {"extension": _("Error reading template file.")},
                code="template_file_read_error",
            ) from e

        try:
            default_storage.save(item.file_key, BytesIO(template_content))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error uploading template file to storage for item %s: %s",
                item.id,
                str(e),
            )
            item.soft_delete()
            item.delete()
            raise drf.exceptions.ValidationError(
                {"detail": _("Error uploading file to storage.")},
                code="storage_upload_error",
            ) from e

        item.upload_state = models.ItemUploadStateChoices.READY
        item.mimetype = utils.detect_mimetype(template_content, item.filename)
        item.size = len(template_content)
        item.save(update_fields=["upload_state", "mimetype", "size", "updated_at"])

    def perform_create(self, serializer):
        """Set the current user as creator and owner of the newly created object."""
        entitlements_backend = get_entitlements_backend()
        can_upload = entitlements_backend.can_upload(self.request.user)
        if (
            serializer.validated_data.get("type") == models.ItemTypeChoices.FILE
            and not can_upload["result"]
        ):
            raise drf.exceptions.PermissionDenied(
                detail=can_upload.get("message", "You do not have permission to upload files.")
            )
        extension = serializer.validated_data.pop("extension", None)

        obj = models.Item.objects.create_child(
            creator=self.request.user,
            link_reach=LinkReachChoices.RESTRICTED,
            **serializer.validated_data,
        )
        if extension:
            self._create_file_from_template(obj, extension)
        serializer.instance = obj
        models.ItemAccess.objects.create(
            item=obj,
            user=self.request.user,
            role=models.RoleChoices.OWNER,
        )

    def perform_destroy(self, instance):
        """Override to implement a soft delete instead of dumping the record in database."""
        instance.soft_delete()

    def perform_update(self, serializer):
        """Override to check if a file is renamed in order to rename file on storage."""
        instance = serializer.instance
        old_title = instance.title
        serializer.save()
        if instance.type == models.ItemTypeChoices.FILE:
            title = serializer.validated_data.get("title")
            if title and old_title != title:
                rename_file.delay(instance.id, title)

    def _resolve_parent_folder_or_none_for_create(
        self,
        *,
        user,
        parent_id,
    ):
        if not parent_id:
            return None

        try:
            parent = (
                models.Item.objects.filter(
                    hard_deleted_at__isnull=True,
                    ancestors_deleted_at__isnull=True,
                )
                .readable_per_se(user)
                .get(id=parent_id)
            )
        except models.Item.DoesNotExist as exc:
            raise drf.exceptions.NotFound from exc

        if parent.type != models.ItemTypeChoices.FOLDER:
            raise drf.exceptions.ValidationError(
                {
                    "parent_id": drf.exceptions.ErrorDetail(
                        "Only folders can have children.",
                        code="item_create_child_type_folder_only",
                    )
                }
            )

        if not parent.get_abilities(user).get("children_create"):
            raise drf.exceptions.PermissionDenied(
                detail="You do not have permission to create items in this folder."
            )

        return parent

    @staticmethod
    def _new_file_payload_for_extension(extension: str):
        odf_extensions = {"odt", "ods", "odp"}
        ooxml_mimetypes = {
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }

        if extension in odf_extensions:
            mimetype, payload = build_minimal_odf_template_bytes(extension)
            return mimetype, payload, models.ItemUploadStateChoices.READY

        if extension in ooxml_mimetypes:
            mimetype = ooxml_mimetypes[extension]
            editnew_client = get_wopi_client_config_for_filename(
                filename=f"new.{extension}",
                mimetype=mimetype,
                action="editnew",
            )
            if editnew_client:
                return mimetype, b"", models.ItemUploadStateChoices.CREATING

            mimetype, payload = build_minimal_ooxml_template_bytes(extension)
            return mimetype, payload, models.ItemUploadStateChoices.READY

        return "application/octet-stream", b"", models.ItemUploadStateChoices.READY

    @staticmethod
    def _put_object_to_default_storage(
        *,
        storage_key: str,
        payload: bytes,
        mimetype: str,
    ) -> None:
        """
        Write bytes to the configured storage backend.

        For S3-compatible backends, prefer a direct `PutObject` (boto3 client)
        instead of `default_storage.save()` to avoid rare ~60s stalls observed
        with SeaweedFS S3 gateway when using the django-storages save path.
        """
        s3_client = getattr(getattr(default_storage, "connection", None), "meta", None)
        s3_client = getattr(s3_client, "client", None)
        bucket_name = getattr(default_storage, "bucket_name", None)
        if s3_client and bucket_name:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=storage_key,
                Body=payload,
                ContentType=mimetype or "application/octet-stream",
            )
            return

        default_storage.save(storage_key, BytesIO(payload))

    @drf.decorators.action(
        detail=False,
        methods=["post"],
        url_path="new-odf",
        permission_classes=[IsAuthenticated],
    )
    def new_odf(self, request, *args, **kwargs):  # pylint: disable=too-many-locals
        """
        Create a new ODF document (odt/ods/odp) from a minimal, valid template.

        This endpoint is designed for WOPI/Collabora flows: ODF files must not be
        created as 0-byte placeholders.
        """
        serializer = serializers.CreateOdfDocumentSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        parent_id = serializer.validated_data.get("parent_id")
        kind = serializer.validated_data["kind"]
        filename = serializer.validated_data["filename"]

        entitlements_backend = get_entitlements_backend()
        can_upload = entitlements_backend.can_upload(user)
        if not can_upload["result"]:
            raise drf.exceptions.PermissionDenied(
                detail=can_upload.get("message", "You do not have permission to upload files.")
            )

        parent = self._resolve_parent_folder_or_none_for_create(user=user, parent_id=parent_id)

        build_at = time.monotonic()
        mimetype, payload = build_minimal_odf_template_bytes(kind)
        build_ms = int((time.monotonic() - build_at) * 1000)

        try:
            started_at = time.monotonic()
            with transaction.atomic():
                if parent is not None:
                    item = models.Item.objects.create_child(
                        creator=user,
                        parent=parent,
                        type=models.ItemTypeChoices.FILE,
                        title=filename,
                        filename=filename,
                        mimetype=mimetype,
                    )
                else:
                    item = models.Item.objects.create_child(
                        creator=user,
                        link_reach=LinkReachChoices.RESTRICTED,
                        type=models.ItemTypeChoices.FILE,
                        title=filename,
                        filename=filename,
                        mimetype=mimetype,
                    )
                    models.ItemAccess.objects.create(
                        item=item,
                        user=user,
                        role=models.RoleChoices.OWNER,
                    )

                if item.filename != item.title:
                    item.filename = item.title
                    item.save(update_fields=["filename", "updated_at"])

                storage_at = time.monotonic()
                self._put_object_to_default_storage(
                    storage_key=item.file_key, payload=payload, mimetype=mimetype
                )
                storage_ms = int((time.monotonic() - storage_at) * 1000)
                item.upload_state = models.ItemUploadStateChoices.READY
                item.size = len(payload)
                item.save(update_fields=["upload_state", "size"])
        except Exception as exc:
            # Best-effort cleanup (no-leak): avoid leaving a partially created object behind.
            with contextlib.suppress(Exception):
                if "item" in locals():
                    default_storage.delete(locals()["item"].file_key)
            raise APIException("Could not create document.") from exc

        total_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            "new_odf: ok (item_id=%s kind=%s ms_total=%s ms_build=%s ms_storage=%s)",
            item.id,
            kind,
            total_ms,
            build_ms,
            storage_ms,
        )
        data = serializers.ItemSerializer(item, context=self.get_serializer_context()).data
        return drf.response.Response(data, status=status.HTTP_201_CREATED)

    @drf.decorators.action(
        detail=False,
        methods=["post"],
        url_path="new-file",
        permission_classes=[IsAuthenticated],
    )
    def new_file(self, request, *args, **kwargs):  # pylint: disable=too-many-locals
        """
        Create a new file from a (stem + extension) user choice.

        - ODF (.odt/.ods/.odp): create a minimal valid template and set READY.
        - OOXML (.docx/.xlsx/.pptx): create a 0-byte placeholder in CREATING state.
        - Other: create an empty file and set READY.
        """
        serializer = serializers.CreateNewFileSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        parent_id = serializer.validated_data.get("parent_id")
        final_filename = serializer.validated_data["final_filename"]
        extension = serializer.validated_data["extension"]

        entitlements_backend = get_entitlements_backend()
        can_upload = entitlements_backend.can_upload(user)
        if not can_upload["result"]:
            raise drf.exceptions.PermissionDenied(
                detail=can_upload.get("message", "You do not have permission to upload files.")
            )

        parent = self._resolve_parent_folder_or_none_for_create(user=user, parent_id=parent_id)

        build_at = time.monotonic()
        mimetype, payload, upload_state = self._new_file_payload_for_extension(extension)
        build_ms = int((time.monotonic() - build_at) * 1000)

        try:
            started_at = time.monotonic()
            with transaction.atomic():
                if parent is not None:
                    item = models.Item.objects.create_child(
                        creator=user,
                        parent=parent,
                        type=models.ItemTypeChoices.FILE,
                        title=final_filename,
                        filename=final_filename,
                        mimetype=mimetype,
                    )
                else:
                    item = models.Item.objects.create_child(
                        creator=user,
                        link_reach=LinkReachChoices.RESTRICTED,
                        type=models.ItemTypeChoices.FILE,
                        title=final_filename,
                        filename=final_filename,
                        mimetype=mimetype,
                    )
                    models.ItemAccess.objects.create(
                        item=item,
                        user=user,
                        role=models.RoleChoices.OWNER,
                    )

                # If collisions occurred in this folder, create_child may have
                # adjusted title; keep filename as source of truth for WOPI.
                if item.filename != item.title:
                    item.filename = item.title
                    item.save(update_fields=["filename", "updated_at"])

                storage_ms = 0
                if extension in {"odt", "ods", "odp"}:
                    storage_at = time.monotonic()
                    self._put_object_to_default_storage(
                        storage_key=item.file_key, payload=payload, mimetype=mimetype
                    )
                    storage_ms = int((time.monotonic() - storage_at) * 1000)
                else:
                    default_storage.save(item.file_key, BytesIO(payload))
                item.upload_state = upload_state
                item.size = len(payload)
                if upload_state == models.ItemUploadStateChoices.CREATING:
                    item.upload_started_at = timezone.now()
                item.save(
                    update_fields=[
                        "upload_state",
                        "size",
                        "upload_started_at",
                    ]
                )
        except Exception as exc:
            with contextlib.suppress(Exception):
                if "item" in locals():
                    default_storage.delete(locals()["item"].file_key)
            raise APIException("Could not create file.") from exc

        if extension in {"odt", "ods", "odp"}:
            total_ms = int((time.monotonic() - started_at) * 1000)
            logger.info(
                "new_file_odf: ok (item_id=%s ext=%s ms_total=%s ms_build=%s ms_storage=%s)",
                item.id,
                extension,
                total_ms,
                build_ms,
                storage_ms,
            )
        data = serializers.ItemSerializer(item, context=self.get_serializer_context()).data
        return drf.response.Response(data, status=status.HTTP_201_CREATED)

    @drf.decorators.action(detail=True, methods=["delete"], url_path="hard-delete")
    def hard_delete(self, request, *args, **kwargs):
        """
        Hard delete an item.
        """
        instance = self.get_object()
        instance.hard_delete()
        process_item_purge.delay(instance.id)
        return drf.response.Response(status=status.HTTP_204_NO_CONTENT)

    def list(self, request, *args, **kwargs):
        """List top level items with pagination and filtering."""
        # Not calling filter_queryset. We do our own cooking.
        queryset = self.get_queryset()

        filterset = ListItemFilter(self.request.GET, queryset=queryset, request=self.request)
        if not filterset.is_valid():
            raise drf.exceptions.ValidationError(filterset.errors)
        filter_data = filterset.form.cleaned_data

        # Filter early, excluding is_favorite whose annotation does not exist yet.
        for field in filterset.filters:
            if field != "is_favorite":
                queryset = filterset.filters[field].filter(queryset, filter_data[field])
        user = request.user
        queryset = queryset.annotate_user_roles(user)

        # Among the results, we may have items that are ancestors/descendants
        # of each other. In this case we want to keep only the highest ancestors.
        root_paths = utils.filter_root_paths(
            queryset.order_by("path").values_list("path", flat=True),
            skip_sorting=True,
        )
        queryset = queryset.filter(path__in=root_paths)

        # Annotate the queryset with an attribute marking instances as highest ancestor
        # in order to save some time while computing abilities in the instance
        queryset = queryset.annotate(
            is_highest_ancestor_for_user=db.Value(True, output_field=db.BooleanField())
        )

        # Annotate favorite status and filter if applicable as late as possible
        queryset = queryset.annotate_is_favorite(user)
        queryset = filterset.filters["is_favorite"].filter(queryset, filter_data["is_favorite"])
        queryset = queryset.annotate_with_numchild()

        # Apply ordering only now that everyting is filtered and annotated
        queryset = self._apply_deterministic_ordering(queryset)

        return self.get_response_for_queryset(queryset)

    @drf.decorators.action(detail=True, methods=["post"], url_path="upload-ended")
    def upload_ended(  # noqa: PLR0915  # pylint: disable=too-many-locals,too-many-statements
        self, request, *args, **kwargs
    ):
        """
        Start the analysis of an item after a successful upload.
        """

        item = self.get_object()
        self._ensure_upload_ended_item_is_pending_file(item)

        entitlements_backend = get_entitlements_backend()
        can_upload = entitlements_backend.can_upload(self.request.user)
        if not can_upload["result"]:
            self._complete_item_deletion(item)
            raise drf.exceptions.PermissionDenied(
                detail=can_upload.get("message", "You do not have permission to upload files.")
            )

        s3_client = default_storage.connection.meta.client
        head_response, file_size, file_head = self._get_item_head_for_mimetype_detection(
            item, s3_client
        )
        if file_size > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
            self._complete_item_deletion(item)
            logger.info(
                "upload_ended: file size (%s) for file %s higher than the allowed max size",
                file_size,
                item.file_key,
            )
            raise drf.exceptions.ValidationError(
                detail="The file size is higher than the allowed max size.",
                code="file_size_exceeded",
            )

        # Use improved MIME type detection combining magic bytes and file extension
        file_key_hash = safe_str_hash(item.file_key)
        logger.info(
            "upload_ended: detecting mimetype (item_id=%s file_key_hash=%s)",
            item.id,
            file_key_hash,
        )
        mimetype = utils.detect_mimetype(file_head, filename=item.filename)

        # Robustness: if content-based MIME detection returns a type that is not
        # allowlisted but extension-based detection is allowlisted, prefer the
        # extension-based MIME. This avoids spurious 400s for text-like files
        # where libmagic returns uncommon subtypes.
        if settings.RESTRICT_UPLOAD_FILE_TYPE and mimetype not in settings.FILE_MIMETYPE_ALLOWED:
            try:
                extension_mimetype, _ = mimetypes.guess_file_type(item.filename, strict=False)
            except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                extension_mimetype = None
            if extension_mimetype and extension_mimetype in settings.FILE_MIMETYPE_ALLOWED:
                logger.info(
                    "upload_ended: using extension mimetype fallback (item_id=%s file_key_hash=%s "
                    "from=%s to=%s)",
                    item.id,
                    file_key_hash,
                    mimetype,
                    extension_mimetype,
                )
                mimetype = extension_mimetype

        if settings.RESTRICT_UPLOAD_FILE_TYPE and mimetype not in settings.FILE_MIMETYPE_ALLOWED:
            self._complete_item_deletion(item)
            logger.info(
                "upload_ended: mimetype not allowed (item_id=%s file_key_hash=%s mimetype=%s)",
                item.id,
                file_key_hash,
                mimetype,
            )
            raise drf.exceptions.ValidationError(
                detail="The file type is not allowed.",
                code="file_type_not_allowed",
            )

        item.upload_state = models.ItemUploadStateChoices.ANALYZING
        item.mimetype = mimetype
        item.size = file_size

        item.save(update_fields=["upload_state", "mimetype", "size"])

        if head_response["ContentType"] != mimetype:
            logger.info(
                "upload_ended: content type mismatch between object storage and item,"
                " updating from %s to %s",
                head_response["ContentType"],
                mimetype,
            )
            try:
                escaped_key = quote(item.file_key, safe="/")
                copy_source = f"/{default_storage.bucket_name}/{escaped_key}"
                s3_client.copy_object(
                    Bucket=default_storage.bucket_name,
                    Key=item.file_key,
                    CopySource=copy_source,
                    ContentType=mimetype,
                    Metadata=head_response["Metadata"],
                    MetadataDirective="REPLACE",
                )
            except ClientError as error:
                # Compatibility: some S3 gateways reject CopyObject. Try a
                # streaming GET→PUT fallback (no-leak logs).
                logger.exception(
                    "upload_ended: content-type update failed "
                    "(item_id=%s file_key_hash=%s error_code=%s)",
                    item.id,
                    file_key_hash,
                    error.response["Error"]["Code"],
                )
                try:
                    obj = s3_client.get_object(
                        Bucket=default_storage.bucket_name,
                        Key=item.file_key,
                    )
                    body = obj.get("Body")
                    try:
                        stream_to_s3_object(
                            s3_client=s3_client,
                            bucket=default_storage.bucket_name,
                            key=item.file_key,
                            body_stream=body,
                            content_type=mimetype,
                            metadata=head_response.get("Metadata", {}),
                            acl="private",
                        )
                    finally:
                        with contextlib.suppress(Exception):
                            body.close()
                except ClientError as fallback_error:
                    logger.exception(
                        "upload_ended: content-type update fallback failed "
                        "(item_id=%s file_key_hash=%s error_code=%s)",
                        item.id,
                        file_key_hash,
                        fallback_error.response["Error"]["Code"],
                    )

        malware_detection.analyse_file(item.file_key, item_id=item.id)

        serializer = self.get_serializer(item)

        posthog_capture(
            "item_uploaded",
            request.user,
            {
                "id": item.id,
                "title": item.title,
                "size": item.size,
                "mimetype": item.mimetype,
            },
        )

        return drf_response.Response(serializer.data, status=status.HTTP_200_OK)

    def _ensure_upload_ended_item_is_pending_file(self, item):
        if item.type != models.ItemTypeChoices.FILE:
            raise drf.exceptions.ValidationError(
                {"item": "This action is only available for items of type FILE."},
                code="item_upload_type_unavailable",
            )

        if item.effective_upload_state() == models.ItemUploadStateChoices.EXPIRED:
            file_key_hash = safe_str_hash(item.file_key) if item.filename else None
            logger.info(
                "upload_ended: pending upload expired "
                "(failure_class=upload.session.expired "
                "next_action_hint=Re-initiate upload (refresh policy) "
                "item_id=%s file_key_hash=%s)",
                item.id,
                file_key_hash,
            )
            item.upload_state = models.ItemUploadStateChoices.EXPIRED
            item.save(update_fields=["upload_state", "updated_at"])
            raise drf.exceptions.ValidationError(
                {"item": "This upload session has expired. Please retry the upload."},
                code="item_upload_state_expired",
            )

        if item.upload_state != models.ItemUploadStateChoices.PENDING:
            raise drf.exceptions.ValidationError(
                {"item": "This action is only available for items in PENDING state."},
                code="item_upload_state_not_pending",
            )

    def _get_item_head_for_mimetype_detection(self, item, s3_client):
        head_response = s3_client.head_object(Bucket=default_storage.bucket_name, Key=item.file_key)
        file_size = head_response["ContentLength"]

        if file_size <= 2048:
            body = s3_client.get_object(Bucket=default_storage.bucket_name, Key=item.file_key)[
                "Body"
            ]
            return head_response, file_size, body.read()

        body = s3_client.get_object(
            Bucket=default_storage.bucket_name,
            Key=item.file_key,
            Range="bytes=0-2047",
        )["Body"]
        return head_response, file_size, body.read()

    @drf.decorators.action(detail=True, methods=["post"], url_path="upload-policy")
    def upload_policy(self, request, *args, **kwargs):
        """
        Re-initiate a pending upload on an existing item by returning a fresh presigned PUT
        policy URL.

        This supports deterministic retry without creating duplicate "ghost" items.
        """
        item = self.get_object()

        if item.type != models.ItemTypeChoices.FILE:
            raise drf.exceptions.ValidationError(
                {"item": "This action is only available for items of type FILE."},
                code="item_upload_type_unavailable",
            )

        if item.upload_state not in {
            models.ItemUploadStateChoices.PENDING,
            models.ItemUploadStateChoices.EXPIRED,
        }:
            raise drf.exceptions.ValidationError(
                {"item": "This action is only available for items in PENDING state."},
                code="item_upload_state_not_pending",
            )

        entitlements_backend = get_entitlements_backend()
        can_upload = entitlements_backend.can_upload(self.request.user)
        if not can_upload["result"]:
            self._complete_item_deletion(item)
            raise drf.exceptions.PermissionDenied(
                detail=can_upload.get("message", "You do not have permission to upload files.")
            )

        # Refresh pending session window deterministically.
        item.restart_pending_upload()

        return drf_response.Response(
            {"policy": utils.generate_upload_policy(item)},
            status=status.HTTP_200_OK,
        )

    def _complete_item_deletion(self, item):
        """Completely delete an item."""
        item.soft_delete()
        item.hard_delete()
        process_item_purge.delay(item.id)

    @drf.decorators.action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated],
    )
    def favorite_list(self, request, *args, **kwargs):
        """Get list of favorite items for the current user."""
        user = request.user
        queryset = self.get_queryset_for_descendants()
        queryset = queryset.annotate(is_favorite=db.Value(True, output_field=db.BooleanField()))
        queryset = queryset.annotate_user_roles(user)

        filterset = ItemFilter(self.request.GET, queryset=queryset, request=self.request)
        if not filterset.is_valid():
            raise drf.exceptions.ValidationError(filterset.errors)

        queryset = filterset.filter_queryset(queryset)

        favorite_items_ids = models.ItemFavorite.objects.filter(user=user).values_list(
            "item_id", flat=True
        )

        queryset = queryset.filter(id__in=favorite_items_ids)
        queryset = queryset.annotate_with_numchild()
        queryset = self._apply_deterministic_ordering(queryset)

        return self.get_response_for_queryset(queryset, with_ancestors_link_definition=True)

    @drf.decorators.action(
        detail=False,
        methods=["get"],
    )
    def trashbin(self, request, *args, **kwargs):
        """
        Retrieve soft-deleted items for which the current user has the owner role.

        The selected items are those deleted within the cutoff period defined in the
        settings (see TRASHBIN_CUTOFF_DAYS), before they are considered permanently deleted.

        Optimized version that uses EXISTS instead of expensive subqueries to check
        owner access on items or their ancestors.
        """
        user = request.user

        # Restrict to soft-deleted items the user owns directly or through an
        # ancestor access. Filtering on the owner access subquery is much faster
        # than on the user_roles annotation.
        queryset = (
            self.queryset.select_related("creator")
            .filter(
                deleted_at__gte=models.get_trashbin_cutoff(),
            )
            .owned_by(user)
        )

        # Apply filtering similar to children method
        filterset = ItemFilter(request.GET, queryset=queryset)
        if not filterset.is_valid():
            raise drf.exceptions.ValidationError(filterset.errors)
        queryset = filterset.qs

        # Only annotate with user roles for the filtered set if needed by serializer
        queryset = queryset.annotate_user_roles(user)
        queryset = queryset.annotate_with_numchild()

        return self.get_response_for_queryset(queryset)

    @drf.decorators.action(
        detail=True,
        methods=["post"],
        url_path="duplicate",
    )
    def duplicate(self, request, *args, **kwargs):
        """
        Duplicate an item of type File. The item is duplicated in the folder where the original
        item is.
        The user who duplicates becomes the creator of the duplicate
        """

        item_to_duplicate = self.get_object()
        user = request.user

        parent = item_to_duplicate.parent() if item_to_duplicate.depth > 1 else None

        if parent and parent.get_role(user) == models.RoleChoices.READER:
            parent = None

        with transaction.atomic():
            duplicated_item = models.Item.objects.create_child(
                creator=user,
                link_reach=None if parent else LinkReachChoices.RESTRICTED,
                parent=parent,
                title=capfirst(_("copy of {title}").format(title=item_to_duplicate.title)),
                type=models.ItemTypeChoices.FILE,
                size=item_to_duplicate.size,
                upload_state=models.ItemUploadStateChoices.DUPLICATING,
                mimetype=item_to_duplicate.mimetype,
                filename=item_to_duplicate.filename,
                description=item_to_duplicate.description,
            )

            if duplicated_item.is_root:
                models.ItemAccess.objects.create(
                    item=duplicated_item,
                    user=user,
                    role=models.RoleChoices.OWNER,
                )

        duplicate_file.delay(
            item_to_duplicate_id=item_to_duplicate.id,
            duplicated_item_id=duplicated_item.id,
        )
        posthog_capture("item_duplicate", user, {}, item=duplicated_item)

        serializer = self.get_serializer(duplicated_item)
        return drf.response.Response(serializer.data, status=drf.status.HTTP_201_CREATED)

    @drf.decorators.action(detail=True, methods=["post"])
    @transaction.atomic
    def move(self, request, *args, **kwargs):
        """
        Move an item to another location within the item tree.

        The user must be an administrator or owner of both the item being moved
        and the target parent item.
        """
        user = request.user
        item = self.get_object()  # including permission checks

        # Validate the input payload
        serializer = serializers.MoveItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        target_item_id = validated_data.get("target_item_id")
        if not target_item_id:
            target_item = None
        else:
            try:
                target_item = models.Item.objects.get(
                    id=target_item_id, ancestors_deleted_at__isnull=True
                )
            except models.Item.DoesNotExist as excpt:
                raise drf.exceptions.ValidationError(
                    {"target_item_id": "Target parent item does not exist."},
                    code="item_move_target_does_not_exist",
                ) from excpt

        message = None
        if target_item and not target_item.get_abilities(user).get("children_create"):
            message = "You do not have permission to move items as a child to this target item."

        if message:
            posthog_capture("item_move_missing_permission", user, {}, item=item)
            raise drf.exceptions.ValidationError(
                {"target_item_id": message}, code="item_move_missing_permission"
            )

        item.move(target_item)

        # If the item is moved to the root and the user does not have an access on the item,
        # create an owner access for the user. Otherwise, the item will be invisible for the user.
        update_fields = []
        if not target_item and not models.ItemAccess.objects.filter(item=item, user=user).exists():
            models.ItemAccess.objects.create(
                item=item,
                user=self.request.user,
                role=models.RoleChoices.OWNER,
            )
            item.creator = user
            update_fields.append("creator")

        # When moving an item to the root and no link_reach is set
        # Force it to be restricted.
        if not target_item and not item.link_reach:
            item.link_reach = LinkReachChoices.RESTRICTED
            update_fields.append("link_reach")

        if target_item:
            # When moving an item in an other item, force it to be sync
            # with its parent's link reach.
            item.link_reach = None
            update_fields.append("link_reach")

        if update_fields:
            item.save(update_fields=update_fields)

        posthog_capture("item_moved", user, {}, item=item)

        return drf.response.Response(
            {"message": "item moved successfully."}, status=status.HTTP_200_OK
        )

    @drf.decorators.action(
        detail=True,
        methods=["post"],
    )
    def restore(self, request, *args, **kwargs):
        """
        Restore a soft-deleted item if it was deleted less than x days ago.
        """
        item = self.get_object()
        item.restore()

        return drf_response.Response(
            {"detail": "item has been successfully restored."},
            status=status.HTTP_200_OK,
        )

    @drf.decorators.action(
        detail=True,
        methods=["get", "post"],
        ordering=["created_at"],
        url_path="children",
    )
    def children(self, request, *args, **kwargs):
        """Handle listing and creating children of a item"""
        item = self.get_object()

        if request.method == "POST":
            # Create a child item
            serializer = serializers.CreateItemSerializer(
                data=request.data, context=self.get_serializer_context()
            )
            serializer.is_valid(raise_exception=True)

            entitlements_backend = get_entitlements_backend()
            can_upload = entitlements_backend.can_upload(self.request.user)
            if (
                serializer.validated_data.get("type") == models.ItemTypeChoices.FILE
                and not can_upload["result"]
            ):
                raise drf.exceptions.PermissionDenied(
                    detail=can_upload.get("message", "You do not have permission to upload files.")
                )

            extension = serializer.validated_data.pop("extension", None)

            child_item = models.Item.objects.create_child(
                creator=request.user,
                parent=item,
                **serializer.validated_data,
            )

            if extension:
                self._create_file_from_template(child_item, extension)

            # Set the created instance to the serializer
            serializer.instance = child_item

            headers = self.get_success_headers(serializer.data)
            return drf.response.Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )

        # GET: List children
        queryset = item.children().select_related("creator").filter(deleted_at__isnull=True)
        queryset = self._filter_suspicious_items(queryset, request.user)
        queryset = self._exclude_pending_items(queryset)
        queryset = self.filter_queryset(queryset)
        filterset = ItemFilter(request.GET, queryset=queryset)
        if not filterset.is_valid():
            raise drf.exceptions.ValidationError(filterset.errors)
        queryset = filterset.qs

        # Apply ordering only now that everything is filtered and annotated
        queryset = self._apply_deterministic_ordering(queryset)

        # Pre-compute number of accesses
        item_nb_accesses = item.nb_accesses
        queryset = queryset.annotate(
            _nb_accesses=db.Value(item_nb_accesses)
            + Coalesce(db.Count("accesses", distinct=True), 0),
        )

        # Pass ancestors' links paths mapping to the serializer as a context variable
        # in order to allow saving time while computing abilities on the instance
        paths_links_mapping = item.compute_ancestors_links_paths_mapping()

        return self.get_response_for_queryset(
            queryset,
            context={
                "request": request,
                "paths_links_mapping": paths_links_mapping,
            },
        )

    @drf.decorators.action(detail=True, methods=["get"])
    def tree(self, request, pk=None):
        """
        List ancestors tree above the item
        What we need to display is the tree structure opened for the current document.
        """
        try:
            item = self.queryset.only("path").get(pk=pk)
        except models.Item.DoesNotExist as exc:
            raise drf.exceptions.NotFound from exc

        highest_ancestor = (
            self.queryset.filter(path__ancestors=item.path, ancestors_deleted_at__isnull=True)
            .readable_per_se(request.user)
            .only("path")
            .order_by("path")
            .first()
        )

        if not highest_ancestor:
            raise (
                drf.exceptions.PermissionDenied()
                if request.user.is_authenticated
                else drf.exceptions.NotAuthenticated()
            )

        ancestors = (
            self.queryset.filter(
                path__ancestors=item.path,
                path__descendants=highest_ancestor.path,
                ancestors_deleted_at__isnull=True,
            )
            .order_by("path")
            .values_list("path", "link_reach", "link_role", named=True)
        )

        if len(ancestors) == 0:
            raise (
                drf.exceptions.PermissionDenied()
                if request.user.is_authenticated
                else drf.exceptions.NotAuthenticated()
            )

        paths_links_mapping = {}
        ancestors_links = []
        clause = db.Q()
        for i, ancestor in enumerate(ancestors):
            # exclude first iteration
            if i == 0:
                # this is the highest ancestor, select it directly
                clause |= db.Q(path=ancestor.path)
            else:
                # Select all siblings of the current ancestor
                clause |= db.Q(
                    path__descendants=".".join(ancestor.path[:-1]),
                    path__depth=len(ancestor.path),
                )

            # Compute cache for ancestors links to avoid many queries while computing
            # abilties for his items in the tree!
            ancestors_links.append(
                {"link_reach": ancestor.link_reach, "link_role": ancestor.link_role}
            )
            paths_links_mapping[str(ancestor.path)] = ancestors_links.copy()

        tree = (
            self.queryset.select_related("creator")
            .filter(clause, type=models.ItemTypeChoices.FOLDER, deleted_at__isnull=True)
            .order_by("created_at")
        )

        user = request.user
        tree = tree.annotate_user_roles(user)
        tree = tree.annotate_is_favorite(user)
        tree = tree.annotate_with_numchild()
        tree = self._filter_suspicious_items(tree, user)

        serializer = self.get_serializer(
            tree,
            many=True,
            context={
                "request": request,
                "paths_links_mapping": paths_links_mapping,
            },
        )

        return drf.response.Response(
            utils.flat_to_nested(serializer.data), status=drf.status.HTTP_200_OK
        )

    @drf.decorators.action(
        url_path="recents",
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated],
    )
    def recents(self, request, *args, **kwargs):
        """Get list of recent items for the current user."""
        user = self.request.user
        queryset = self.get_queryset_for_descendants()

        filterset = ItemFilter(self.request.GET, queryset=queryset, request=self.request)
        if not filterset.is_valid():
            raise drf.exceptions.ValidationError(filterset.errors)

        queryset = filterset.filter_queryset(queryset)

        queryset = queryset.annotate_is_favorite(user)
        queryset = queryset.annotate_user_roles(user)
        queryset = queryset.annotate_with_numchild()

        queryset = self._apply_deterministic_ordering(queryset)

        return self.get_response_for_queryset(queryset, with_ancestors_link_definition=True)

    @drf.decorators.action(detail=True, methods=["get"])
    def breadcrumb(self, request, *args, **kwargs):
        """
        List the breadcrumb for an item
        """
        item = self.get_object()

        highest_ancestor = (
            self.queryset.filter(path__ancestors=item.path, ancestors_deleted_at__isnull=True)
            .readable_per_se(request.user)
            .only("path")
            .order_by("path")
            .first()
        )

        if not highest_ancestor:
            raise (
                drf.exceptions.PermissionDenied()
                if request.user.is_authenticated
                else drf.exceptions.NotAuthenticated()
            )

        breadcrumb = self.queryset.filter(
            path__ancestors=item.path,
            path__descendants=highest_ancestor.path,
            ancestors_deleted_at__isnull=True,
        ).order_by("path")

        serializer = self.get_serializer(breadcrumb, many=True)
        return drf.response.Response(serializer.data, status=drf.status.HTTP_200_OK)

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    @method_decorator(refresh_oidc_access_token)
    def _indexed_search(self, request, queryset, indexer, text):
        """
        Returns a DRF response containding the results the fulltext search of Find
        sorted by score.
        """
        user = request.user
        token = request.session.get("oidc_access_token")

        # Retrieve the documents ids from Find. No pagination here the queryset is
        # already filtered
        result_ids = [
            r["_id"]
            for r in indexer.search(
                text=text, token=token, visited=get_visited_items_ids_of(queryset, user)
            )
        ]

        queryset = queryset.filter(pk__in=result_ids)
        queryset = queryset.annotate_user_roles(user)
        queryset = queryset.annotate_is_favorite(user)
        queryset = queryset.annotate_with_numchild()

        files_by_uuid = {str(d.pk): d for d in queryset}
        ordered_files = [files_by_uuid[id] for id in result_ids if id in files_by_uuid]

        page = self.paginate_queryset(ordered_files)

        if page is not None:
            items = self._compute_parents(page)
            serializer = self.get_serializer(items, many=True)
            result = self.get_paginated_response(serializer.data)
            return result

        items = self._compute_parents(ordered_files)
        serializer = self.get_serializer(items, many=True)
        return drf.response.Response(serializer.data)

    @staticmethod
    def _filter_indexed_search_queryset(filterset, queryset):
        """Apply non-title search filters before preserving indexer relevance order."""
        filter_data = filterset.form.cleaned_data
        for field, field_filter in filterset.filters.items():
            if field in {"title", "workspace"}:
                continue
            queryset = field_filter.filter(queryset, filter_data.get(field))
        return queryset

    @drf.decorators.action(
        detail=False,
        methods=["get"],
        url_path="search",
        pagination_class=drf.pagination.PageNumberPagination,
    )
    def search(self, request, *args, **kwargs):
        """
        Returns a DRF response containing the filtered, annotated and ordered items.

        Applies filtering based on request parameter 'q' from `SearchItemFilter`.
        Depending of the configuration it can be:
         - A fulltext search through the opensearch indexation app "find" if the backend is
           enabled (see SEARCH_INDEXER_CLASS) and the feature flag INDEXED_SEARCH_ENABLED is True
         - A filtering by the model fields 'title' & 'type'.
        """
        queryset = self.queryset
        indexer = get_file_indexer()

        queryset = queryset.select_related("creator")
        filterset = SearchItemFilter(request.GET, queryset=queryset, request=self.request)

        if not filterset.is_valid():
            raise drf.exceptions.ValidationError(filterset.errors)

        workspace = filterset.form.cleaned_data.get("workspace")

        # First look for all top level items user has access to
        user = request.user
        item_access_queryset = models.ItemAccess.objects.select_related("item").filter(
            db.Q(user=user) | db.Q(team__in=user.teams),
            item__deleted_at__isnull=True,
        )

        # Remove items with upload_state SUSPICIOUS for non-creators
        queryset = self._filter_suspicious_items(queryset, user)
        queryset = self._exclude_pending_items(queryset)

        queryset = queryset.annotate_is_favorite(user)

        if workspace:
            item_access_queryset = item_access_queryset.filter(item__id=workspace)

        top_level_items = item_access_queryset.values_list("item__path", flat=True)
        # Then look for all items that are children of the top level items

        if not top_level_items:
            return self.get_response_for_queryset(queryset.none())

        # Among the results, we may have items that are ancestors/descendants
        # of each other. In this case we want to keep only the highest ancestors.
        root_paths = utils.filter_root_paths(
            top_level_items,
            skip_sorting=True,
        )

        path_list = db.Q()
        for top_level_item in root_paths:
            path_list |= db.Q(path__descendants=top_level_item)

        queryset = queryset.filter(path_list)

        # use indexed search ONLY when the feature flag is enabled
        if indexer and settings.FEATURES_INDEXED_SEARCH is True:
            # When the indexer is configured pop "title" from queryset search and use
            # fulltext results instead.
            queryset = self._filter_indexed_search_queryset(filterset, queryset)
            return self._indexed_search(
                request,
                queryset,
                indexer,
                text=filterset.form.cleaned_data.pop("title"),
            )

        # Without the indexer, the "title" filtering is kept
        queryset = filterset.filter_queryset(queryset)
        queryset = queryset.annotate_user_roles(user)
        queryset = queryset.annotate_with_numchild()

        page = self.paginate_queryset(queryset)

        if page is not None:
            items = self._compute_parents(page)
            serializer = self.get_serializer(items, many=True)
            result = self.get_paginated_response(serializer.data)
            return result

        items = self._compute_parents(queryset)
        serializer = self.get_serializer(items, many=True)
        return drf.response.Response(serializer.data)

    def _compute_parents(self, items):
        """
        Compute parents for the items by analyzing their paths and fetching missing parents.
        """
        # Build parents dictionary and collect missing parent IDs
        parents = {str(item.id): item for item in items}
        missing_parent_ids = set()

        for item in items:
            for item_id in item.path:
                if item_id not in parents and item_id not in missing_parent_ids:
                    missing_parent_ids.add(item_id)

        # Fetch missing ancestors from database
        if missing_parent_ids:
            for parent in (
                models.Item.objects.annotate_with_numchild()
                .filter(id__in=missing_parent_ids)
                .iterator()
            ):
                parents[str(parent.id)] = parent

        # Set parents for each item
        for item in items:
            item.parents = [parents[item_id] for item_id in item.path if item_id != str(item.id)]

        return items

    @drf.decorators.action(detail=True, methods=["put"], url_path="link-configuration")
    def link_configuration(self, request, *args, **kwargs):
        """Update link configuration with specific rights (cf get_abilities)."""
        # Check permissions first
        item = self.get_object()
        previous_link_reach = item.link_reach

        # Deserialize and validate the data
        serializer = serializers.LinkItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        serializer.save()

        if models.LinkReachChoices.get_priority(
            item.link_reach
        ) >= models.LinkReachChoices.get_priority(previous_link_reach):
            item.descendants().update(link_reach=None)

        return drf.response.Response(serializer.data, status=drf.status.HTTP_200_OK)

    @drf.decorators.action(detail=True, methods=["post", "delete"], url_path="favorite")
    def favorite(self, request, *args, **kwargs):
        """
        Mark or unmark the item as a favorite for the logged-in user based on the HTTP method.
        """
        # Check permissions first
        item = self.get_object()
        user = request.user

        if request.method == "POST":
            # Try to mark as favorite
            try:
                models.ItemFavorite.objects.create(item=item, user=user)
            except ValidationError:
                return drf.response.Response(
                    {"detail": "item already marked as favorite"},
                    status=drf.status.HTTP_200_OK,
                )

            posthog_capture("item_favorited", user, {}, item=item)

            # At this point the annotation is_favorite is already made by the
            # queryset.annotate_is_favorite(user) and its value is False.
            # If we want a fresh data we have to make a new queryset, apply the annotation
            # and get the item again.
            # To avoid all of this we directly set item.is_favorite to True.
            item.is_favorite = True
            serializer = self.get_serializer(item)
            return drf.response.Response(serializer.data, status=drf.status.HTTP_201_CREATED)

        # Handle DELETE method to unmark as favorite
        deleted, _ = models.ItemFavorite.objects.filter(item=item, user=user).delete()
        if deleted:
            # At this point the annotation is_favorite is already made by the
            # queryset.annotate_is_favorite(user) and its value is True.
            # If we want a fresh data we have to make a new queryset, apply the annotation
            # and get the item again.
            # To avoid all of this we directly set item.is_favorite to False.
            posthog_capture("item_unfavorited", user, {}, item=item)
            item.is_favorite = False
            serializer = self.get_serializer(item)
            return drf.response.Response(serializer.data, status=drf.status.HTTP_200_OK)
        return drf.response.Response(
            {"detail": "item was already not marked as favorite"},
            status=drf.status.HTTP_200_OK,
        )

    def _authorize_subrequest(self, request, pattern):
        """
        Shared method to authorize access based on the original URL of an Nginx subrequest
        and user permissions. Returns a dictionary of URL parameters if authorized.

        The original url is passed by nginx in the "HTTP_X_ORIGINAL_URL" header.
        See corresponding ingress configuration in Helm chart and read about the
        nginx.ingress.kubernetes.io/auth-url annotation to understand how the Nginx ingress
        is configured to do this.

        Based on the original url and the logged in user, we must decide if we authorize Nginx
        to let this request go through (by returning a 200 code) or if we block it (by returning
        a 403 error). Note that we return 403 errors without any further details for security
        reasons.

        Parameters:
        - pattern: The regex pattern to extract identifiers from the URL.

        Returns:
        - A dictionary of URL parameters if the request is authorized.
        Raises:
        - PermissionDenied if authorization fails.
        """
        # Extract the original URL from the request header
        original_url = request.META.get("HTTP_X_ORIGINAL_URL")
        if not original_url:
            logger.debug("Missing HTTP_X_ORIGINAL_URL header in subrequest")
            raise drf.exceptions.PermissionDenied()

        parsed_url = urlparse(original_url)
        match = pattern.search(unquote(parsed_url.path))

        # If the path does not match the pattern, try to extract the parameters from the query
        if not match:
            match = pattern.search(unquote(parsed_url.query))

        if not match:
            logger.debug(
                "Subrequest URL '%s' did not match pattern '%s'",
                parsed_url.path,
                pattern,
            )
            raise drf.exceptions.PermissionDenied()

        try:
            url_params = match.groupdict()
        except (ValueError, AttributeError) as exc:
            logger.debug("Failed to extract parameters from subrequest URL: %s", exc)
            raise drf.exceptions.PermissionDenied() from exc

        pk = url_params.get("pk")
        if not pk:
            logger.debug("item ID (pk) not found in URL parameters: %s", url_params)
            raise drf.exceptions.PermissionDenied()

        # Fetch the item and check if the user has access
        queryset = models.Item.objects.all()
        queryset = self._filter_suspicious_items(queryset, request.user)
        try:
            item = queryset.get(pk=pk)
        except models.Item.DoesNotExist as exc:
            logger.debug("item with ID '%s' does not exist", pk)
            raise drf.exceptions.PermissionDenied() from exc

        user_abilities = item.get_abilities(request.user)

        if not user_abilities.get(self.action, False):
            logger.debug("User '%s' lacks permission for item '%s'", request.user.id, pk)
            raise drf.exceptions.PermissionDenied()

        logger.debug("Subrequest authorization successful. Extracted parameters: %s", url_params)
        return url_params, user_abilities, request.user.id, item

    @drf.decorators.action(detail=True, methods=["get"], url_path="download")
    def download(self, request, *args, **kwargs):
        """
        Permalink endpoint for downloading an item's file.

        Returns a redirect to the current media URL for the item, so this link
        remains valid even after the item is renamed. Authentication is still
        enforced by the existing media-auth mechanism on the redirected URL.
        """
        item = self.get_object()

        if item.type != models.ItemTypeChoices.FILE:
            raise drf.exceptions.PermissionDenied()

        if item.upload_state == models.ItemUploadStateChoices.PENDING:
            raise drf.exceptions.PermissionDenied()

        redirect_url = f"{settings.MEDIA_BASE_URL}{settings.MEDIA_URL}{quote(item.file_key)}"
        return drf.response.Response(
            status=status.HTTP_302_FOUND,
            headers={"Location": redirect_url},
        )

    @drf.decorators.action(detail=True, methods=["get"], url_path="export")
    def export(self, request, *args, **kwargs):
        """Stream a recursive ZIP archive for a regular Drive folder."""
        folder = self.get_object()

        if folder.type != models.ItemTypeChoices.FOLDER or not folder.get_abilities(
            request.user
        ).get("export"):
            raise drf.exceptions.PermissionDenied()

        descendants = export_descendants(folder)
        zip_stream = build_zip_stream(descendants)
        filename = sanitize_archive_component(folder.title)
        encoded_name = quote(f"{filename}.zip", safe="")
        return StreamingHttpResponse(
            zip_stream,
            content_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
        )

    @drf.decorators.action(detail=False, methods=["get"], url_path="media-auth")
    def media_auth(self, request, *args, **kwargs):
        """
        This view is used by an Nginx subrequest to control access to an item's
        attachment file.

        When we let the request go through, we compute authorization headers that will be added to
        the request going through thanks to the nginx.ingress.kubernetes.io/auth-response-headers
        annotation. The request will then be proxied to the object storage backend who will
        respond with the file after checking the signature included in headers.
        """
        url_params, _, _, item = self._authorize_subrequest(request, MEDIA_STORAGE_URL_PATTERN)
        if not request.user.is_authenticated:
            original_url = request.META.get("HTTP_X_ORIGINAL_URL", "")
            parsed = urlparse(original_url)
            share_token = parse_qs(parsed.query).get("share_token", [None])[0]
            share_item_id = validate_item_share_token(share_token or "")
            if share_item_id != item.id:
                raise drf.exceptions.PermissionDenied()

        if item.type != models.ItemTypeChoices.FILE:
            logger.debug("Item '%s' is not a file", item.id)
            raise drf.exceptions.PermissionDenied()

        effective_upload_state = item.effective_upload_state()
        if effective_upload_state in {
            models.ItemUploadStateChoices.PENDING,
            models.ItemUploadStateChoices.EXPIRED,
        }:
            file_key_hash = safe_str_hash(item.file_key) if item.filename else None
            logger.info(
                "media_auth: denying access for not-ready item "
                "(failure_class=s3.drive.media_auth_http_403 "
                "next_action_hint=Wait for upload to finalize or re-initiate upload; "
                "audience=INTERNAL_PROXY item_id=%s upload_state=%s file_key_hash=%s)",
                item.id,
                effective_upload_state,
                file_key_hash,
            )
            raise drf.exceptions.PermissionDenied()

        if url_params.get("preview") and not utils.is_previewable_item(item):
            logger.debug("Item '%s' is not previewable", item.id)
            raise drf.exceptions.PermissionDenied()

        # Generate S3 authorization headers using the extracted URL parameters
        request = utils.generate_s3_authorization_headers(f"{url_params.get('key'):s}")

        return drf.response.Response("authorized", headers=request.headers, status=200)

    @drf.decorators.action(detail=True, methods=["get"], url_path="wopi")
    def wopi(self, request, *args, **kwargs):
        """
        This view is used to generate an access token and access token ttl in order to start
        a WOPI session for the item and the current user.
        """
        item = self.get_object()

        if not is_wopi_deployment_enabled():
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Online editing is not enabled for this deployment.",
                        code="wopi.not_enabled",
                    )
                }
            )

        if not is_wopi_backend_supported():
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Online editing is not available on this storage backend.",
                        code="wopi.backend_unsupported",
                    )
                }
            )

        if not is_wopi_discovery_configured():
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Online editing is not configured (WOPI discovery missing).",
                        code="wopi.discovery_missing",
                    )
                }
            )

        wopi_action = "edit"
        if item.upload_state == models.ItemUploadStateChoices.CREATING and (item.size or 0) == 0:
            editnew_url = get_wopi_client_config(item, request.user, action="editnew")
            if editnew_url:
                wopi_action = "editnew"

        wopi_client = get_wopi_client_config(item, request.user, action=wopi_action)
        if not wopi_client:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Online editing is not available for this file.",
                        code="wopi.file_unavailable",
                    )
                }
            )

        service = access_service.AccessUserItemService()
        access_token, access_token_ttl = service.insert_new_access(item, request.user)

        get_file_info = reverse("files-detail", kwargs={"pk": item.id})
        launch = resolve_wopi_init_launch(
            request=request,
            wopi_client=wopi_client,
            get_file_info_path=get_file_info,
        )

        return drf.response.Response(
            {
                "access_token": access_token,
                "access_token_ttl": access_token_ttl,
                "launch_url": launch.launch_url,
            },
            status=drf.status.HTTP_200_OK,
        )

    def _is_text_item_eligible(self, item: models.Item) -> bool:
        filename = str(item.filename or "")
        ext = posixpath.splitext(filename)[1].lstrip(".").lower()
        mimetype_raw = str(item.mimetype or "")
        mimetype = mimetype_raw.split(";", 1)[0].strip().lower()

        if mimetype.startswith("text/"):
            return True

        if mimetype in TEXT_LIKE_MIMETYPES_ALLOWLIST:
            return True

        if ext and (ext not in TEXT_EXTENSIONS_DENYLIST) and (ext in TEXT_EXTENSIONS_WHITELIST):
            return True

        if not self._should_sniff_text(item, mimetype=mimetype):
            return False

        return self._sniff_prefix_is_utf8_text(item)

    def _should_sniff_text(self, item: models.Item, *, mimetype: str) -> bool:
        # Only sniff for unknown/generic/non-conclusive MIME types.
        # Sniffing is bounded and happens only on-demand via the `/text/` endpoint.
        if item.type != models.ItemTypeChoices.FILE:
            return False
        return mimetype in GENERIC_MIMETYPES_FOR_TEXT_SNIFF

    def _read_item_prefix(self, item: models.Item, *, max_bytes: int) -> bytes:
        if max_bytes <= 0:
            return b""

        s3_meta = getattr(getattr(default_storage, "connection", None), "meta", None)
        s3_client = getattr(s3_meta, "client", None)
        bucket_name = getattr(default_storage, "bucket_name", None)
        if s3_client and bucket_name:
            obj = s3_client.get_object(
                Bucket=bucket_name,
                Key=item.file_key,
                Range=f"bytes=0-{max_bytes - 1}",
            )
            return obj["Body"].read(max_bytes)

        with default_storage.open(item.file_key, "rb") as fp:
            return fp.read(max_bytes)

    def _sniff_prefix_is_utf8_text(self, item: models.Item) -> bool:
        data = self._read_item_prefix(item, max_bytes=TEXT_SNIFF_PREFIX_BYTES)
        if not data:
            # Empty files are safe to treat as text.
            return True

        # UTF-8 BOM
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]

        # UTF-16 BOMs are text, but read-only via this endpoint (GET only).
        if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
            return True

        if b"\x00" in data:
            return False

        try:
            data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return False
        return True

    def _decode_text_bytes_best_effort(
        self, data: bytes, *, truncated: bool
    ) -> tuple[str, str, bool]:
        return _decode_text_bytes_best_effort(data, truncated=truncated)

    def _text_item_head_and_etag(self, item: models.Item) -> tuple[int, str]:
        head_object = utils.get_item_file_head_object(item)
        content_length = int(head_object.get("ContentLength") or 0)
        version_id = str(head_object.get("VersionId") or "").strip()
        etag = f'"{version_id}"' if version_id else str(head_object.get("ETag") or "").strip()
        return content_length, etag

    def _normalize_if_match_tag(self, v: str) -> str:
        return _normalize_if_match_tag(v)

    def _text_get(self, item: models.Item, *, content_length: int, etag: str):
        truncated = content_length > MAX_TEXT_PREVIEW_BYTES
        max_len = min(content_length, MAX_TEXT_PREVIEW_BYTES)

        data = b""
        if max_len > 0:
            s3_client = default_storage.connection.meta.client
            if truncated:
                obj = s3_client.get_object(
                    Bucket=default_storage.bucket_name,
                    Key=item.file_key,
                    Range=f"bytes=0-{MAX_TEXT_PREVIEW_BYTES - 1}",
                )
            else:
                obj = s3_client.get_object(
                    Bucket=default_storage.bucket_name,
                    Key=item.file_key,
                )
            data = obj["Body"].read(MAX_TEXT_PREVIEW_BYTES)

        decoded, encoding, editable_by_encoding = _decode_text_bytes_best_effort(
            data, truncated=truncated
        )
        read_only = (not editable_by_encoding) or truncated

        resp = drf.response.Response(
            {
                "content": decoded,
                "truncated": truncated,
                "size": content_length,
                "max_preview_bytes": MAX_TEXT_PREVIEW_BYTES,
                "etag": etag,
                "encoding": encoding,
                "read_only": read_only,
            },
            status=drf.status.HTTP_200_OK,
        )
        if etag:
            resp["ETag"] = etag
        return resp

    def _text_put_check_existing_utf8_editable(
        self, item: models.Item, *, content_length: int
    ) -> bool:
        """
        Ensure the existing file can be safely edited as UTF-8.

        Returns True when the existing bytes start with a UTF-8 BOM that should be preserved.
        Raises ValidationError when the encoding is unsupported for editing.
        """
        if content_length <= 0:
            return False

        s3_client = default_storage.connection.meta.client
        obj = s3_client.get_object(
            Bucket=default_storage.bucket_name,
            Key=item.file_key,
            Range=f"bytes=0-{content_length - 1}",
        )
        existing = obj["Body"].read(MAX_TEXT_PREVIEW_BYTES)

        if existing.startswith(b"\xff\xfe") or existing.startswith(b"\xfe\xff"):
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "This file's encoding is not supported for editing.",
                        code="item.text.unsupported_encoding",
                    )
                }
            )

        preserve_utf8_bom = existing.startswith(b"\xef\xbb\xbf")
        if preserve_utf8_bom:
            existing = existing[3:]

        try:
            existing.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "This file's encoding is not supported for editing.",
                        code="item.text.unsupported_encoding",
                    )
                }
            ) from exc

        return preserve_utf8_bom

    def _text_put(self, request, item: models.Item, *, content_length: int, etag: str):
        if content_length > MAX_TEXT_PREVIEW_BYTES:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "File is too large to edit.",
                        code="item.text.too_large_to_edit",
                    )
                }
            )

        abilities = item.get_abilities(request.user)
        if not abilities.get("update", False):
            raise drf.exceptions.PermissionDenied()

        if_match_raw = str(request.META.get("HTTP_IF_MATCH") or "").strip()
        if not if_match_raw:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "If-Match header is required.",
                        code="item.text.if_match_required",
                    )
                }
            )

        if_match_tags = {
            self._normalize_if_match_tag(t) for t in if_match_raw.split(",") if t.strip()
        }
        if self._normalize_if_match_tag(etag) not in if_match_tags:
            raise _PreconditionFailed("Le fichier a changé, rechargez", code="item.text.changed")

        content = request.data.get("content")
        if not isinstance(content, str):
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Missing text content.", code="item.text.missing_content"
                    )
                }
            )

        preserve_utf8_bom = self._text_put_check_existing_utf8_editable(
            item, content_length=content_length
        )

        payload = content.encode("utf-8")
        if preserve_utf8_bom:
            payload = b"\xef\xbb\xbf" + payload
        if len(payload) > MAX_TEXT_PREVIEW_BYTES:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Content is too large.", code="item.text.too_large"
                    )
                }
            )

        s3_client = default_storage.connection.meta.client
        put_response = s3_client.put_object(
            Bucket=default_storage.bucket_name,
            Key=item.file_key,
            Body=payload,
            ContentType=str(item.mimetype or "text/plain; charset=utf-8"),
        )

        item.size = len(payload)
        update_fields = ["size", "updated_at"]
        if item.upload_state == models.ItemUploadStateChoices.CREATING:
            item.upload_state = models.ItemUploadStateChoices.READY
            update_fields.append("upload_state")
        item.save(update_fields=update_fields)

        new_version_id = str(put_response.get("VersionId") or "").strip()
        new_etag = f'"{new_version_id}"' if new_version_id else ""
        if not new_etag:
            try:
                head2 = utils.get_item_file_head_object(item)
                head2_version = str(head2.get("VersionId") or "").strip()
                new_etag = (
                    f'"{head2_version}"' if head2_version else str(head2.get("ETag") or "").strip()
                )
            except ClientError:
                new_etag = ""

        resp = drf.response.Response(
            {"etag": new_etag},
            status=drf.status.HTTP_200_OK,
        )
        if new_etag:
            resp["ETag"] = new_etag
        return resp

    @drf.decorators.action(detail=True, methods=["get", "put"], url_path="text")
    def text(self, request, *args, **kwargs):
        """
        Read/write text content for eligible files.

        - GET returns a JSON payload with `content` (possibly truncated) and an `ETag` header.
        - PUT requires `If-Match` for optimistic locking and updates the file content.
        """
        item = self.get_object()

        if item.type != models.ItemTypeChoices.FILE:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Item is not a file.", code="item.text.not_a_file"
                    )
                }
            )

        effective_upload_state = item.effective_upload_state()
        if effective_upload_state in {
            models.ItemUploadStateChoices.PENDING,
            models.ItemUploadStateChoices.EXPIRED,
        }:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "File is not ready.", code="item.text.not_ready"
                    )
                }
            )

        if not self._is_text_item_eligible(item):
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Text preview is not available for this file.",
                        code="item.text.not_text",
                    )
                }
            )

        content_length, etag = self._text_item_head_and_etag(item)
        if request.method == "GET":
            return self._text_get(item, content_length=content_length, etag=etag)
        return self._text_put(request, item, content_length=content_length, etag=etag)


class ShareLinkViewSet(viewsets.GenericViewSet):
    """Open/browse token-enforced public share links (unauthenticated)."""

    permission_classes = [AllowAny]
    pagination_class = Pagination
    queryset = models.Item.objects.filter(hard_deleted_at__isnull=True)
    lookup_value_regex = r"[^/]+"

    def _get_root_item(self, token: str) -> models.Item:
        item_id = validate_item_share_token(token)
        if item_id is None:
            raise drf.exceptions.NotFound()

        try:
            item = self.queryset.get(id=item_id, ancestors_deleted_at__isnull=True)
        except models.Item.DoesNotExist as exc:
            raise drf.exceptions.NotFound() from exc

        if item.computed_link_reach != LinkReachChoices.PUBLIC:
            raise drf.exceptions.NotFound()

        return item

    @drf.decorators.action(detail=True, methods=["get"], url_path="browse")
    def browse(self, request, pk=None):
        """Browse the shared item subtree rooted at the share token."""
        token = pk or ""
        root = self._get_root_item(token)

        target_raw = request.query_params.get("item_id")
        if not target_raw:
            target = root
        else:
            try:
                target_id = UUID(target_raw)
            except ValueError as exc:
                raise drf.exceptions.NotFound() from exc

            if target_id == root.id:
                target = root
            else:
                target = self.queryset.filter(
                    id=target_id,
                    path__descendants=root.path,
                    ancestors_deleted_at__isnull=True,
                ).first()
                if target is None:
                    raise drf.exceptions.NotFound()

        if target.computed_link_reach != LinkReachChoices.PUBLIC:
            raise drf.exceptions.NotFound()

        item_data = PublicShareItemSerializer(target, context={"share_token": token}).data

        if target.type != models.ItemTypeChoices.FOLDER:
            return drf.response.Response(
                {"root_item_id": str(root.id), "item": item_data, "children": None}
            )

        children_qs = (
            target.children()
            .filter(deleted_at__isnull=True, hard_deleted_at__isnull=True)
            .order_by("type", "title", "id")
        )
        page = self.paginate_queryset(children_qs)
        children_data = PublicShareItemSerializer(
            page, many=True, context={"share_token": token}
        ).data
        children_payload = self.get_paginated_response(children_data).data

        return drf.response.Response(
            {
                "root_item_id": str(root.id),
                "item": item_data,
                "children": children_payload,
            }
        )


class MountShareLinkViewSet(viewsets.GenericViewSet):
    """Open/browse MountProvider share links (unauthenticated)."""

    permission_classes = [AllowAny]
    lookup_value_regex = r"[^/]+"

    class _PublicMountBrowsePagination(LimitOffsetPagination):
        default_limit = int(settings.REST_FRAMEWORK.get("PAGE_SIZE", 20))
        max_limit = int(getattr(settings, "MAX_PAGE_SIZE", 200))

    def _enabled_mount(self, mount_id: str) -> dict | None:
        mounts = list(getattr(settings, "MOUNTS_REGISTRY", []) or [])
        for mount in mounts:
            if not bool(mount.get("enabled", True)):
                continue
            if mount.get("mount_id") == mount_id:
                return mount
        return None

    def _token_hash(self, token: str) -> str:
        return hmac_sha256_16(salt="drive.mount.share_token_hash.v1", value=token)

    def _path_hash(self, *, mount_id: str, normalized_path: str) -> str:
        return hmac_sha256_16(
            salt="drive.mount.path_hash.v1",
            value=f"{mount_id}:{normalized_path}",
        )

    def _relative_path_from_request(self, request) -> str:
        raw_path = request.query_params.get("path")
        try:
            return normalize_mount_path(raw_path)
        except MountPathNormalizationError as exc:
            raise drf.exceptions.NotFound(
                drf.exceptions.ErrorDetail("Link unavailable.", code="mount.share_link.not_found")
            ) from exc

    def _join_under_root(self, *, root: str, rel: str) -> str:
        root_norm = normalize_mount_path(root)
        rel_norm = normalize_mount_path(rel)
        if rel_norm == "/":
            return root_norm
        if root_norm == "/":
            return rel_norm
        return normalize_mount_path(root_norm.rstrip("/") + rel_norm)

    def _rel_under_root(self, *, root: str, absolute: str) -> str:
        root_norm = normalize_mount_path(root)
        abs_norm = normalize_mount_path(absolute)
        if root_norm == "/":
            return abs_norm
        if abs_norm == root_norm:
            return "/"
        prefix = root_norm.rstrip("/") + "/"
        if not abs_norm.startswith(prefix):
            return "/"
        return normalize_mount_path("/" + abs_norm[len(prefix) :].lstrip("/"))

    def _entry_payload(self, *, normalized_path: str, entry: MountEntry) -> dict[str, object]:
        payload: dict[str, object] = {
            "normalized_path": normalized_path,
            "entry_type": entry.entry_type,
            "name": entry.name,
        }
        if entry.size is not None:
            payload["size"] = entry.size
        if entry.modified_at is not None:
            payload["modified_at"] = entry.modified_at
        return payload

    @drf.decorators.action(detail=True, methods=["get"], url_path="browse")
    def browse(self, request, pk=None):  # pylint: disable=too-many-locals
        """
        GET /api/v1.0/mount-share-links/{token}/browse/?path=/&limit=..&offset=..

        Browse a MountProvider public share link rooted at the stored
        (mount_id, normalized_path) mapping, without exposing mount internals.
        """
        token = pk or ""
        token_hash = self._token_hash(token)

        try:
            link = models.MountShareLink.objects.get(token=token)
        except models.MountShareLink.DoesNotExist as exc:
            logger.info(
                "mount_share_open: not_found "
                "(failure_class=mount.drive.share_token_invalid "
                "next_action_hint=Verify the share link token and retry "
                "token_hash=%s)",
                token_hash,
            )
            raise drf.exceptions.NotFound(
                drf.exceptions.ErrorDetail("Link unavailable.", code="mount.share_link.not_found")
            ) from exc

        mount_id = str(link.mount_id or "").strip()
        root_abs = normalize_mount_path(link.normalized_path)
        mount = self._enabled_mount(mount_id)
        if mount is None:
            logger.info(
                "mount_share_open: gone "
                "(failure_class=mount.drive.share_target_missing "
                "next_action_hint=Ask the sender to create a new link "
                "mount_id=%s path_hash=%s token_hash=%s)",
                mount_id,
                self._path_hash(mount_id=mount_id, normalized_path=root_abs),
                token_hash,
            )
            raise MountShareLinkGone()

        rel = self._relative_path_from_request(request)
        target_abs = self._join_under_root(root=root_abs, rel=rel)

        provider = get_mount_provider(str(mount.get("provider") or ""))
        try:
            entry_abs = provider.stat(mount=mount, normalized_path=target_abs)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                logger.info(
                    "mount_share_open: gone "
                    "(failure_class=mount.drive.share_target_missing "
                    "next_action_hint=Ask the sender to create a new link "
                    "mount_id=%s path_hash=%s token_hash=%s)",
                    mount_id,
                    self._path_hash(mount_id=mount_id, normalized_path=target_abs),
                    token_hash,
                )
                raise MountShareLinkGone() from None
            logger.info(
                "mount_share_open: failed "
                "(failure_class=%s next_action_hint=%s mount_id=%s token_hash=%s)",
                exc.failure_class,
                exc.next_action_hint,
                mount_id,
                token_hash,
            )
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Link unavailable.", code="mount.share_link.failed"
                    )
                }
            ) from None

        rel_path = self._rel_under_root(root=root_abs, absolute=entry_abs.normalized_path)
        entry_payload = self._entry_payload(normalized_path=rel_path, entry=entry_abs)
        MountShareLinkPublicEntrySerializer(data=entry_payload).is_valid(raise_exception=True)

        if entry_abs.entry_type != "folder":
            payload = {
                "normalized_path": rel_path,
                "entry": entry_payload,
                "children": None,
            }
            MountShareLinkPublicBrowseResponseSerializer(data=payload).is_valid(
                raise_exception=True
            )
            return drf.response.Response(payload, status=status.HTTP_200_OK)

        try:
            children_abs = provider.list_children(mount=mount, normalized_path=target_abs)
        except MountProviderError as exc:
            logger.info(
                "mount_share_open: children_failed "
                "(failure_class=%s next_action_hint=%s mount_id=%s token_hash=%s)",
                exc.failure_class,
                exc.next_action_hint,
                mount_id,
                token_hash,
            )
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Link unavailable.", code="mount.share_link.failed"
                    )
                }
            ) from None

        children_payload: list[dict[str, object]] = []
        for child in children_abs:
            rel_child = self._rel_under_root(root=root_abs, absolute=child.normalized_path)
            children_payload.append(self._entry_payload(normalized_path=rel_child, entry=child))

        children_sorted = sorted(
            children_payload,
            key=lambda e: (
                0 if e.get("entry_type") == "folder" else 1,
                str(e.get("name") or "").casefold(),
                posixpath.normpath(str(e.get("normalized_path") or "/")),
            ),
        )

        paginator = self._PublicMountBrowsePagination()
        page = paginator.paginate_queryset(children_sorted, request, view=self)
        MountShareLinkPublicEntrySerializer(data=page, many=True).is_valid(raise_exception=True)
        children_page = paginator.get_paginated_response(page).data

        payload = {
            "normalized_path": rel_path,
            "entry": entry_payload,
            "children": children_page,
        }
        MountShareLinkPublicBrowseResponseSerializer(data=payload).is_valid(raise_exception=True)
        return drf.response.Response(payload, status=status.HTTP_200_OK)


class ItemAccessViewSet(
    drf.mixins.CreateModelMixin,
    drf.mixins.DestroyModelMixin,
    drf.mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    API ViewSet for all interactions with item accesses.

    GET /api/v1.0/items/<resource_id>/accesses/:<item_access_id>
        Return list of all item accesses related to the logged-in user or one
        item access if an id is provided.

    POST /api/v1.0/items/<resource_id>/accesses/ with expected data:
        - user: str
        - role: str [administrator|editor|reader]
        Return newly created item access

    PUT /api/v1.0/items/<resource_id>/accesses/<item_access_id>/ with expected data:
        - role: str [owner|admin|editor|reader]
        Return updated item access

    PATCH /api/v1.0/items/<resource_id>/accesses/<item_access_id>/ with expected data:
        - role: str [owner|admin|editor|reader]
        Return partially updated item access

    DELETE /api/v1.0/items/<resource_id>/accesses/<item_access_id>/
        Delete targeted item access
    """

    lookup_field = "pk"
    permission_classes = [permissions.ItemAccessPermission]
    queryset = models.ItemAccess.objects.select_related("user", "item").all()
    resource_field_name = "item"
    serializer_class = serializers.ItemAccessSerializer

    @cached_property
    def item(self):
        """Get related item from resource ID in url and annotate user roles."""
        try:
            return models.Item.objects.annotate_user_roles(self.request.user).get(
                pk=self.kwargs["resource_id"]
            )
        except models.Item.DoesNotExist as excpt:
            raise drf.exceptions.NotFound() from excpt

    def get_serializer_class(self):
        """Use light serializer for unprivileged users."""
        return (
            serializers.ItemAccessSerializer
            if self.item.get_role(self.request.user) in PRIVILEGED_ROLES
            else serializers.ItemAccessLightSerializer
        )

    def get_serializer_context(self):
        """Extra context provided to the serializer class."""
        context = super().get_serializer_context()
        context["resource_id"] = self.kwargs["resource_id"]
        return context

    def filter_queryset(self, queryset):
        """Override to filter on related resource."""
        queryset = super().filter_queryset(queryset)
        return queryset.filter(**{self.resource_field_name: self.kwargs["resource_id"]})

    def list(self, request, *args, **kwargs):
        """
        List item accesses for an item and its ancestors.

        Returns the deepest access per target (user/team) with computed max_ancestors_role.
        For inherited accesses (not on current item), max_ancestors_role equals the access's role.

        Non-privileged users only see privileged roles to prevent information leakage.
        Results are ordered by item depth and creation date.
        """
        user = request.user
        role = self.item.get_role(user)
        if not role:
            return drf.response.Response([])

        # Get all accesses from ancestors (including current item)
        ancestors_qs = models.Item.objects.filter(
            path__ancestors=self.item.path, ancestors_deleted_at__isnull=True
        )
        accesses_qs = self.get_queryset().filter(item__in=ancestors_qs)
        if role not in PRIVILEGED_ROLES:
            accesses_qs = accesses_qs.filter(role__in=PRIVILEGED_ROLES)

        accesses_qs = accesses_qs.annotate_user_roles(user).order_by("item__path", "created_at")

        # Track max role and keep only deepest access per target
        max_role_by_target = {}
        deepest_access_by_target = {}

        for access in accesses_qs.iterator():
            target = access.target_key
            previous = max_role_by_target.get(target)
            previous_role = previous["role"] if previous else None

            # Set max_ancestors_role from previous accesses in hierarchy
            access.max_ancestors_role = previous_role
            access.max_ancestors_role_item_id = previous["item_id"] if previous else None

            max_role_by_target[target] = {
                "role": models.RoleChoices.max(previous_role, access.role),
                "item_id": access.item_id,
            }
            deepest_access_by_target[target] = access

        for access in deepest_access_by_target.values():
            # In case of inherited accesses, the max ancestors role and the max ancestors
            # item id should be the access itself because it is the one should go to update.
            if access.item.depth < self.item.depth:
                access.max_ancestors_role = access.role
                access.max_ancestors_role_item_id = access.item_id

        # Sort by depth and creation date, then serialize
        selected_accesses = sorted(
            deepest_access_by_target.values(),
            key=lambda a: (a.item.depth, a.created_at),
        )

        serializer = self.get_serializer_class()(
            selected_accesses, many=True, context=self.get_serializer_context()
        )
        return drf.response.Response(serializer.data)

    def update(self, request, *args, **kwargs):
        """
        We not use the update mixin to apply a specific behavior we can't implement using
        perform_update method.

        If the role is updated and is the same role as the max ancestors role,
        we don't want to have two consecutive explicit accesses with the same role.
        We have to delete the current access, this item will have an inherited access
        with the correct role.
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        old_role = instance.role
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data.get("role")

        # Check if the role is being updated and the new role is not "owner"
        if role and role != models.RoleChoices.OWNER:
            # Check if the access being updated is the last owner access for the resource
            if (
                self.item.is_root
                and instance.role == models.RoleChoices.OWNER
                and self.item.accesses.filter(role=models.RoleChoices.OWNER).count() == 1
            ):
                message = "Cannot change the role to a non-owner role for the last owner access."
                raise drf.exceptions.PermissionDenied({"detail": message})

        if role and instance.max_ancestors_role == role:
            # The submitted role is the same as the max ancestors role,
            # We don't want to have two consecutive explicit accesses with the same role.
            # We have to delete the current access, this item will have an inherited access
            # with the correct role.
            instance.delete()
            return drf.response.Response(status=drf.status.HTTP_204_NO_CONTENT)

        access = serializer.save()

        self._syncronize_descendants_accesses(access)

        if access.role != old_role:
            posthog_capture(
                "item_access_updated",
                request.user,
                {
                    "id": access.id,
                    "role": access.role,
                    "old_role": old_role,
                },
                item=access.item,
            )

        return drf.response.Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """Partial update the item access."""
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def perform_create(self, serializer):
        """
        Actually create the new item access:
        - Ensures the `item_id` is explicitly set from the URL
        - If the assigned role is `OWNER`, checks that the requesting user is an owner
          of the item. This is the only permission check deferred until this step;
          all other access checks are handled earlier in the permission lifecycle.
        - Sends an invitation email to the newly added user after saving the access.
        """
        role = serializer.validated_data.get("role")
        if (
            role == models.RoleChoices.OWNER
            and self.item.get_role(self.request.user) != models.RoleChoices.OWNER
        ):
            raise drf.exceptions.PermissionDenied(
                "Only owners of an item can assign other users as owners."
            )

        # Look for the max ancestors role of the item for the current user.
        ancestor_qs = (self.item.ancestors() | models.Item.objects.filter(pk=self.item.pk)).filter(
            ancestors_deleted_at__isnull=True
        )
        ancestors_roles = models.ItemAccess.objects.filter(
            item__in=ancestor_qs, user=serializer.validated_data.get("user")
        ).values_list("role", flat=True)
        max_ancestors_role = models.RoleChoices.max(*ancestors_roles)

        if models.RoleChoices.get_priority(max_ancestors_role) >= models.RoleChoices.get_priority(
            role
        ):
            raise drf.exceptions.ValidationError(
                {
                    "role": (
                        f"The role {role} you are trying to assign is lower or equal"
                        f" than the max ancestors role {max_ancestors_role}."
                    ),
                }
            )

        access = serializer.save(item_id=self.kwargs["resource_id"])
        self._syncronize_descendants_accesses(access)
        if access.user:
            access.item.send_invitation_email(
                access.user.email,
                access.role,
                self.request.user,
                self.request.user.language or settings.LANGUAGE_CODE,
            )

        posthog_capture(
            "item_access_created",
            self.request.user,
            {
                "id": access.id,
                "role": access.role,
            },
            item=access.item,
        )

    def perform_destroy(self, instance):
        """Delete the item access and capture the event."""
        access_id = instance.id
        item = instance.item
        role = instance.role
        super().perform_destroy(instance)
        posthog_capture(
            "item_access_deleted",
            self.request.user,
            {
                "id": access_id,
                "role": role,
            },
            item=item,
        )

    def _syncronize_descendants_accesses(self, access):
        """
        Syncronize the accesses of the descendants of the item
        by removing accesses with roles lower than the current user's role.
        """
        descendants = self.item.descendants().filter(ancestors_deleted_at__isnull=True)

        condition_filter = db.Q()
        if access.user:
            condition_filter |= db.Q(user=access.user)
        if access.team:
            condition_filter |= db.Q(team=access.team)

        role_priority = models.RoleChoices.get_priority(access.role)

        lower_roles = [
            role
            for role in models.RoleChoices.values
            if models.RoleChoices.get_priority(role) <= role_priority
        ]

        models.ItemAccess.objects.filter(
            condition_filter, item__in=descendants, role__in=lower_roles
        ).delete()


class InvitationViewset(
    drf.mixins.CreateModelMixin,
    drf.mixins.ListModelMixin,
    drf.mixins.RetrieveModelMixin,
    drf.mixins.DestroyModelMixin,
    drf.mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """API ViewSet for user invitations to item.

    GET /api/v1.0/items/<item_id>/invitations/:<invitation_id>/
        Return list of invitations related to that item or one
        item access if an id is provided.

    POST /api/v1.0/items/<item_id>/invitations/ with expected data:
        - email: str
        - role: str [administrator|editor|reader]
        Return newly created invitation (issuer and item are automatically set)

    PATCH /api/v1.0/items/<item_id>/invitations/:<invitation_id>/ with expected data:
        - role: str [owner|admin|editor|reader]
        Return partially updated item invitation

    DELETE  /api/v1.0/items/<item_id>/invitations/<invitation_id>/
        Delete targeted invitation
    """

    lookup_field = "id"
    pagination_class = Pagination
    permission_classes = [permissions.InvitationPermission]
    queryset = models.Invitation.objects.all().select_related("item").order_by("-created_at")
    serializer_class = serializers.InvitationSerializer
    resource_field_name = "item"

    @cached_property
    def item(self) -> models.Item:
        """Get related item from resource ID in url and annotate user roles."""
        try:
            return models.Item.objects.annotate_user_roles(self.request.user).get(
                pk=self.kwargs["resource_id"]
            )
        except models.Item.DoesNotExist as excpt:
            raise drf.exceptions.NotFound() from excpt

    def get_serializer_context(self):
        """Extra context provided to the serializer class."""
        context = super().get_serializer_context()
        context["resource_id"] = self.kwargs["resource_id"]
        return context

    def get_queryset(self):
        """Return the queryset according to the action."""
        queryset = super().get_queryset()
        queryset = queryset.filter(item=self.kwargs["resource_id"])

        user = self.request.user
        queryset = queryset.annotate_user_roles(user)

        if self.action == "list" and self.item.get_role(user) not in PRIVILEGED_ROLES:
            return queryset.none()

        return queryset

    def _validate_provided_role(self, validated_role):
        """Ensure that the validated_role can be used."""
        if (
            validated_role == models.RoleChoices.OWNER
            and self.item.get_role(self.request.user) != models.RoleChoices.OWNER
        ):
            raise drf.serializers.ValidationError(
                "Only owners of an item can invite other users as owners.",
                code="invitation_role_owner_limited_to_owners",
            )

    def perform_create(self, serializer):
        """Save invitation to a item then send an email to the invited user."""
        self._validate_provided_role(serializer.validated_data.get("role"))
        invitation = serializer.save()

        invitation.item.send_invitation_email(
            invitation.email,
            invitation.role,
            self.request.user,
            self.request.user.language or settings.LANGUAGE_CODE,
        )

        posthog_capture(
            "item_invitation_created",
            self.request.user,
            {
                "id": invitation.id,
                "role": invitation.role,
            },
            item=invitation.item,
        )

    def perform_update(self, serializer):
        """Update the invitation and capture the event."""
        self._validate_provided_role(serializer.validated_data.get("role"))
        old_role = serializer.instance.role
        super().perform_update(serializer)
        if serializer.instance.role != old_role:
            posthog_capture(
                "item_invitation_updated",
                self.request.user,
                {
                    "id": serializer.instance.id,
                    "role": serializer.instance.role,
                    "old_role": old_role,
                },
                item=serializer.instance.item,
            )

    def perform_destroy(self, instance):
        """Delete the invitation and capture the event."""
        invitation_id = instance.id
        item = instance.item
        role = instance.role
        super().perform_destroy(instance)
        posthog_capture(
            "item_invitation_deleted",
            self.request.user,
            {
                "id": invitation_id,
                "role": role,
            },
            item=item,
        )


class ReconciliationConfirmView(drf.views.APIView):
    """API endpoint to confirm user reconciliation emails."""

    permission_classes = [AllowAny]

    invalid_link_response = {"detail": "Invalid confirmation link"}

    def get(self, _request, user_type, confirmation_id):
        """Validate the confirmation ID and mark the corresponding email as checked."""
        if user_type not in ("active", "inactive"):
            return drf_response.Response(
                self.invalid_link_response,
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            confirmation_uuid = UUID(str(confirmation_id))
        except ValueError:
            return drf_response.Response(
                self.invalid_link_response,
                status=status.HTTP_400_BAD_REQUEST,
            )

        lookup = (
            {"active_email_confirmation_id": confirmation_uuid}
            if user_type == "active"
            else {"inactive_email_confirmation_id": confirmation_uuid}
        )

        try:
            reconciliation = models.UserReconciliation.objects.get(**lookup)
        except models.UserReconciliation.DoesNotExist:
            return drf_response.Response(
                self.invalid_link_response,
                status=status.HTTP_404_NOT_FOUND,
            )

        field_name = "active_email_checked" if user_type == "active" else "inactive_email_checked"
        if not getattr(reconciliation, field_name):
            setattr(reconciliation, field_name, True)
            reconciliation.save(update_fields=[field_name, "updated_at"])

        return drf_response.Response({"detail": "Confirmation received"})


class ConfigView(drf.views.APIView):
    """API ViewSet for sharing some public settings."""

    permission_classes = [AllowAny]

    def get(self, request):
        """
        GET /api/v1.0/config/
            Return a dictionary of public settings.
        """
        # SPA clients may need a CSRF cookie even before any HTML page is served.
        # Ensure it's available early so follow-up authenticated POST/PATCH requests
        # (e.g. syncing user language on first login) don't fail with CSRF 403.
        get_token(request)

        array_settings = [
            "CRISP_WEBSITE_ID",
            "DATA_UPLOAD_MAX_MEMORY_SIZE",
            "ENVIRONMENT",
            "FRONTEND_THEME",
            "FRONTEND_MORE_LINK",
            "FRONTEND_FEEDBACK_BUTTON_SHOW",
            "FRONTEND_FEEDBACK_BUTTON_IDLE",
            "FRONTEND_FEEDBACK_ITEMS",
            "FRONTEND_FEEDBACK_MESSAGES_WIDGET_ENABLED",
            "FRONTEND_FEEDBACK_MESSAGES_WIDGET_API_URL",
            "FRONTEND_FEEDBACK_MESSAGES_WIDGET_CHANNEL",
            "FRONTEND_FEEDBACK_MESSAGES_WIDGET_PATH",
            "FRONTEND_HIDE_GAUFRE",
            "FRONTEND_SILENT_LOGIN_ENABLED",
            "FRONTEND_EXTERNAL_HOME_URL",
            "FRONTEND_OPERATION_TIME_BOUNDS_MS",
            "FRONTEND_RELEASE_NOTE_ENABLED",
            "FRONTEND_ENTITLEMENTS_DISCLAIMERS",
            "FRONTEND_CSS_URL",
            "FRONTEND_JS_URL",
            "MEDIA_BASE_URL",
            "POSTHOG_KEY",
            "POSTHOG_HOST",
            "LANGUAGES",
            "LANGUAGE_CODE",
            "SENTRY_DSN",
        ]
        dict_settings = {}
        for setting in array_settings:
            if hasattr(settings, setting):
                dict_settings[setting] = getattr(settings, setting)

        dict_settings["theme_customization"] = self._load_theme_customization()

        return drf.response.Response(dict_settings)

    def _load_theme_customization(self):
        if not settings.THEME_CUSTOMIZATION_FILE_PATH:
            return {}

        cache_key = f"theme_customization_{slugify(settings.THEME_CUSTOMIZATION_FILE_PATH)}"
        theme_customization = cache.get(cache_key, {})
        if theme_customization:
            return theme_customization

        try:
            with open(settings.THEME_CUSTOMIZATION_FILE_PATH, "r", encoding="utf-8") as f:
                theme_customization = json.load(f)
        except FileNotFoundError:
            logger.error(
                "Configuration file not found: %s",
                settings.THEME_CUSTOMIZATION_FILE_PATH,
            )
        except json.JSONDecodeError:
            logger.error(
                "Configuration file is not a valid JSON: %s",
                settings.THEME_CUSTOMIZATION_FILE_PATH,
            )
        else:
            cache.set(
                cache_key,
                theme_customization,
                settings.THEME_CUSTOMIZATION_CACHE_TIMEOUT,
            )

        return theme_customization


class SDKRelayEventViewset(drf.viewsets.ViewSet):
    """API View for SDK relay interactions."""

    permission_classes = [AllowAny]

    throttle_scope = "sdk_event_relay"

    def get_permissions(self):
        """
        Return the list of permissions that this view requires.
        """
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def handle_cors(self, request, response):
        """Handle CORS preflight requests."""
        # Same approach as here:
        # https://github.com/adamchainz/django-cors-headers/blob/b04460f37cbf458984bb377d8e6afb56776c3465/src/corsheaders/middleware.py#L96
        origin = request.headers.get("origin")
        if origin and origin in settings.SDK_CORS_ALLOWED_ORIGINS:
            response[ACCESS_CONTROL_ALLOW_ORIGIN] = origin
            response[ACCESS_CONTROL_ALLOW_METHODS] = "GET, OPTIONS"

    def retrieve(self, request, pk=None):
        """
        GET /api/v1.0/sdk-relay/events/<token>/
        """
        sdk_relay = SDKRelayManager()
        event = sdk_relay.get_event(pk)

        response = drf.response.Response(event)
        self.handle_cors(request, response)
        return response

    def create(self, request):
        """
        POST /api/v1.0/sdk-relay/events/
        """
        serializer = serializers.SDKRelayEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sdk_relay = SDKRelayManager()
        sdk_relay.register_event(
            serializer.validated_data.get("token"),
            serializer.validated_data.get("event"),
        )
        return drf.response.Response(status=status.HTTP_201_CREATED)

    def options(self, request, *args, **kwargs):
        """
        OPTIONS /api/v1.0/sdk-relay/events/<token>/
        Handle CORS preflight requests.
        """
        response = drf.response.Response(status=status.HTTP_200_OK)
        self.handle_cors(request, response)
        return response


class UsageMetricViewset(drf.mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Viewset for usage metrics.
    """

    permission_classes = [HasAPIKey]
    queryset = models.User.objects.all().filter(is_active=True)
    serializer_class = serializers.UserUsageMetricSerializer
    pagination_class = Pagination

    def get_queryset(self):
        """Return the queryset filtered through `UsageMetricFilter`."""
        filterset = UsageMetricFilter(
            self.request.GET, queryset=self.queryset, request=self.request
        )
        if not filterset.is_valid():
            raise drf.exceptions.ValidationError(filterset.errors)
        return filterset.filter_queryset(self.queryset)

    def list(self, request, *args, **kwargs):
        """Handle listing with account_type branching."""
        account_type = request.query_params.get("account_type", UsageMetricAccountTypeChoices.USER)

        if account_type == UsageMetricAccountTypeChoices.ORGANIZATION:
            return self._list_organization(request)

        return super().list(request, *args, **kwargs)

    def _list_organization(self, request):
        """Aggregate storage metrics across users of an organization."""
        base_qs = models.User.objects.filter(is_active=True)
        filterset = OrganizationUsageMetricFilter(request.GET, queryset=base_qs, request=request)
        if not filterset.is_valid():
            raise drf.exceptions.ValidationError(filterset.errors)
        users = filterset.filter_queryset(base_qs)

        storage_backend = get_storage_compute_backend()
        total_storage = storage_backend.compute_storage_used(users)

        serializer = serializers.OrganizationUsageMetricSerializer(
            {
                "account_id_key": filterset.form.cleaned_data["account_id_key"],
                "account_id_value": filterset.form.cleaned_data["account_id_value"],
                "total_storage": total_storage,
            }
        )

        return drf.response.Response(
            {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [serializer.data],
            }
        )


class EntitlementsViewset(viewsets.ViewSet):
    """API View for handling entitlements."""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """
        GET /api/v1.0/entitlements/
        """
        entitlements_backend = get_entitlements_backend()
        entitlements = {}
        for method_name in dir(entitlements_backend):
            if method_name.startswith("can_"):
                method = getattr(entitlements_backend, method_name)
                if callable(method):
                    entitlements[method_name] = method(request.user)
        entitlements["context"] = entitlements_backend.get_context(request.user)
        return drf.response.Response(entitlements)


class MountViewSet(viewsets.ViewSet):
    """Mount discovery endpoint (enabled only, no-leak)."""

    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "mount_id"
    lookup_url_kwarg = "mount_id"
    lookup_value_regex = r"[a-z0-9][a-z0-9._-]{1,62}[a-z0-9]"

    _UPLOAD_LOCK = threading.Lock()
    _UPLOAD_SEMAPHORES: dict[str, threading.BoundedSemaphore] = {}

    def _enabled_mounts(self) -> list[dict]:
        mounts = list(getattr(settings, "MOUNTS_REGISTRY", []) or [])
        return [m for m in mounts if bool(m.get("enabled", True))]

    def _get_enabled_mount_or_404(self, mount_id: str) -> dict:
        mount = resolve_enabled_mount(mount_id)
        if mount:
            return mount
        raise drf.exceptions.NotFound(
            drf.exceptions.ErrorDetail("Mount not found.", code="mount.not_found")
        )

    def get_enabled_mount_or_404(self, mount_id: str) -> dict:
        """Public wrapper used by sibling views resolving enabled mounts."""
        return self._get_enabled_mount_or_404(mount_id)

    def _discovery_mount(self, mount: dict) -> dict:
        params = mount.get("params") or {}
        capabilities_raw = params.get("capabilities") if isinstance(params, dict) else {}
        capabilities = normalize_mount_capabilities(capabilities_raw)
        return {
            "mount_id": mount.get("mount_id"),
            "display_name": mount.get("display_name"),
            "provider": mount.get("provider"),
            "capabilities": capabilities,
        }

    def list(self, request):
        """
        GET /api/v1.0/mounts/
        """
        mounts = [self._discovery_mount(m) for m in self._enabled_mounts()]
        return drf.response.Response(mounts, status=status.HTTP_200_OK)

    def retrieve(self, request, mount_id: str | None = None):
        """
        GET /api/v1.0/mounts/{mount_id}/

        Disabled mounts are treated as not found for end-user surfaces.
        """
        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        return drf.response.Response(self._discovery_mount(mount), status=status.HTTP_200_OK)

    class _MountBrowsePagination(LimitOffsetPagination):
        default_limit = int(settings.REST_FRAMEWORK.get("PAGE_SIZE", 20))
        max_limit = int(getattr(settings, "MAX_PAGE_SIZE", 200))

    def _mount_capabilities(self, mount: dict) -> dict[str, bool]:
        params = mount.get("params") if isinstance(mount.get("params"), dict) else {}
        return normalize_mount_capabilities((params or {}).get("capabilities"))

    def mount_capabilities(self, mount: dict) -> dict[str, bool]:
        """Public wrapper returning normalized capabilities for one mount."""
        return self._mount_capabilities(mount)

    def _normalized_path_from_request(self, request) -> str:
        raw_path = request.query_params.get("path")
        try:
            return normalize_mount_path(raw_path)
        except MountPathNormalizationError as exc:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Invalid mount path.", code="mount.path.invalid"
                    )
                }
            ) from exc

    @classmethod
    def _upload_semaphore(cls, mount_id: str) -> threading.BoundedSemaphore:
        limit = int(getattr(settings, "MOUNTS_UPLOAD_MAX_CONCURRENCY_PER_MOUNT", 1))
        limit = max(limit, 1)

        with cls._UPLOAD_LOCK:
            sem = cls._UPLOAD_SEMAPHORES.get(mount_id)
            if sem is None:
                sem = threading.BoundedSemaphore(limit)
                cls._UPLOAD_SEMAPHORES[mount_id] = sem
            return sem

    @staticmethod
    def _sanitize_upload_filename(raw: str) -> str:
        candidate = str(raw or "").strip()
        candidate = candidate.rsplit("/", maxsplit=1)[-1].rsplit("\\", maxsplit=1)[-1].strip()
        if not candidate or candidate in {".", ".."}:
            raise ValueError("invalid_filename")
        if "/" in candidate or "\\" in candidate or "\x00" in candidate:
            raise ValueError("invalid_filename")
        if len(candidate) > 255:
            raise ValueError("filename_too_long")
        return candidate

    @staticmethod
    def _mount_entry_target_path_or_400(*, normalized_path: str, name: str) -> str:
        parent_path = parent_mount_path(normalized_path)
        try:
            return normalize_mount_path(posixpath.join(parent_path, name))
        except MountPathNormalizationError as exc:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Invalid mount path.", code="mount.path.invalid"
                    )
                }
            ) from exc

    @staticmethod
    def _mount_path_is_same_or_descendant(*, parent_path: str, candidate_path: str) -> bool:
        if candidate_path == parent_path:
            return True
        if parent_path == "/":
            return candidate_path.startswith("/")
        return candidate_path.startswith(f"{parent_path.rstrip('/')}/")

    def _mount_entry_or_400(
        self,
        *,
        provider,
        mount: dict,
        normalized_path: str,
    ) -> MountEntry:
        try:
            return provider.stat(mount=mount, normalized_path=normalized_path)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

    def _mount_entry_folder_or_400(
        self,
        *,
        provider,
        mount: dict,
        normalized_path: str,
    ) -> MountEntry:
        entry = self._mount_entry_or_400(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
        )

        if entry.entry_type != "folder":
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Mount path is not a folder.", code="mount.path.not_a_folder"
                    )
                }
            )

        return entry

    def _mount_move_target_folder_path_or_400(self, request) -> str:
        req = MountMoveRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        try:
            return normalize_mount_path(req.validated_data["target_path"])
        except MountPathNormalizationError as exc:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Invalid mount path.", code="mount.path.invalid"
                    )
                }
            ) from exc

    def _mount_create_folder_request_or_400(self, request) -> dict[str, bool | str]:
        req = MountCreateFolderRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        try:
            folder_name = self._sanitize_upload_filename(req.validated_data["name"])
        except ValueError as exc:
            code = (
                "mount.create_folder.name_too_long"
                if str(exc) == "filename_too_long"
                else "mount.create_folder.invalid_name"
            )
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail("Invalid folder name.", code=code)}
            ) from exc
        return {
            "name": folder_name,
            "reuse_existing": bool(req.validated_data.get("reuse_existing", False)),
        }

    def _mount_entry_or_none_or_400(
        self,
        *,
        provider,
        mount: dict,
        normalized_path: str,
    ) -> MountEntry | None:
        try:
            return provider.stat(mount=mount, normalized_path=normalized_path)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                return None
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

    def _mount_move_final_path_or_400(
        self,
        *,
        provider,
        mount: dict,
        source_entry: MountEntry,
        target_folder_path: str,
    ) -> str:
        target_folder = self._mount_entry_folder_or_400(
            provider=provider,
            mount=mount,
            normalized_path=target_folder_path,
        )
        if source_entry.entry_type == "folder" and self._mount_path_is_same_or_descendant(
            parent_path=source_entry.normalized_path,
            candidate_path=target_folder.normalized_path,
        ):
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Invalid move destination.", code="mount.move.invalid_destination"
                    )
                }
            )

        try:
            return normalize_mount_path(
                posixpath.join(target_folder.normalized_path, source_entry.name)
            )
        except MountPathNormalizationError as exc:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Invalid mount path.", code="mount.path.invalid"
                    )
                }
            ) from exc

    def _mount_ensure_entry_missing_or_400(
        self,
        *,
        provider,
        mount: dict,
        normalized_path: str,
        error_code: str,
    ) -> None:
        try:
            provider.stat(mount=mount, normalized_path=normalized_path)
        except MountProviderError as exc:
            if exc.public_code != "mount.path.not_found":
                raise drf.exceptions.ValidationError(
                    {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
                ) from exc
            return
        raise drf.exceptions.ValidationError(
            {"detail": drf.exceptions.ErrorDetail("Target already exists.", code=error_code)}
        )

    def _mount_rename_or_400(
        self,
        *,
        provider,
        mount: dict,
        source_path: str,
        final_path: str,
    ) -> None:
        try:
            provider.rename(
                mount=mount,
                src_normalized_path=source_path,
                dst_normalized_path=final_path,
            )
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

    def _mount_entry_response(  # pylint: disable=too-many-arguments
        self,
        *,
        mount_id: str,
        mount: dict,
        provider,
        entry: MountEntry,
        capabilities: dict[str, bool],
    ):
        payload = self._mount_entry_payload(
            mount_id=mount_id,
            mount=mount,
            provider=provider,
            entry=entry,
            capabilities=capabilities,
        )
        MountEntrySerializer(data=payload).is_valid(raise_exception=True)
        return drf.response.Response(payload, status=status.HTTP_200_OK)

    def _mount_provider_context_or_400(
        self,
        *,
        mount: dict,
        mount_id: str,
        normalized_path: str,
        unavailable_spec: MountEndpointUnavailableSpec,
    ) -> tuple[object, MountProviderIoCapabilities]:
        try:
            resolved = resolve_mount_provider_context(
                mount=mount,
                unavailable_spec=unavailable_spec,
            )
        except MountEndpointUnavailableError as exc:
            logger.info(
                "%s: unavailable (failure_class=%s next_action_hint=%s mount_id=%s path_hash=%s)",
                exc.spec.log_name,
                exc.spec.failure_class,
                exc.spec.next_action_hint,
                mount_id,
                safe_str_hash(normalized_path),
            )
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        exc.spec.public_message,
                        code=exc.spec.public_code,
                    )
                }
            ) from exc
        return resolved.provider, resolved.io_capabilities

    def mount_provider_context_or_400(
        self,
        *,
        mount: dict,
        mount_id: str,
        normalized_path: str,
        unavailable_spec: MountEndpointUnavailableSpec,
    ) -> tuple[object, MountProviderIoCapabilities]:
        """Public wrapper exposing centralized endpoint guards to sibling views."""

        return self._mount_provider_context_or_400(
            mount=mount,
            mount_id=mount_id,
            normalized_path=normalized_path,
            unavailable_spec=unavailable_spec,
        )

    def _mount_upload_provider_or_400(
        self,
        *,
        mount: dict,
        mount_id: str,
        normalized_path: str,
    ):
        provider, _io = self._mount_provider_context_or_400(
            mount=mount,
            mount_id=mount_id,
            normalized_path=normalized_path,
            unavailable_spec=MOUNT_UPLOAD_UNAVAILABLE,
        )
        return provider

    def _mount_rename_provider_or_400(
        self,
        *,
        mount: dict,
        mount_id: str,
        normalized_path: str,
    ):
        provider, _io = self._mount_provider_context_or_400(
            mount=mount,
            mount_id=mount_id,
            normalized_path=normalized_path,
            unavailable_spec=MOUNT_RENAME_UNAVAILABLE,
        )
        return provider

    def _mount_move_provider_or_400(
        self,
        *,
        mount: dict,
        mount_id: str,
        normalized_path: str,
    ):
        provider, _io = self._mount_provider_context_or_400(
            mount=mount,
            mount_id=mount_id,
            normalized_path=normalized_path,
            unavailable_spec=MOUNT_MOVE_UNAVAILABLE,
        )
        return provider

    def _mount_create_folder_provider_or_400(
        self,
        *,
        mount: dict,
        mount_id: str,
        normalized_path: str,
    ):
        provider, _io = self._mount_provider_context_or_400(
            mount=mount,
            mount_id=mount_id,
            normalized_path=normalized_path,
            unavailable_spec=MOUNT_CREATE_FOLDER_UNAVAILABLE,
        )
        return provider

    def _mount_delete_provider_or_400(
        self,
        *,
        mount: dict,
        mount_id: str,
        normalized_path: str,
    ):
        provider, _io = self._mount_provider_context_or_400(
            mount=mount,
            mount_id=mount_id,
            normalized_path=normalized_path,
            unavailable_spec=MOUNT_DELETE_UNAVAILABLE,
        )
        return provider

    @staticmethod
    def _mount_upload_file_or_400(request):
        uploaded = request.FILES.get("file") or request.data.get("file")
        if uploaded is None or not hasattr(uploaded, "chunks"):
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Missing upload file.", code="mount.upload.missing_file"
                    )
                }
            )
        return uploaded

    def _mount_upload_paths_or_400(
        self,
        *,
        folder_path: str,
        filename: str,
    ) -> tuple[str, str]:
        try:
            final_path = normalize_mount_path(posixpath.join(folder_path, filename))
        except MountPathNormalizationError as exc:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Invalid mount path.", code="mount.path.invalid"
                    )
                }
            ) from exc

        temp_name = f".drive-upload-{safe_str_hash(final_path)}.tmp"
        temp_path = normalize_mount_path(posixpath.join(folder_path, temp_name))
        return final_path, temp_path

    @staticmethod
    def _mount_upload_remove_stale_temp(*, provider, mount: dict, temp_path: str) -> None:
        try:
            provider.remove(mount=mount, normalized_path=temp_path)
        except MountProviderError as exc:
            if exc.public_code != "mount.path.not_found":
                raise

    @staticmethod
    def _mount_upload_ensure_target_missing(*, provider, mount: dict, final_path: str) -> None:
        try:
            _ = provider.stat(mount=mount, normalized_path=final_path)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                return
            raise
        raise drf.exceptions.ValidationError(
            {
                "detail": drf.exceptions.ErrorDetail(
                    "Target already exists.", code="mount.upload.target_exists"
                )
            }
        )

    @staticmethod
    def _mount_upload_limits(*, uploaded) -> tuple[int, int]:
        max_bytes = int(getattr(settings, "MOUNTS_UPLOAD_MAX_BYTES", 1) or 1)
        max_seconds = int(getattr(settings, "MOUNTS_UPLOAD_MAX_SECONDS", 1) or 1)
        max_bytes = max(max_bytes, 1)
        max_seconds = max(max_seconds, 1)

        known_size = getattr(uploaded, "size", None)
        if isinstance(known_size, int) and known_size > max_bytes:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Upload is too large.", code="mount.upload.too_large"
                    )
                }
            )

        return max_bytes, max_seconds

    @staticmethod
    def _mount_upload_write_temp(
        *,
        provider,
        mount: dict,
        uploaded,
        write_spec: tuple[str, int, int],
    ) -> int:
        temp_path, max_bytes, max_seconds = write_spec
        started = time.monotonic()
        bytes_written = 0
        chunk_size = 64 * 1024
        with provider.open_write(mount=mount, normalized_path=temp_path) as f:
            for chunk in uploaded.chunks(chunk_size):
                if not chunk:
                    continue
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise _MountUploadTooLarge()
                if (time.monotonic() - started) > max_seconds:
                    raise _MountUploadTimeout()
                f.write(chunk)
        return bytes_written

    @staticmethod
    def _mount_upload_cleanup_temp(*, provider, mount: dict, temp_path: str) -> None:
        with contextlib.suppress(MountProviderError, Exception):
            provider.remove(mount=mount, normalized_path=temp_path)

    def _mount_upload_write_temp_or_400(
        self,
        *,
        provider,
        mount: dict,
        uploaded,
        write_spec: tuple[str, int, int],
    ) -> int:
        temp_path, max_bytes, max_seconds = write_spec
        try:
            return self._mount_upload_write_temp(
                provider=provider,
                mount=mount,
                uploaded=uploaded,
                write_spec=(temp_path, max_bytes, max_seconds),
            )
        except _MountUploadTimeout:
            self._mount_upload_cleanup_temp(provider=provider, mount=mount, temp_path=temp_path)
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Upload timed out.", code="mount.upload.timeout"
                    )
                }
            ) from None
        except _MountUploadTooLarge:
            self._mount_upload_cleanup_temp(provider=provider, mount=mount, temp_path=temp_path)
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Upload is too large.", code="mount.upload.too_large"
                    )
                }
            ) from None
        except MountProviderError as exc:
            self._mount_upload_cleanup_temp(provider=provider, mount=mount, temp_path=temp_path)
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc
        except OSError:
            self._mount_upload_cleanup_temp(provider=provider, mount=mount, temp_path=temp_path)
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail("Upload failed.", code="mount.upload.failed")}
            ) from None

    @staticmethod
    def _mount_upload_finalize_rename(
        *,
        provider,
        mount: dict,
        temp_path: str,
        final_path: str,
    ) -> None:
        provider.rename(
            mount=mount,
            src_normalized_path=temp_path,
            dst_normalized_path=final_path,
        )

    def _mount_upload_finalize_or_400(
        self,
        *,
        provider,
        mount: dict,
        temp_path: str,
        final_path: str,
    ) -> None:
        try:
            self._mount_upload_finalize_rename(
                provider=provider,
                mount=mount,
                temp_path=temp_path,
                final_path=final_path,
            )
        except MountProviderError as exc:
            self._mount_upload_cleanup_temp(provider=provider, mount=mount, temp_path=temp_path)
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

    def _mount_duplicate_provider_or_400(
        self,
        *,
        mount: dict,
        mount_id: str,
        normalized_path: str,
    ):
        provider, _io = self._mount_provider_context_or_400(
            mount=mount,
            mount_id=mount_id,
            normalized_path=normalized_path,
            unavailable_spec=MOUNT_DUPLICATE_UNAVAILABLE,
        )
        return provider

    @staticmethod
    def _mount_duplicate_target_name(*, source_name: str, existing_names: set[str]) -> str:
        base_name, extension = posixpath.splitext(str(source_name or ""))
        counter = 1
        while True:
            candidate = f"{base_name}_{counter:02d}{extension}"
            if candidate not in existing_names:
                return candidate
            counter += 1

    def _mount_duplicate_paths_or_400(
        self,
        *,
        provider,
        mount: dict,
        normalized_path: str,
    ) -> tuple[str, str]:
        source_entry = self._mount_entry_file_or_400(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
        )
        folder_path = parent_mount_path(normalized_path)

        try:
            siblings = provider.list_children(mount=mount, normalized_path=folder_path)
        except MountProviderError as exc:
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        target_name = self._mount_duplicate_target_name(
            source_name=source_entry.name,
            existing_names={str(entry.name or "") for entry in siblings},
        )
        try:
            final_path = normalize_mount_path(posixpath.join(folder_path, target_name))
            temp_name = f".drive-duplicate-{safe_str_hash(final_path)}.tmp"
            temp_path = normalize_mount_path(posixpath.join(folder_path, temp_name))
        except MountPathNormalizationError as exc:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Invalid mount path.", code="mount.path.invalid"
                    )
                }
            ) from exc
        return final_path, temp_path

    @staticmethod
    def _mount_duplicate_copy_temp(
        *,
        provider,
        mount: dict,
        source_path: str,
        temp_path: str,
    ) -> None:
        chunk_size = 64 * 1024
        with (
            provider.open_read(mount=mount, normalized_path=source_path) as src,
            provider.open_write(mount=mount, normalized_path=temp_path) as dst,
        ):
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                dst.write(chunk)

    @staticmethod
    def _mount_duplicate_cleanup_temp(*, provider, mount: dict, temp_path: str) -> None:
        with contextlib.suppress(MountProviderError, Exception):
            provider.remove(mount=mount, normalized_path=temp_path)

    def _mount_duplicate_copy_or_400(
        self,
        *,
        provider,
        mount: dict,
        source_path: str,
        temp_path: str,
    ) -> None:
        try:
            self._mount_upload_remove_stale_temp(
                provider=provider, mount=mount, temp_path=temp_path
            )
            self._mount_duplicate_copy_temp(
                provider=provider,
                mount=mount,
                source_path=source_path,
                temp_path=temp_path,
            )
        except MountProviderError as exc:
            self._mount_duplicate_cleanup_temp(provider=provider, mount=mount, temp_path=temp_path)
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc
        except OSError:
            self._mount_duplicate_cleanup_temp(provider=provider, mount=mount, temp_path=temp_path)
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Duplicate failed.", code="mount.duplicate.failed"
                    )
                }
            ) from None

    def _mount_duplicate_finalize_or_400(
        self,
        *,
        provider,
        mount: dict,
        temp_path: str,
        final_path: str,
    ) -> None:
        try:
            provider.rename(
                mount=mount,
                src_normalized_path=temp_path,
                dst_normalized_path=final_path,
            )
        except MountProviderError as exc:
            self._mount_duplicate_cleanup_temp(provider=provider, mount=mount, temp_path=temp_path)
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

    def _require_capability(
        self,
        *,
        capabilities: dict[str, bool],
        capability_key: str,
        public_code: str,
        public_message: str,
    ) -> None:
        if not bool(capabilities.get(capability_key, False)):
            raise drf.exceptions.PermissionDenied(
                detail=drf.exceptions.ErrorDetail(public_message, code=public_code)
            )

    def require_capability(
        self,
        *,
        capabilities: dict[str, bool],
        capability_key: str,
        public_code: str,
        public_message: str,
    ) -> None:
        """Public wrapper enforcing a mount capability check."""
        self._require_capability(
            capabilities=capabilities,
            capability_key=capability_key,
            public_code=public_code,
            public_message=public_message,
        )

    @staticmethod
    def _mount_provider_io_capabilities(*, provider, mount: dict) -> MountProviderIoCapabilities:
        return resolve_mount_provider_io_capabilities(provider=provider, mount=mount)

    @staticmethod
    def mount_provider_io_capabilities(*, provider, mount: dict) -> MountProviderIoCapabilities:
        """Public wrapper exposing provider IO capabilities to sibling views."""
        return MountViewSet._mount_provider_io_capabilities(provider=provider, mount=mount)

    def _issue_mount_stream_ticket(
        self,
        *,
        request,
        target: MountResolvedEntry,
        ticket: MountStreamTicketSpec,
    ) -> dict[str, object]:
        version = compute_mount_entry_version(target.entry)
        mount_id = str(target.mount.get("mount_id") or "").strip()
        service = MountStreamAccessService()
        try:
            token, expires_at = service.insert_new_access(
                NewMountStreamAccess(
                    mount_id=mount_id,
                    normalized_path=target.normalized_path,
                    user=request.user,
                    version=version,
                    filename=str(target.entry.name or "stream"),
                    content_type=str(ticket.content_type or "application/octet-stream"),
                    content_length=(
                        int(target.entry.size) if target.entry.size is not None else None
                    ),
                    disposition=ticket.disposition,
                    purpose=ticket.purpose,
                    supports_range=bool(target.io.range_reads),
                )
            )
        except MountStreamAccessNotAllowed as exc:
            raise drf.exceptions.PermissionDenied(
                detail=drf.exceptions.ErrorDetail(
                    "Stream access is not allowed.", code="mount.stream.not_allowed"
                )
            ) from exc

        stream_url = request.build_absolute_uri(reverse("mount_stream", kwargs={"token": token}))
        return {
            "stream_url": stream_url,
            "expires_at": expires_at,
            "etag": f'"{version}"',
            "content_type": str(ticket.content_type or "application/octet-stream"),
            "content_length": (int(target.entry.size) if target.entry.size is not None else None),
            "supports_range": bool(target.io.range_reads),
        }

    @staticmethod
    def _mount_stream_plain_error(*, message: str, status_code: int) -> HttpResponse:
        resp = HttpResponse(
            message,
            status=status_code,
            content_type="text/plain; charset=utf-8",
        )
        resp["Cache-Control"] = "private, no-store, no-transform"
        return resp

    @staticmethod
    def mount_stream_plain_error(*, message: str, status_code: int) -> HttpResponse:
        """Public wrapper for plain-text stream errors shared across views."""
        return MountViewSet._mount_stream_plain_error(message=message, status_code=status_code)

    def _mount_stream_response(
        self,
        *,
        target: MountResolvedEntry,
        options: MountStreamOptions,
    ) -> HttpResponse:
        total_size = int(target.entry.size or 0)
        parsed_range: tuple[int, int] | None = None
        if options.supports_range and options.range_header and options.method == "GET":
            try:
                parsed_range = self._parse_single_bytes_range(
                    header_value=options.range_header, size=total_size
                )
            except (ValueError, IndexError):
                if options.invalid_range_response == "empty":
                    resp = HttpResponse(status=416)
                else:
                    resp = self._mount_stream_plain_error(
                        message="Invalid range.",
                        status_code=416,
                    )
                resp["Accept-Ranges"] = "bytes"
                resp["Content-Range"] = f"bytes */{total_size}"
                return resp

        start, end = (0, max(total_size - 1, 0))
        status_code = 200
        if isinstance(parsed_range, tuple):
            start, end = parsed_range
            status_code = 206

        content_length = (end - start + 1) if total_size > 0 else 0
        filename = str(target.entry.name or "stream")
        if options.method == "HEAD":
            resp = HttpResponse(status=status_code, content_type=options.content_type)
        else:
            resp = StreamingHttpResponse(
                streaming_content=self._iter_provider_file(
                    provider=target.provider,
                    mount=target.mount,
                    normalized_path=target.normalized_path,
                    slice_spec=(start, content_length, 64 * 1024),
                ),
                content_type=options.content_type,
                status=status_code,
            )
        if options.supports_range:
            resp["Accept-Ranges"] = "bytes"
        if options.cache_control is not None:
            resp["Cache-Control"] = options.cache_control
        resp["Content-Disposition"] = f"{options.disposition}; filename*=UTF-8''{quote(filename)}"
        resp["Content-Length"] = str(content_length)
        if options.include_etag and options.etag:
            resp["ETag"] = options.etag
        if options.include_last_modified and target.entry.modified_at is not None:
            resp["Last-Modified"] = target.entry.modified_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
        if status_code == 206:
            resp["Content-Range"] = f"bytes {start}-{end}/{total_size}"
        return resp

    def mount_stream_response(
        self, *, target: MountResolvedEntry, options: MountStreamOptions
    ) -> HttpResponse:
        """Public wrapper producing a mount-backed streaming HTTP response."""
        return self._mount_stream_response(target=target, options=options)

    def _mount_entry_abilities(
        self,
        *,
        entry: MountEntry,
        mount: dict,
        provider,
        capabilities: dict[str, bool],
    ) -> dict[str, bool]:
        io = resolve_mount_provider_io_capabilities(provider=provider, mount=mount)
        return build_mount_entry_abilities(
            entry=entry,
            mount_capabilities=capabilities,
            io_capabilities=io,
            preview_candidate=_is_mount_filename_preview_candidate(str(entry.name or "")),
            wopi_supported=bool(
                get_wopi_client_config_for_filename(filename=str(entry.name or ""))
            ),
        )

    def _mount_entry_payload(  # pylint: disable=too-many-arguments
        self,
        *,
        mount_id: str,
        mount: dict,
        provider,
        entry: MountEntry,
        capabilities: dict[str, bool],
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "mount_id": mount_id,
            "normalized_path": entry.normalized_path,
            "entry_type": entry.entry_type,
            "name": entry.name,
            "abilities": self._mount_entry_abilities(
                entry=entry, mount=mount, provider=provider, capabilities=capabilities
            ),
        }
        if entry.size is not None:
            payload["size"] = entry.size
        if entry.modified_at is not None:
            payload["modified_at"] = entry.modified_at
        return payload

    def _mount_entry_file_or_400(
        self,
        *,
        provider,
        mount: dict,
        normalized_path: str,
    ) -> MountEntry:
        try:
            entry = provider.stat(mount=mount, normalized_path=normalized_path)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        if entry.entry_type != "file":
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Mount path is not a file.", code="mount.path.not_a_file"
                    )
                }
            )

        return entry

    def mount_entry_file_or_400(
        self,
        *,
        provider,
        mount: dict,
        normalized_path: str,
    ) -> MountEntry:
        """Public wrapper resolving a mount file entry or raising a DRF error."""
        return self._mount_entry_file_or_400(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
        )

    def _mount_read_target_or_400(
        self,
        *,
        mount: dict,
        mount_id: str,
        normalized_path: str,
        unavailable_spec: MountEndpointUnavailableSpec | None = None,
    ) -> MountResolvedEntry:
        if unavailable_spec is None:
            provider = get_mount_provider(str(mount.get("provider") or ""))
            io = self._mount_provider_io_capabilities(provider=provider, mount=mount)
        else:
            provider, io = self._mount_provider_context_or_400(
                mount=mount,
                mount_id=mount_id,
                normalized_path=normalized_path,
                unavailable_spec=unavailable_spec,
            )
        entry = self._mount_entry_file_or_400(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
        )
        return MountResolvedEntry(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
            io=io,
            entry=entry,
        )

    @staticmethod
    def _parse_single_bytes_range(*, header_value: str, size: int) -> tuple[int, int] | None:
        if not header_value or not header_value.startswith("bytes="):
            return None

        spec = header_value[len("bytes=") :].strip()
        if "," in spec or "-" not in spec:
            raise ValueError("invalid_range")

        if size <= 0:
            raise IndexError("unsatisfiable_range")

        start_s, end_s = (s.strip() for s in spec.split("-", 1))
        try:
            if start_s == "":
                suffix_len = int(end_s)
                if suffix_len <= 0:
                    raise ValueError("invalid_range")
                start = max(size - suffix_len, 0)
                end = size - 1
            else:
                start = int(start_s)
                end = int(end_s) if end_s != "" else size - 1
        except ValueError as exc:
            raise ValueError("invalid_range") from exc

        if start < 0 or end < start:
            raise ValueError("invalid_range")
        if start >= size:
            raise IndexError("unsatisfiable_range")
        end = min(end, size - 1)
        return (start, end)

    @staticmethod
    def _iter_provider_file(
        *,
        provider,
        mount: dict,
        normalized_path: str,
        slice_spec: tuple[int, int, int],
    ):
        start, length, chunk_size = slice_spec
        try:
            with provider.open_read(mount=mount, normalized_path=normalized_path) as f:
                if start:
                    f.seek(start)
                remaining = length
                while remaining > 0:
                    data = f.read(min(chunk_size, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data
        except MountProviderError:
            return
        except (OSError, ValueError):
            return

    @staticmethod
    def _is_previewable_mimetype(mimetype: str | None) -> bool:
        if not mimetype:
            return False
        for allowed in getattr(settings, "ITEM_PREVIEWABLE_MIME_TYPES", []) or []:
            if not isinstance(allowed, str):
                continue
            if allowed.endswith("/"):
                if mimetype.startswith(allowed):
                    return True
            elif mimetype == allowed:
                return True
        return False

    def _mount_text_key(self, filename: str | None) -> str | None:
        lower = str(filename or "").strip().lower()
        if not lower:
            return None
        if "." in lower:
            ext = lower.rsplit(".", 1)[-1]
            return ext or None
        if lower in {"dockerfile", "makefile"}:
            return lower
        return None

    def _read_mount_entry_prefix(
        self,
        *,
        provider,
        mount: dict,
        normalized_path: str,
        max_bytes: int,
    ) -> bytes:
        if max_bytes <= 0:
            return b""
        with provider.open_read(mount=mount, normalized_path=normalized_path) as fp:
            return fp.read(max_bytes)

    def _mount_read_metadata_or_400(
        self,
        *,
        target: MountResolvedEntry,
        max_bytes: int = 4096,
    ) -> MountResolvedReadMetadata:
        try:
            head = self._read_mount_entry_prefix(
                provider=target.provider,
                mount=target.mount,
                normalized_path=target.normalized_path,
                max_bytes=max_bytes,
            )
        except MountProviderError as exc:
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc
        return MountResolvedReadMetadata(
            target=target,
            head=head,
            mimetype=utils.detect_mimetype(head, filename=str(target.entry.name or "")),
        )

    def _mount_read_target_with_metadata_or_400(  # pylint: disable=too-many-arguments
        self,
        *,
        mount: dict,
        mount_id: str,
        normalized_path: str,
        unavailable_spec: MountEndpointUnavailableSpec | None = None,
        max_bytes: int = 4096,
    ) -> MountResolvedReadMetadata:
        target = self._mount_read_target_or_400(
            mount=mount,
            mount_id=mount_id,
            normalized_path=normalized_path,
            unavailable_spec=unavailable_spec,
        )
        return self._mount_read_metadata_or_400(target=target, max_bytes=max_bytes)

    def _sniff_mount_prefix_is_utf8_text(
        self,
        *,
        provider,
        mount: dict,
        normalized_path: str,
    ) -> bool:
        data = self._read_mount_entry_prefix(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
            max_bytes=TEXT_SNIFF_PREFIX_BYTES,
        )
        if not data:
            return True
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
            return True
        if b"\x00" in data:
            return False
        try:
            data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return False
        return True

    # pylint: disable=too-many-arguments
    def _is_mount_text_entry_eligible(
        self,
        *,
        provider,
        mount: dict,
        normalized_path: str,
        entry: MountEntry,
        mimetype: str,
    ) -> bool:
        normalized_mimetype = str(mimetype or "").split(";", 1)[0].strip().lower()
        text_key = self._mount_text_key(str(entry.name or ""))
        if normalized_mimetype.startswith("text/"):
            return True
        if normalized_mimetype in TEXT_LIKE_MIMETYPES_ALLOWLIST:
            return True
        if (
            text_key
            and text_key not in TEXT_EXTENSIONS_DENYLIST
            and text_key in TEXT_EXTENSIONS_WHITELIST
        ):
            return True
        if normalized_mimetype not in GENERIC_MIMETYPES_FOR_TEXT_SNIFF:
            return False
        return self._sniff_mount_prefix_is_utf8_text(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
        )

    def _mount_text_head_and_etag(self, entry: MountEntry) -> tuple[int, str]:
        content_length = int(entry.size or 0)
        etag = f'"{compute_mount_entry_version(entry)}"'
        return content_length, etag

    def _mount_text_get(
        self,
        *,
        target: MountResolvedEntry,
        content_length: int,
        etag: str,
    ):
        truncated = content_length > MAX_TEXT_PREVIEW_BYTES
        max_len = min(content_length, MAX_TEXT_PREVIEW_BYTES)
        data = b""
        if max_len > 0:
            data = self._read_mount_entry_prefix(
                provider=target.provider,
                mount=target.mount,
                normalized_path=target.normalized_path,
                max_bytes=max_len,
            )

        decoded, encoding, editable_by_encoding = _decode_text_bytes_best_effort(
            data, truncated=truncated
        )
        read_only = (not editable_by_encoding) or truncated or (not target.io.open_write)

        resp = drf.response.Response(
            {
                "content": decoded,
                "truncated": truncated,
                "size": content_length,
                "max_preview_bytes": MAX_TEXT_PREVIEW_BYTES,
                "etag": etag,
                "encoding": encoding,
                "read_only": read_only,
            },
            status=drf.status.HTTP_200_OK,
        )
        if etag:
            resp["ETag"] = etag
        return resp

    def _mount_text_put_check_existing_utf8_editable(
        self,
        *,
        target: MountResolvedEntry,
        content_length: int,
    ) -> bool:
        if content_length <= 0:
            return False

        existing = self._read_mount_entry_prefix(
            provider=target.provider,
            mount=target.mount,
            normalized_path=target.normalized_path,
            max_bytes=min(content_length, MAX_TEXT_PREVIEW_BYTES),
        )

        if existing.startswith(b"\xff\xfe") or existing.startswith(b"\xfe\xff"):
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "This file's encoding is not supported for editing.",
                        code="mount.text.unsupported_encoding",
                    )
                }
            )

        preserve_utf8_bom = existing.startswith(b"\xef\xbb\xbf")
        if preserve_utf8_bom:
            existing = existing[3:]

        try:
            existing.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "This file's encoding is not supported for editing.",
                        code="mount.text.unsupported_encoding",
                    )
                }
            ) from exc

        return preserve_utf8_bom

    def _mount_text_put(
        self,
        request,
        *,
        target: MountResolvedEntry,
        content_length: int,
    ):
        if content_length > MAX_TEXT_PREVIEW_BYTES:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "File is too large to edit.",
                        code="mount.text.too_large_to_edit",
                    )
                }
            )

        if not target.io.open_write:
            raise drf.exceptions.PermissionDenied()

        if_match_raw = str(request.META.get("HTTP_IF_MATCH") or "").strip()
        if not if_match_raw:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "If-Match header is required.",
                        code="mount.text.if_match_required",
                    )
                }
            )

        current_entry = self._mount_entry_file_or_400(
            provider=target.provider,
            mount=target.mount,
            normalized_path=target.normalized_path,
        )
        current_content_length, current_etag = self._mount_text_head_and_etag(current_entry)
        if_match_tags = {_normalize_if_match_tag(t) for t in if_match_raw.split(",") if t.strip()}
        if _normalize_if_match_tag(current_etag) not in if_match_tags:
            raise _PreconditionFailed("Le fichier a changé, rechargez", code="mount.text.changed")

        content = request.data.get("content")
        if not isinstance(content, str):
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Missing text content.", code="mount.text.missing_content"
                    )
                }
            )

        preserve_utf8_bom = self._mount_text_put_check_existing_utf8_editable(
            target=target,
            content_length=current_content_length,
        )

        payload = content.encode("utf-8")
        if preserve_utf8_bom:
            payload = b"\xef\xbb\xbf" + payload
        if len(payload) > MAX_TEXT_PREVIEW_BYTES:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Content is too large.", code="mount.text.too_large"
                    )
                }
            )

        try:
            with target.provider.open_write(
                mount=target.mount, normalized_path=target.normalized_path
            ) as fp:
                fp.write(payload)
        except MountProviderError as exc:
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        new_entry = self._mount_entry_file_or_400(
            provider=target.provider,
            mount=target.mount,
            normalized_path=target.normalized_path,
        )
        _new_content_length, new_etag = self._mount_text_head_and_etag(new_entry)
        resp = drf.response.Response(
            {"etag": new_etag},
            status=drf.status.HTTP_200_OK,
        )
        if new_etag:
            resp["ETag"] = new_etag
        return resp

    @staticmethod
    def _mount_preview_kind(
        *,
        mimetype: str,
        is_wopi_supported: bool,
        can_inline_preview: bool,
    ) -> str:
        return classify_mount_preview_kind(
            mimetype=mimetype,
            is_wopi_supported=is_wopi_supported,
            can_inline_preview=can_inline_preview,
        )

    def _build_mount_action_url(
        self,
        *,
        request,
        mount_id: str,
        action_name: str,
        normalized_path: str,
    ) -> str:
        base = reverse(
            f"mounts-{action_name}",
            kwargs={self.lookup_url_kwarg: mount_id},
        )
        return request.build_absolute_uri(f"{base}?path={quote(normalized_path)}")

    @drf.decorators.action(detail=True, methods=["get"], url_path="browse")
    def browse(self, request, mount_id: str | None = None):
        """
        GET /api/v1.0/mounts/{mount_id}/browse/?path=/&limit=..&offset=..

        Browse a mount path and list children with deterministic ordering and
        contract-level pagination.
        """

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)

        capabilities = self._mount_capabilities(mount)
        normalized_path = self._normalized_path_from_request(request)

        provider = get_mount_provider(str(mount.get("provider") or ""))

        try:
            entry = provider.stat(mount=mount, normalized_path=normalized_path)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        entry_payload = self._mount_entry_payload(
            mount_id=target,
            mount=mount,
            provider=provider,
            entry=entry,
            capabilities=capabilities,
        )

        if entry.entry_type != "folder":
            payload = {
                "mount_id": target,
                "normalized_path": entry.normalized_path,
                "capabilities": capabilities,
                "entry": entry_payload,
                "children": None,
            }
            MountBrowseResponseSerializer(data=payload).is_valid(raise_exception=True)
            return drf.response.Response(payload, status=status.HTTP_200_OK)

        try:
            children = provider.list_children(mount=mount, normalized_path=normalized_path)
        except MountProviderError as exc:
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        children_sorted = sorted(
            children,
            key=lambda e: (
                0 if e.entry_type == "folder" else 1,
                str(e.name).casefold(),
                e.normalized_path,
            ),
        )

        paginator = self._MountBrowsePagination()
        page = paginator.paginate_queryset(children_sorted, request, view=self)
        page_payload = [
            self._mount_entry_payload(
                mount_id=target,
                mount=mount,
                provider=provider,
                entry=e,
                capabilities=capabilities,
            )
            for e in page
        ]
        MountEntrySerializer(data=page_payload, many=True).is_valid(raise_exception=True)
        children_payload = paginator.get_paginated_response(page_payload).data

        payload = {
            "mount_id": target,
            "normalized_path": entry.normalized_path,
            "capabilities": capabilities,
            "entry": entry_payload,
            "children": children_payload,
        }
        MountBrowseResponseSerializer(data=payload).is_valid(raise_exception=True)
        return drf.response.Response(payload, status=status.HTTP_200_OK)

    @drf.decorators.action(detail=True, methods=["post"], url_path="share-links")
    def share_links(self, request, mount_id: str | None = None):
        """Create (or return) a share link for a mount virtual entry."""

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.share_link",
            public_code="mount.share_link.disabled",
            public_message="Share links are not enabled for this mount.",
        )

        public_base = getattr(settings, "DRIVE_PUBLIC_URL", None)
        if not public_base:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Public sharing is not configured.",
                        code="config.public_url.missing",
                    )
                }
            )

        req = MountShareLinkCreateRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        try:
            normalized_path = normalize_mount_path(req.validated_data.get("path"))
        except MountPathNormalizationError as exc:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Invalid mount path.", code="mount.path.invalid"
                    )
                }
            ) from exc

        provider = get_mount_provider(str(mount.get("provider") or ""))
        try:
            provider.stat(mount=mount, normalized_path=normalized_path)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        link = models.MountShareLink.objects.filter(
            mount_id=target,
            normalized_path=normalized_path,
        ).first()
        if link is None:
            for _ in range(5):
                token = secrets.token_urlsafe(32)
                try:
                    link, _created = models.MountShareLink.objects.get_or_create(
                        mount_id=target,
                        normalized_path=normalized_path,
                        defaults={"token": token, "created_by": request.user},
                    )
                    break
                except IntegrityError:
                    continue
            else:
                raise drf.exceptions.ValidationError(
                    {
                        "detail": drf.exceptions.ErrorDetail(
                            "Share link could not be created.",
                            code="mount.share_link.create_failed",
                        )
                    }
                )

        share_url = join_public_url(public_base, f"share/mount/{link.token}")
        payload = {
            "mount_id": target,
            "normalized_path": normalized_path,
            "token": link.token,
            "share_url": share_url,
        }
        MountShareLinkCreateResponseSerializer(data=payload).is_valid(raise_exception=True)
        return drf.response.Response(payload, status=status.HTTP_201_CREATED)

    @drf.decorators.action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate(self, request, mount_id: str | None = None):
        """Duplicate one mount-backed file in place when the capability is enabled."""

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.duplicate",
            public_code="mount.duplicate.disabled",
            public_message="Duplicate is not enabled for this mount.",
        )

        normalized_path = self._normalized_path_from_request(request)
        provider = self._mount_duplicate_provider_or_400(
            mount=mount,
            mount_id=target,
            normalized_path=normalized_path,
        )
        self._mount_entry_file_or_400(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
        )
        final_path, temp_path = self._mount_duplicate_paths_or_400(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
        )

        self._mount_duplicate_copy_or_400(
            provider=provider,
            mount=mount,
            source_path=normalized_path,
            temp_path=temp_path,
        )
        self._mount_duplicate_finalize_or_400(
            provider=provider,
            mount=mount,
            temp_path=temp_path,
            final_path=final_path,
        )

        duplicated_entry = self._mount_entry_file_or_400(
            provider=provider,
            mount=mount,
            normalized_path=final_path,
        )
        payload = self._mount_entry_payload(
            mount_id=target,
            mount=mount,
            provider=provider,
            entry=duplicated_entry,
            capabilities=capabilities,
        )
        MountEntrySerializer(data=payload).is_valid(raise_exception=True)
        return drf.response.Response(payload, status=status.HTTP_201_CREATED)

    @drf.decorators.action(detail=True, methods=["post"], url_path="rename")
    def rename(self, request, mount_id: str | None = None):
        """Rename one mount-backed entry when the capability is enabled."""

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.rename",
            public_code="mount.rename.disabled",
            public_message="Rename is not enabled for this mount.",
        )

        normalized_path = self._normalized_path_from_request(request)
        if normalized_path == "/":
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Mount root cannot be renamed.", code="mount.rename.root_forbidden"
                    )
                }
            )

        provider = self._mount_rename_provider_or_400(
            mount=mount,
            mount_id=target,
            normalized_path=normalized_path,
        )
        try:
            source_entry = provider.stat(mount=mount, normalized_path=normalized_path)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        req = MountRenameRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        try:
            target_name = self._sanitize_upload_filename(req.validated_data["name"])
        except ValueError as exc:
            code = (
                "mount.rename.filename_too_long"
                if str(exc) == "filename_too_long"
                else "mount.rename.invalid_name"
            )
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail("Invalid mount name.", code=code)}
            ) from exc

        final_path = self._mount_entry_target_path_or_400(
            normalized_path=normalized_path,
            name=target_name,
        )
        if final_path == normalized_path:
            payload = self._mount_entry_payload(
                mount_id=target,
                mount=mount,
                provider=provider,
                entry=source_entry,
                capabilities=capabilities,
            )
            MountEntrySerializer(data=payload).is_valid(raise_exception=True)
            return drf.response.Response(payload, status=status.HTTP_200_OK)

        try:
            provider.stat(mount=mount, normalized_path=final_path)
        except MountProviderError as exc:
            if exc.public_code != "mount.path.not_found":
                raise drf.exceptions.ValidationError(
                    {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
                ) from exc
        else:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Target already exists.", code="mount.rename.target_exists"
                    )
                }
            )

        try:
            provider.rename(
                mount=mount,
                src_normalized_path=normalized_path,
                dst_normalized_path=final_path,
            )
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        try:
            renamed_entry = provider.stat(mount=mount, normalized_path=final_path)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        payload = self._mount_entry_payload(
            mount_id=target,
            mount=mount,
            provider=provider,
            entry=renamed_entry,
            capabilities=capabilities,
        )
        MountEntrySerializer(data=payload).is_valid(raise_exception=True)
        return drf.response.Response(payload, status=status.HTTP_200_OK)

    @drf.decorators.action(detail=True, methods=["post"], url_path="move")
    def move(self, request, mount_id: str | None = None):
        """Move one mount-backed entry inside the same mount."""

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.move",
            public_code="mount.move.disabled",
            public_message="Move is not enabled for this mount.",
        )

        normalized_path = self._normalized_path_from_request(request)
        if normalized_path == "/":
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Mount root cannot be moved.", code="mount.move.root_forbidden"
                    )
                }
            )

        target_folder_path = self._mount_move_target_folder_path_or_400(request)

        provider = self._mount_move_provider_or_400(
            mount=mount,
            mount_id=target,
            normalized_path=normalized_path,
        )
        source_entry = self._mount_entry_or_400(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
        )
        final_path = self._mount_move_final_path_or_400(
            provider=provider,
            mount=mount,
            source_entry=source_entry,
            target_folder_path=target_folder_path,
        )

        if final_path == normalized_path:
            return self._mount_entry_response(
                mount_id=target,
                mount=mount,
                provider=provider,
                entry=source_entry,
                capabilities=capabilities,
            )

        self._mount_ensure_entry_missing_or_400(
            provider=provider,
            mount=mount,
            normalized_path=final_path,
            error_code="mount.move.target_exists",
        )
        self._mount_rename_or_400(
            provider=provider,
            mount=mount,
            source_path=normalized_path,
            final_path=final_path,
        )
        moved_entry = self._mount_entry_or_400(
            provider=provider,
            mount=mount,
            normalized_path=final_path,
        )
        return self._mount_entry_response(
            mount_id=target,
            mount=mount,
            provider=provider,
            entry=moved_entry,
            capabilities=capabilities,
        )

    @drf.decorators.action(detail=True, methods=["post"], url_path="folders")
    def folders(self, request, mount_id: str | None = None):
        """Create one child folder inside the current mount folder."""

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.create_folder",
            public_code="mount.create_folder.disabled",
            public_message="Folder creation is not enabled for this mount.",
        )

        normalized_path = self._normalized_path_from_request(request)
        provider = self._mount_create_folder_provider_or_400(
            mount=mount,
            mount_id=target,
            normalized_path=normalized_path,
        )
        _ = self._mount_entry_folder_or_400(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
        )
        create_folder_request = self._mount_create_folder_request_or_400(request)
        folder_name = str(create_folder_request["name"])
        reuse_existing = bool(create_folder_request["reuse_existing"])
        final_path = self._mount_entry_target_path_or_400(
            normalized_path=normalize_mount_path(f"{normalized_path.rstrip('/')}/placeholder"),
            name=folder_name,
        )
        existing_entry = self._mount_entry_or_none_or_400(
            provider=provider,
            mount=mount,
            normalized_path=final_path,
        )
        if existing_entry is not None:
            if reuse_existing and existing_entry.entry_type == "folder":
                return self._mount_entry_response(
                    mount_id=target,
                    mount=mount,
                    provider=provider,
                    entry=existing_entry,
                    capabilities=capabilities,
                )
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Target already exists.", code="mount.create_folder.target_exists"
                    )
                }
            )

        try:
            provider.mkdirs(mount=mount, normalized_path=final_path)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        created_entry = self._mount_entry_folder_or_400(
            provider=provider,
            mount=mount,
            normalized_path=final_path,
        )
        return self._mount_entry_response(
            mount_id=target,
            mount=mount,
            provider=provider,
            entry=created_entry,
            capabilities=capabilities,
        )

    @drf.decorators.action(detail=True, methods=["delete"], url_path="delete")
    def delete(self, request, mount_id: str | None = None):
        """Delete one mount-backed file or empty non-root folder when enabled."""

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.delete",
            public_code="mount.delete.disabled",
            public_message="Delete is not enabled for this mount.",
        )

        normalized_path = self._normalized_path_from_request(request)
        provider = self._mount_delete_provider_or_400(
            mount=mount,
            mount_id=target,
            normalized_path=normalized_path,
        )
        entry = self._mount_entry_or_400(
            provider=provider,
            mount=mount,
            normalized_path=normalized_path,
        )
        if entry.normalized_path == "/":
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Root mount folder cannot be deleted.",
                        code="mount.delete.root_forbidden",
                    )
                }
            )

        try:
            provider.remove(mount=mount, normalized_path=normalized_path)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        return drf.response.Response(status=status.HTTP_204_NO_CONTENT)

    @drf.decorators.action(detail=True, methods=["get"], url_path="preview")
    def preview(self, request, mount_id: str | None = None):
        """
        Preview a mount entry (capability-gated).

        This endpoint streams preview content for providers that support it.
        """

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.preview",
            public_code="mount.preview.disabled",
            public_message="Preview is not enabled for this mount.",
        )

        normalized_path = self._normalized_path_from_request(request)

        provider, _io = self._mount_provider_context_or_400(
            mount=mount,
            mount_id=target,
            normalized_path=normalized_path,
            unavailable_spec=MOUNT_PREVIEW_UNAVAILABLE,
        )

        try:
            entry = provider.stat(mount=mount, normalized_path=normalized_path)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        if entry.entry_type != "file":
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Mount path is not a file.", code="mount.path.not_a_file"
                    )
                }
            )

        try:
            with provider.open_read(mount=mount, normalized_path=normalized_path) as f:
                head = f.read(4096)
        except MountProviderError as exc:
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        mimetype = utils.detect_mimetype(head, filename=str(entry.name or ""))
        if not self._is_previewable_mimetype(mimetype):
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Preview is not available for this file.",
                        code="mount.preview.not_previewable",
                    )
                }
            )

        chunk_size = 64 * 1024

        def _stream():
            try:
                with provider.open_read(mount=mount, normalized_path=normalized_path) as f:
                    while True:
                        data = f.read(chunk_size)
                        if not data:
                            break
                        yield data
            except MountProviderError:
                return
            except (OSError, ValueError):
                return

        filename = str(entry.name or "preview")
        resp = StreamingHttpResponse(
            streaming_content=_stream(),
            content_type=mimetype,
            status=status.HTTP_200_OK,
        )
        resp["Cache-Control"] = "no-store"
        resp["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(filename)}"
        if entry.size is not None:
            resp["Content-Length"] = str(int(entry.size))
        return resp

    @method_decorator(xframe_options_exempt)
    @drf.decorators.action(detail=True, methods=["get"], url_path="inline-preview")
    def inline_preview(self, request, mount_id: str | None = None):  # pylint: disable=too-many-locals
        """
        Stream an inline-previewable mount file with browser-friendly headers.

        Unlike the generic preview action, this endpoint is intended to be consumed
        directly by inline viewers such as the browser PDF iframe and media tags.
        """

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.preview",
            public_code="mount.preview.disabled",
            public_message="Preview is not enabled for this mount.",
        )

        normalized_path = self._normalized_path_from_request(request)
        metadata = self._mount_read_target_with_metadata_or_400(
            mount=mount,
            mount_id=target,
            normalized_path=normalized_path,
            unavailable_spec=MOUNT_PREVIEW_UNAVAILABLE,
        )
        read_target = metadata.target
        mimetype = metadata.mimetype
        preview_kind = self._mount_preview_kind(
            mimetype=mimetype,
            is_wopi_supported=False,
            can_inline_preview=True,
        )
        if preview_kind not in {"image", "video", "audio", "pdf"}:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Inline preview is not available for this file.",
                        code="mount.preview.not_inline_previewable",
                    )
                }
            )

        return self._mount_stream_response(
            target=read_target,
            options=MountStreamOptions(
                content_type=mimetype,
                disposition="inline",
                supports_range=bool(read_target.io.range_reads),
                range_header=str(request.META.get("HTTP_RANGE") or "").strip(),
                method="GET",
                cache_control="no-store",
                include_etag=False,
                include_last_modified=False,
                invalid_range_response="empty",
            ),
        )

    @drf.decorators.action(detail=True, methods=["post"], url_path="stream-tickets")
    def create_stream_ticket(self, request, mount_id: str | None = None):
        """Create a short-lived browser stream ticket for a mount file."""

        serializer = MountStreamTicketRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)

        try:
            normalized_path = normalize_mount_path(serializer.validated_data["path"])
        except MountPathNormalizationError as exc:
            raise drf.exceptions.ValidationError(
                {
                    "path": drf.exceptions.ErrorDetail(
                        "Invalid mount path.", code="mount.path.invalid"
                    )
                }
            ) from exc
        disposition = serializer.validated_data["disposition"]
        purpose = serializer.validated_data["purpose"]

        metadata = self._mount_read_target_with_metadata_or_400(
            mount=mount,
            mount_id=target,
            normalized_path=normalized_path,
            unavailable_spec=MOUNT_STREAM_UNAVAILABLE,
        )
        read_target = metadata.target
        mimetype = metadata.mimetype
        if purpose in {"preview", "archive"}:
            self._require_capability(
                capabilities=capabilities,
                capability_key="mount.preview",
                public_code="mount.preview.disabled",
                public_message="Preview is not enabled for this mount.",
            )
            if purpose == "preview":
                preview_kind = self._mount_preview_kind(
                    mimetype=mimetype,
                    is_wopi_supported=False,
                    can_inline_preview=True,
                )
                if preview_kind not in {"image", "video", "audio", "pdf"}:
                    raise drf.exceptions.ValidationError(
                        {
                            "detail": drf.exceptions.ErrorDetail(
                                "Preview stream is not available for this file.",
                                code="mount.stream.not_previewable",
                            )
                        }
                    )
            elif not (
                _is_archive_filename(str(read_target.entry.name or ""))
                or str(mimetype or "").split(";", 1)[0].strip().lower()
                in {"application/zip", "application/x-tar"}
            ):
                raise drf.exceptions.ValidationError(
                    {
                        "detail": drf.exceptions.ErrorDetail(
                            "Archive stream is not available for this file.",
                            code="mount.stream.not_archive",
                        )
                    }
                )

        payload = self._issue_mount_stream_ticket(
            request=request,
            target=read_target,
            ticket=MountStreamTicketSpec(
                disposition=disposition,
                purpose=purpose,
                content_type=mimetype,
            ),
        )
        MountStreamTicketResponseSerializer(data=payload).is_valid(raise_exception=True)
        return drf.response.Response(payload, status=status.HTTP_201_CREATED)

    @drf.decorators.action(detail=True, methods=["get"], url_path="preview-info")
    # pylint: disable=too-many-locals
    def preview_info(self, request, mount_id: str | None = None):
        """Resolve the actual preview contract for one mount file."""

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        normalized_path = self._normalized_path_from_request(request)

        read_target = self._mount_read_target_or_400(
            mount=mount,
            mount_id=target,
            normalized_path=normalized_path,
        )
        metadata = self._mount_read_metadata_or_400(target=read_target)
        abilities = self._mount_entry_abilities(
            entry=read_target.entry,
            mount=mount,
            provider=read_target.provider,
            capabilities=capabilities,
        )
        mimetype = metadata.mimetype
        can_inline_preview = bool(abilities.get("preview", False))
        is_wopi_supported = bool(abilities.get("wopi", False))
        can_download = bool(abilities.get("download", False))
        text_supported = can_inline_preview and self._is_mount_text_entry_eligible(
            provider=read_target.provider,
            mount=mount,
            normalized_path=normalized_path,
            entry=read_target.entry,
            mimetype=mimetype,
        )
        preview_contract = resolve_mount_preview_contract(
            filename=str(read_target.entry.name or ""),
            mimetype=mimetype,
            can_inline_preview=can_inline_preview,
            is_wopi_supported=is_wopi_supported,
            can_download=can_download,
            can_edit_text=bool(read_target.io.open_write),
            text_supported=text_supported,
        )

        inline_url = None
        if preview_contract.has_inline_url:
            inline_url = self._build_mount_action_url(
                request=request,
                mount_id=target,
                action_name="inline-preview",
                normalized_path=normalized_path,
            )

        download_url = None
        if preview_contract.can_download:
            download_url = self._build_mount_action_url(
                request=request,
                mount_id=target,
                action_name="download",
                normalized_path=normalized_path,
            )

        payload: dict[str, object] = {
            "mount_id": target,
            "normalized_path": normalized_path,
            "name": str(read_target.entry.name or ""),
            "mimetype": mimetype,
            "preview_kind": preview_contract.preview_kind,
            "is_wopi_supported": preview_contract.is_wopi_supported,
            "can_download": preview_contract.can_download,
            "can_edit_text": preview_contract.can_edit_text,
            "stream_url": None,
            "stream_expires_at": None,
            "inline_url": inline_url,
            "download_url": download_url,
        }
        if preview_contract.needs_stream_ticket and preview_contract.stream_purpose:
            stream_ticket = self._issue_mount_stream_ticket(
                request=request,
                target=read_target,
                ticket=MountStreamTicketSpec(
                    disposition="inline",
                    purpose=preview_contract.stream_purpose,
                    content_type=mimetype,
                ),
            )
            payload["stream_url"] = stream_ticket["stream_url"]
            payload["stream_expires_at"] = stream_ticket["expires_at"]
        if read_target.entry.size is not None:
            payload["size"] = read_target.entry.size
        MountPreviewInfoSerializer(data=payload).is_valid(raise_exception=True)
        return drf.response.Response(payload, status=status.HTTP_200_OK)

    @drf.decorators.action(detail=True, methods=["get", "put"], url_path="text")
    def text(self, request, mount_id: str | None = None):
        """Read or update text content for an eligible mount file."""

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.preview",
            public_code="mount.preview.disabled",
            public_message="Preview is not enabled for this mount.",
        )

        normalized_path = self._normalized_path_from_request(request)
        metadata = self._mount_read_target_with_metadata_or_400(
            mount=mount,
            mount_id=target,
            normalized_path=normalized_path,
            unavailable_spec=MOUNT_TEXT_UNAVAILABLE,
        )
        read_target = metadata.target
        mimetype = metadata.mimetype
        if not self._is_mount_text_entry_eligible(
            provider=read_target.provider,
            mount=mount,
            normalized_path=normalized_path,
            entry=read_target.entry,
            mimetype=mimetype,
        ):
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Text preview is not available for this file.",
                        code="mount.text.not_text",
                    )
                }
            )

        content_length, etag = self._mount_text_head_and_etag(read_target.entry)
        if request.method == "GET":
            return self._mount_text_get(
                target=read_target,
                content_length=content_length,
                etag=etag,
            )
        return self._mount_text_put(
            request,
            target=read_target,
            content_length=content_length,
        )

    @drf.decorators.action(detail=True, methods=["get"], url_path="wopi")
    def wopi(self, request, mount_id: str | None = None):
        """
        WOPI init for mount entries (capability-gated).

        This endpoint issues a short-lived WOPI access token bound to the
        (mount_id, normalized_path) tuple and returns a launch URL for the
        configured WOPI client (Collabora-only).
        """

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.wopi",
            public_code="mount.wopi.disabled",
            public_message="Online editing is not enabled for this mount.",
        )

        normalized_path = self._normalized_path_from_request(request)

        if not is_wopi_deployment_enabled():
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Online editing is not enabled for this deployment.",
                        code="wopi.not_enabled",
                    )
                }
            )

        if not is_wopi_discovery_configured():
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Online editing is not configured (WOPI discovery missing).",
                        code="wopi.discovery_missing",
                    )
                }
            )

        try:
            wopi_target = resolve_mount_wopi_target(
                mount=mount,
                mount_id=target,
                normalized_path=normalized_path,
            )
        except MountEndpointUnavailableError as exc:
            logger.info(
                "%s: unavailable (failure_class=%s next_action_hint=%s mount_id=%s path_hash=%s)",
                exc.spec.log_name,
                exc.spec.failure_class,
                exc.spec.next_action_hint,
                target,
                safe_str_hash(normalized_path),
            )
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        exc.spec.public_message,
                        code=exc.spec.public_code,
                    )
                }
            ) from exc
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                raise drf.exceptions.NotFound(
                    drf.exceptions.ErrorDetail("Mount path not found.", code="mount.path.not_found")
                ) from exc
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc
        except MountEntryNotAFileError as exc:
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Mount path is not a file.", code="mount.path.not_a_file"
                    )
                }
            ) from exc

        if not (
            wopi_client := get_wopi_client_config_for_filename(filename=str(wopi_target.entry.name))
        ):
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Online editing is not available for this file.",
                        code="wopi.file_unavailable",
                    )
                }
            )

        service = access_service.AccessUserMountEntryService()
        access_token, access_token_ttl, file_id = service.insert_new_access(
            mount_id=target,
            normalized_path=normalized_path,
            user=request.user,
        )

        get_file_info = reverse("mount-files-detail", kwargs={"pk": file_id})
        launch = resolve_wopi_init_launch(
            request=request,
            wopi_client=wopi_client,
            get_file_info_path=get_file_info,
        )

        return drf.response.Response(
            {
                "access_token": access_token,
                "access_token_ttl": access_token_ttl,
                "launch_url": launch.launch_url,
            },
            status=drf.status.HTTP_200_OK,
        )

    @drf.decorators.action(detail=True, methods=["post"], url_path="upload")
    def upload(self, request, mount_id: str | None = None):
        """
        Upload to a mount folder (capability-gated).

        This endpoint streams content for providers that support upload.
        """

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.upload",
            public_code="mount.upload.disabled",
            public_message="Upload is not enabled for this mount.",
        )

        normalized_path = self._normalized_path_from_request(request)

        provider = self._mount_upload_provider_or_400(
            mount=mount, mount_id=target, normalized_path=normalized_path
        )
        uploaded = self._mount_upload_file_or_400(request)

        try:
            filename = self._sanitize_upload_filename(str(getattr(uploaded, "name", "")))
        except ValueError as exc:
            code = (
                "mount.upload.filename_too_long"
                if str(exc) == "filename_too_long"
                else "mount.upload.invalid_filename"
            )
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail("Invalid filename.", code=code)}
            ) from None

        _ = self._mount_entry_folder_or_400(
            provider=provider, mount=mount, normalized_path=normalized_path
        )

        final_path, temp_path = self._mount_upload_paths_or_400(
            folder_path=normalized_path,
            filename=filename,
        )

        try:
            self._mount_upload_remove_stale_temp(
                provider=provider, mount=mount, temp_path=temp_path
            )
        except MountProviderError as exc:
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        try:
            self._mount_upload_ensure_target_missing(
                provider=provider, mount=mount, final_path=final_path
            )
        except MountProviderError as exc:
            raise drf.exceptions.ValidationError(
                {"detail": drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)}
            ) from exc

        max_bytes, max_seconds = self._mount_upload_limits(uploaded=uploaded)

        sem = self._upload_semaphore(target)
        if not sem.acquire(blocking=False):
            raise drf.exceptions.ValidationError(
                {
                    "detail": drf.exceptions.ErrorDetail(
                        "Upload is busy; retry later.", code="mount.upload.busy"
                    )
                }
            )

        try:
            bytes_written = self._mount_upload_write_temp_or_400(
                provider=provider,
                mount=mount,
                uploaded=uploaded,
                write_spec=(temp_path, max_bytes, max_seconds),
            )
        finally:
            sem.release()

        self._mount_upload_finalize_or_400(
            provider=provider,
            mount=mount,
            temp_path=temp_path,
            final_path=final_path,
        )

        logger.info(
            "mount_upload: ok (mount_id=%s path_hash=%s size=%sB)",
            target,
            safe_str_hash(final_path),
            bytes_written,
        )
        return drf.response.Response(
            {"mount_id": target, "normalized_path": final_path},
            status=status.HTTP_201_CREATED,
        )

    @drf.decorators.action(detail=True, methods=["post"], url_path="archive-extractions")
    def archive_extractions(self, request, mount_id: str | None = None):
        """
        Start a server-side archive extraction job targeting a mount folder.

        Security:
        - Refused unless MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT=true
        - Extraction currently supports ZIP archives only.
        """

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        capabilities = self._mount_capabilities(mount)
        self._require_capability(
            capabilities=capabilities,
            capability_key="mount.upload",
            public_code="mount.upload.disabled",
            public_message="Upload is not enabled for this mount.",
        )

        req = StartMountArchiveExtractionSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        try:
            job_spec = resolve_mount_archive_extraction_job(
                user=request.user,
                mount_id=target,
                mount=mount,
                start_request=MountArchiveExtractionStartRequest(
                    archive_item_id=str(req.validated_data["item_id"]),
                    destination_path=self._normalized_path_from_request(request),
                    mode=req.validated_data["mode"],
                    selection_paths=req.validated_data.get("selection_paths") or [],
                ),
            )
        except MountArchiveExtractionPreflightError as exc:
            error_detail = (
                drf.exceptions.ErrorDetail(exc.public_message, code=exc.public_code)
                if exc.public_code
                else exc.public_message
            )
            if exc.error_kind == "permission_denied":
                raise drf.exceptions.PermissionDenied(detail=error_detail) from exc
            if exc.error_kind == "not_found":
                raise drf.exceptions.NotFound(error_detail) from exc
            raise drf.exceptions.ValidationError({"detail": error_detail}) from exc

        job_id = str(uuid.uuid4())
        start_mount_archive_extraction_job(
            job_id=job_id,
            **job_spec.as_task_kwargs(),
        )

        try:
            extract_archive_to_mount_task.apply_async(
                kwargs={
                    "job_id": job_id,
                    **job_spec.as_task_kwargs(),
                },
                task_id=job_id,
            )
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            status_payload = get_mount_archive_extraction_job_status(job_id)
            status_payload.update({"state": "failed", "errors": [{"detail": str(exc)}]})
            set_mount_archive_extraction_job_status(job_id, status_payload)

        return drf.response.Response({"job_id": job_id}, status=status.HTTP_201_CREATED)

    @drf.decorators.action(detail=True, methods=["get"], url_path="download")
    def download(self, request, mount_id: str | None = None):  # pylint: disable=too-many-locals
        """
        Download a mount entry.

        This endpoint streams content for providers that support download.
        """

        target = mount_id or self.kwargs.get(self.lookup_url_kwarg) or ""
        mount = self._get_enabled_mount_or_404(target)
        normalized_path = self._normalized_path_from_request(request)

        read_target = self._mount_read_target_or_400(
            mount=mount,
            mount_id=target,
            normalized_path=normalized_path,
            unavailable_spec=MOUNT_DOWNLOAD_UNAVAILABLE,
        )
        return self._mount_stream_response(
            target=read_target,
            options=MountStreamOptions(
                content_type="application/octet-stream",
                disposition="attachment",
                supports_range=bool(read_target.io.range_reads),
                range_header=str(request.META.get("HTTP_RANGE") or "").strip(),
                method="GET",
                cache_control=None,
                include_etag=False,
                include_last_modified=False,
                invalid_range_response="empty",
            ),
        )


@method_decorator(xframe_options_exempt, name="dispatch")
class MountStreamView(drf.views.APIView):
    """Dedicated browser-stream endpoint for mount-backed files."""

    permission_classes = [AllowAny]

    def _resolve_stream_context(self, token: str):
        service = MountStreamAccessService()
        try:
            return service.get_access_user_mount_stream(token)
        except (MountStreamAccessNotFoundError, MountPathNormalizationError):
            raise drf.exceptions.NotFound(
                drf.exceptions.ErrorDetail(
                    "Stream ticket not found.", code="mount.stream.not_found"
                )
            ) from None

    def _load_stream_target(self, token: str):
        access_context = self._resolve_stream_context(token)
        mount_viewset = MountViewSet()
        mount = mount_viewset.get_enabled_mount_or_404(access_context.mount_id)
        provider, io = mount_viewset.mount_provider_context_or_400(
            mount=mount,
            mount_id=access_context.mount_id,
            normalized_path=access_context.normalized_path,
            unavailable_spec=MOUNT_STREAM_UNAVAILABLE,
        )

        target = MountResolvedEntry(
            provider=provider,
            mount=mount,
            normalized_path=access_context.normalized_path,
            io=io,
            entry=mount_viewset.mount_entry_file_or_400(
                provider=provider,
                mount=mount,
                normalized_path=access_context.normalized_path,
            ),
        )
        current_version = compute_mount_entry_version(target.entry)
        if current_version != access_context.version:
            return mount_viewset.mount_stream_plain_error(
                message="Stream ticket is stale.",
                status_code=409,
            )

        if access_context.purpose in {"preview", "archive"}:
            capabilities = mount_viewset.mount_capabilities(mount)
            mount_viewset.require_capability(
                capabilities=capabilities,
                capability_key="mount.preview",
                public_code="mount.preview.disabled",
                public_message="Preview is not enabled for this mount.",
            )

        return mount_viewset, target, access_context

    # pylint: disable=method-hidden
    def head(self, request, token: str):
        """Serve HEAD requests for short-lived mount browser-stream URLs."""
        loaded = self._load_stream_target(token)
        if isinstance(loaded, HttpResponse):
            return loaded
        mount_viewset, target, access_context = loaded
        return mount_viewset.mount_stream_response(
            target=target,
            options=MountStreamOptions(
                content_type=access_context.content_type,
                disposition=access_context.disposition,
                supports_range=bool(access_context.supports_range and target.io.range_reads),
                range_header=str(request.META.get("HTTP_RANGE") or "").strip(),
                method="HEAD",
                etag=f'"{access_context.version}"',
            ),
        )

    def get(self, request, token: str):
        """Serve GET requests for short-lived mount browser-stream URLs."""
        loaded = self._load_stream_target(token)
        if isinstance(loaded, HttpResponse):
            return loaded
        mount_viewset, target, access_context = loaded
        return mount_viewset.mount_stream_response(
            target=target,
            options=MountStreamOptions(
                content_type=access_context.content_type,
                disposition=access_context.disposition,
                supports_range=bool(access_context.supports_range and target.io.range_reads),
                range_header=str(request.META.get("HTTP_RANGE") or "").strip(),
                method="GET",
                etag=f'"{access_context.version}"',
            ),
        )
