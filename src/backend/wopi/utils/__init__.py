"""Utils for WOPI"""

import re
from dataclasses import dataclass
from os.path import splitext
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage

from core import models
from core.mounts.providers.base import MountEntry
from core.utils.no_leak import sha256_16
from wopi.services.s3_prerequisites import check_wopi_s3_bucket_versioning
from wopi.tasks.configure_wopi import (
    WOPI_CONFIGURATION_CACHE_KEY,
    WOPI_DEFAULT_CONFIGURATION,
)

LAUNCH_URL_PLACEHOLDER_REGEX = r"(<(?P<name>[a-z]+)=(?P<placeholder>[a-zA-Z0-9_]+)&?>)"


@dataclass(frozen=True, slots=True)
class ResolvedWopiInitContext:
    """Shared request-derived context for WOPI init launch construction."""

    language: str | None
    wopi_src_base_url: str


@dataclass(frozen=True, slots=True)
class ResolvedWopiInitLaunch:
    """Shared WOPI init launch contract used by Items and Mounts adapters."""

    client_url: str
    language: str | None
    wopi_src_base_url: str
    launch_url: str


def is_wopi_deployment_enabled() -> bool:
    """Return whether WOPI clients are configured for this deployment."""

    return bool(getattr(settings, "WOPI_CLIENTS", []))


def get_wopi_discovery_configuration():
    """Return cached WOPI discovery configuration with the project default fallback."""

    return cache.get(WOPI_CONFIGURATION_CACHE_KEY, default=WOPI_DEFAULT_CONFIGURATION)


def is_wopi_discovery_configured() -> bool:
    """Return whether WOPI discovery is configured for init flows."""

    wopi_configuration = get_wopi_discovery_configuration()
    return bool(
        wopi_configuration
        and (wopi_configuration.get("mimetypes") or wopi_configuration.get("extensions"))
    )


def resolve_wopi_init_context(request) -> ResolvedWopiInitContext:
    """Resolve request-derived WOPI init context shared by Items and Mounts."""

    language = (
        request.user.language
        if request.user.is_authenticated and request.user.language
        else settings.LANGUAGE_CODE
    )
    wopi_src_base_url = (
        getattr(settings, "WOPI_SRC_BASE_URL", None)
        or getattr(settings, "DRIVE_PUBLIC_URL", None)
        or request.build_absolute_uri("/").rstrip("/")
    )
    return ResolvedWopiInitContext(
        language=language,
        wopi_src_base_url=str(wopi_src_base_url).rstrip("/"),
    )


def resolve_wopi_init_launch(
    *,
    request,
    wopi_client,
    get_file_info_path: str,
) -> ResolvedWopiInitLaunch:
    """Resolve the shared launch URL contract for one WOPI init response."""

    context = resolve_wopi_init_context(request)
    client_url = wopi_client["url"] if isinstance(wopi_client, dict) else str(wopi_client or "")
    return ResolvedWopiInitLaunch(
        client_url=client_url,
        language=context.language,
        wopi_src_base_url=context.wopi_src_base_url,
        launch_url=compute_wopi_launch_url(
            client_url,
            get_file_info_path,
            context.language,
            wopi_src_base_url=context.wopi_src_base_url,
        ),
    )


def is_wopi_backend_supported() -> bool:
    """
    Return whether the configured storage backend supports the WOPI flows.

    Current WOPI implementation uses S3 operations via django-storages, so it
    requires a backend exposing an S3-like client and a bucket name.
    """
    bucket_name = getattr(default_storage, "bucket_name", None)
    connection = getattr(default_storage, "connection", None)
    client = getattr(getattr(connection, "meta", None), "client", None)
    if not (bucket_name and client):
        return False

    return bool(check_wopi_s3_bucket_versioning().ok)


def is_item_wopi_supported(item, user):
    """
    Check if an item is supported by WOPI.
    """
    return bool(get_wopi_client_config(item, user))


def get_wopi_client_config(item, user, *, action: str = "edit"):
    """
    Get the WOPI client configuration (launch URL template) for an item.

    Supported actions:
    - "edit" (default)
    - "editnew" (for create-new flows on 0-byte placeholders)
    """
    if not is_wopi_deployment_enabled():
        return None

    if not is_wopi_backend_supported():
        return None

    if (
        item.type != models.ItemTypeChoices.FILE
        or item.upload_state == models.ItemUploadStateChoices.SUSPICIOUS
        or (item.creator != user and item.upload_state != models.ItemUploadStateChoices.READY)
    ):
        return None

    wopi_configuration = get_wopi_discovery_configuration()

    if not wopi_configuration:
        return None

    extensions_key = "extensions" if action != "editnew" else "extensions_editnew"
    mimetypes_key = "mimetypes" if action != "editnew" else "mimetypes_editnew"

    result = None
    # Extension must always be checked first.
    extensions_map = wopi_configuration.get(extensions_key, {})
    mimetypes_map = wopi_configuration.get(mimetypes_key, {})

    if item.extension in extensions_map:
        result = extensions_map[item.extension]
    elif item.mimetype in mimetypes_map:
        result = mimetypes_map[item.mimetype]

    return result


def get_wopi_client_config_for_filename(
    *,
    filename: str,
    mimetype: str | None = None,
    action: str = "edit",
):
    """
    Return the WOPI client configuration for a mount-backed file.

    Unlike `get_wopi_client_config` this does not depend on the S3 backend
    (mount-backed WOPI is provider-driven).
    """
    if not is_wopi_deployment_enabled():
        return None

    wopi_configuration = get_wopi_discovery_configuration()
    if not wopi_configuration:
        return None

    _, ext = splitext(str(filename or ""))
    ext_key = ext.lstrip(".") if ext else None

    extensions_key = "extensions" if action != "editnew" else "extensions_editnew"
    mimetypes_key = "mimetypes" if action != "editnew" else "mimetypes_editnew"

    result = None
    if ext_key and ext_key in wopi_configuration.get(extensions_key, {}):
        result = wopi_configuration[extensions_key][ext_key]
    elif mimetype and mimetype in wopi_configuration.get(mimetypes_key, {}):
        result = wopi_configuration[mimetypes_key][mimetype]

    return result


def compute_mount_entry_version(entry: MountEntry) -> str:
    """
    Compute a deterministic application-level version string for a mount entry.

    This version changes when mount metadata changes (size and/or modified_at).
    """
    size_part = "" if entry.size is None else str(int(entry.size))
    modified_part = "" if entry.modified_at is None else entry.modified_at.isoformat()
    digest = sha256_16(f"mount:v1:{size_part}:{modified_part}")
    return f"m1-{digest}"


def compute_wopi_launch_url(
    launch_url,
    get_file_info_path,
    lang=None,
    *,
    wopi_src_base_url: str | None = None,
):
    """
    Compute the WOPI launch URL for an item.
    """
    if isinstance(launch_url, dict):
        launch_url = launch_url.get("url") or ""
    launch_url = str(launch_url)
    launch_url = launch_url.rstrip("?")
    launch_url = launch_url.rstrip("&")

    wopi_src_base_url = wopi_src_base_url or settings.WOPI_SRC_BASE_URL
    wopi_src = get_file_info_path
    if wopi_src_base_url:
        wopi_src = f"{wopi_src_base_url}{get_file_info_path}"

    query_params = {
        "WOPISrc": wopi_src,
        "closebutton": "false",  # Collabora specific
    }

    if lang:
        query_params["lang"] = lang

    # List of placeholders available here
    # https://learn.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/online/discovery#placeholder-values
    placeholders = {
        "UI_LLCC": lang,
        "DC_LLCC": lang,
        "DISABLE_CHAT": settings.WOPI_DISABLE_CHAT,
    }

    parsed_launch_url = urlparse(launch_url)

    matches = re.finditer(LAUNCH_URL_PLACEHOLDER_REGEX, launch_url)

    for match in matches:
        if (
            match.group("placeholder") in placeholders
            and placeholders[match.group("placeholder")] is not None
        ):
            query_params[match.group("name")] = placeholders[match.group("placeholder")]

    return parsed_launch_url._replace(query=urlencode(query_params)).geturl()
