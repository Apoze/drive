"""WOPI viewsets module."""

import logging
import time
import uuid
from os.path import splitext

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import StreamingHttpResponse

import botocore.exceptions
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from sentry_sdk import capture_exception

from core.api.utils import get_item_file_head_object
from core.models import Item, ItemUploadStateChoices
from core.mounts.providers.base import MountProviderError
from core.services.mount_capabilities import (
    MountEndpointUnavailableError,
    MountEntryNotAFileError,
    normalize_mount_capabilities,
    resolve_enabled_mount,
    resolve_mount_wopi_target,
)
from core.services.s3_streaming import stream_to_s3_object
from core.utils.no_leak import safe_str_hash
from wopi.authentication import (
    WopiAccessTokenAuthentication,
    WopiMountAccessTokenAuthentication,
)
from wopi.permissions import AccessTokenPermission, MountAccessTokenPermission
from wopi.services.lock import LockService, MountLockService
from wopi.utils import get_wopi_client_config

logger = logging.getLogger(__name__)


HTTP_X_WOPI_LOCK = "HTTP_X_WOPI_LOCK"
HTTP_X_WOPI_OLD_LOCK = "HTTP_X_WOPI_OLDLOCK"
HTTP_X_WOPI_OVERRIDE = "HTTP_X_WOPI_OVERRIDE"

X_WOPI_INVALIDFILENAMERROR = "X-WOPI-InvalidFileNameError"
X_WOPI_ITEMVERSION = "X-WOPI-ItemVersion"
X_WOPI_LOCK = "X-WOPI-Lock"


WOPI_SHARED_DETAIL_POST_ACTIONS = {
    "LOCK": "_lock",
    "GET_LOCK": "_get_lock",
    "REFRESH_LOCK": "_refresh_lock",
    "UNLOCK": "_unlock",
}

WOPI_CHECK_FILE_INFO_SHARED_FLAGS = {
    "UserCanPresent": False,
    "UserCanAttend": False,
    "UserCanNotWriteRelative": True,
    "SupportsUpdate": True,
    "SupportsCobalt": False,
    "SupportsContainers": False,
    "SupportsEcosystem": False,
    "SupportsGetFileWopiSrc": False,
    "SupportsGetLock": True,
    "SupportsLocks": True,
    "SupportsUserInfo": False,
}


def build_wopi_check_file_info_base(
    *,
    base_file_name: str,
    owner_id: str,
    user,
    size: int,
    version: str,
) -> dict[str, object]:
    """Return the shared WOPI CheckFileInfo contract base."""

    return {
        "BaseFileName": base_file_name,
        "OwnerId": owner_id,
        "IsAnonymousUser": user.is_anonymous,
        "UserFriendlyName": user.full_name if not user.is_anonymous else None,
        "Size": size,
        "UserId": str(user.id),
        "Version": version,
        **WOPI_CHECK_FILE_INFO_SHARED_FLAGS,
    }


def get_wopi_max_expected_size_preflight_response(
    *, actual_size: int | None, max_expected_size: str | None
) -> Response | None:
    """Return the standard WOPI GetFile max-expected-size preflight response."""

    if max_expected_size and actual_size is not None:
        if int(actual_size) > int(max_expected_size):
            return Response(status=412)
    return None


def build_wopi_get_file_streaming_response(
    *,
    streaming_content,
    content_type: str,
    version: str,
    size: int | None,
) -> StreamingHttpResponse:
    """Return the shared WOPI GetFile streaming response contract."""

    headers = {X_WOPI_ITEMVERSION: version}
    if size is not None:
        headers["Content-Length"] = str(int(size))

    return StreamingHttpResponse(
        streaming_content=streaming_content,
        content_type=content_type,
        headers=headers,
        status=200,
    )


def get_wopi_put_override_preflight_response(*, override: str | None) -> Response | None:
    """Return the standard WOPI PutFile override preflight response."""

    if override != "PUT":
        return Response(status=404)
    return None


def build_wopi_put_file_success_response(*, version: str) -> Response:
    """Return the standard WOPI PutFile success response contract."""

    return Response(status=200, headers={X_WOPI_ITEMVERSION: version})


class WopiLockRuntimeMixin:
    """Shared WOPI lock lifecycle runtime for Items and Mounts."""

    detail_post_actions = WOPI_SHARED_DETAIL_POST_ACTIONS

    def _lock_service_or_response(self, request, pk=None) -> object | Response:
        """Return the lock service or an HTTP response when the target is invalid."""

        raise NotImplementedError

    @staticmethod
    def _lock_conflict_response(*, current_lock_value: str):
        """Return a deterministic lock conflict response (WOPI 409 + X-WOPI-Lock)."""

        return Response(status=409, headers={X_WOPI_LOCK: current_lock_value})

    def detail_post(self, request, pk=None):
        """
        Shared detail POST dispatcher for WOPI runtime actions.

        The action is determined by the X-WOPI-Override header.
        """

        override = request.META.get(HTTP_X_WOPI_OVERRIDE)
        if override not in self.detail_post_actions:
            return Response(status=404)

        preflight_hook = getattr(self, "_detail_post_preflight", None)
        if callable(preflight_hook):
            # pylint: disable=not-callable
            preflight = preflight_hook(request, pk)
            if preflight is not None:
                return preflight

        post_action = self.detail_post_actions[override]
        return getattr(self, post_action)(request, pk)

    def _lock(self, request, pk=None):
        """Acquire or refresh a lock using the shared WOPI lock contract."""

        lock_value = request.META.get(HTTP_X_WOPI_LOCK)
        if not lock_value:
            return Response(status=400)

        if request.META.get(HTTP_X_WOPI_OLD_LOCK, False):
            return self._unlock_and_relock(request, pk)

        lock_service = self._lock_service_or_response(request, pk)
        if isinstance(lock_service, Response):
            return lock_service

        if not lock_service.is_locked():
            lock_service.lock(lock_value)
            return Response(status=200)

        if not lock_service.is_lock_valid(lock_value):
            return self._lock_conflict_response(
                current_lock_value=lock_service.get_lock(default="")
            )

        lock_service.refresh_lock()
        return Response(status=200)

    def _get_lock(self, request, pk=None):
        """Return the current lock value using the shared WOPI lock contract."""

        lock_service = self._lock_service_or_response(request, pk)
        if isinstance(lock_service, Response):
            return lock_service

        return Response(status=200, headers={X_WOPI_LOCK: lock_service.get_lock(default="")})

    def _refresh_lock(self, request, pk=None):
        """Refresh the current lock using the shared WOPI lock contract."""

        lock_value = request.META.get(HTTP_X_WOPI_LOCK)
        if not lock_value:
            return Response(status=400)

        lock_service = self._lock_service_or_response(request, pk)
        if isinstance(lock_service, Response):
            return lock_service

        current_lock_value = lock_service.get_lock(default="")
        if current_lock_value != lock_value:
            return self._lock_conflict_response(current_lock_value=current_lock_value)

        lock_service.refresh_lock()
        return Response(status=200)

    def _unlock(self, request, pk=None):
        """Release the current lock using the shared WOPI lock contract."""

        lock_value = request.META.get(HTTP_X_WOPI_LOCK)
        if not lock_value:
            return Response(status=400)

        lock_service = self._lock_service_or_response(request, pk)
        if isinstance(lock_service, Response):
            return lock_service

        current_lock_value = lock_service.get_lock(default="")
        if current_lock_value != lock_value:
            return self._lock_conflict_response(current_lock_value=current_lock_value)

        lock_service.unlock()
        return Response(status=200)

    def _unlock_and_relock(self, request, pk=None):
        """Replace the current lock using the shared WOPI lock contract."""

        old_lock_value = request.META.get(HTTP_X_WOPI_OLD_LOCK)
        new_lock_value = request.META.get(HTTP_X_WOPI_LOCK)
        if not old_lock_value or not new_lock_value:
            return Response(status=400)

        lock_service = self._lock_service_or_response(request, pk)
        if isinstance(lock_service, Response):
            return lock_service

        current_lock_value = lock_service.get_lock(default="")
        if current_lock_value != old_lock_value:
            return self._lock_conflict_response(current_lock_value=current_lock_value)

        lock_service.unlock()
        lock_service.lock(new_lock_value)
        return Response(status=200)


class WopiFileContentRuntimeMixin:
    """Shared HTTP dispatch for WOPI GetFile/PutFile contents routes."""

    @action(detail=True, methods=["get", "post"], url_path="contents")
    def file_content(self, request, pk=None):
        """Dispatch the WOPI contents route to GetFile or PutFile."""

        if request.method == "GET":
            return self._get_file_content(request, pk)
        if request.method == "POST":
            return self._put_file_content(request, pk)

        return Response(status=405)


class WopiViewSet(WopiFileContentRuntimeMixin, WopiLockRuntimeMixin, viewsets.ViewSet):
    """
    WOPI ViewSet
    """

    authentication_classes = [WopiAccessTokenAuthentication]
    permission_classes = [AccessTokenPermission]
    # WOPI PutFile must stream the request body; DRF parsing would consume it and/or
    # encourage buffering via request.body. Keep parsers disabled for this viewset family.
    parser_classes = []
    queryset = Item.objects.all()

    detail_post_actions = {
        **WOPI_SHARED_DETAIL_POST_ACTIONS,
        "RENAME_FILE": "_rename_file",
    }

    def get_file_id(self):
        """Get the file id from the URL path."""
        return uuid.UUID(self.kwargs.get("pk"))

    # pylint: disable=unused-argument
    def retrieve(self, request, pk=None):
        """
        Implementation of the Wopi CheckFileInfo file operation
        https://learn.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/rest/files/checkfileinfo
        """
        item = request.auth.item
        abilities = item.get_abilities(request.user)

        head_object = get_item_file_head_object(item)
        wopi_client = get_wopi_client_config(item, request.user)
        client_options = {}
        if wopi_client:
            client_name = wopi_client.get("client", "")
            client_config = settings.WOPI_CLIENTS_CONFIGURATION.get(client_name, {})
            client_options = client_config.get("options", {})

        properties = build_wopi_check_file_info_base(
            base_file_name=item.filename,
            owner_id=str(item.creator.id),
            user=request.user,
            size=int(head_object["ContentLength"]),
            version=str(head_object.get("VersionId", "")),
        )
        properties.update(
            {
                "UserCanWrite": abilities["update"],
                "UserCanRename": abilities["update"],
                "ReadOnly": not abilities["update"],
                "SupportsRename": client_options.get("SupportsRename", True),
                "SupportsDeleteFile": True,
                "DownloadUrl": f"/media/{item.file_key}",
            }
        )

        return Response(properties, status=200)

    def _get_file_content(self, request, pk=None):
        """
        Implementation of the Wopi GetFile file operation
        https://learn.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/rest/files/getfile
        """
        item = request.auth.item

        head_object = get_item_file_head_object(item)
        preflight_response = get_wopi_max_expected_size_preflight_response(
            actual_size=int(head_object["ContentLength"]),
            max_expected_size=request.META.get("HTTP_X_WOPI_MAXEXPECTEDSIZE"),
        )
        if preflight_response is not None:
            return preflight_response

        s3_client = default_storage.connection.meta.client

        file = s3_client.get_object(
            Bucket=default_storage.bucket_name,
            Key=item.file_key,
        )

        return build_wopi_get_file_streaming_response(
            streaming_content=file["Body"].iter_chunks(),
            content_type=item.mimetype,
            version=str(head_object["VersionId"]),
            size=int(head_object["ContentLength"]),
        )

    def _put_file_content(  # noqa: PLR0911,PLR0912,PLR0915
        self, request, pk=None
    ):  # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches,too-many-statements
        """
        Implementation of the Wopi PutFile file operation
        https://learn.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/rest/files/putfile
        """
        started_at = time.monotonic()
        preflight_response = get_wopi_put_override_preflight_response(
            override=request.META.get(HTTP_X_WOPI_OVERRIDE)
        )
        if preflight_response is not None:
            return preflight_response

        item = request.auth.item
        abilities = item.get_abilities(request.user)

        if not abilities["update"]:
            return Response(status=401)

        request_lock_value = (request.META.get(HTTP_X_WOPI_LOCK) or "").strip()

        body_size = int(request.META.get("CONTENT_LENGTH") or 0)

        lock_service = LockService(item)
        current_lock_value = lock_service.get_lock(default="")

        # Size check is required by ONLYOFFICE for unlocked PutFile:
        # - if current size is 0 => accept PutFile
        # - if current size is != 0 or missing => 409 Conflict
        s3_client = default_storage.connection.meta.client
        size_missing = False
        current_size = None
        current_version_id = None
        try:
            head_object = s3_client.head_object(
                Bucket=default_storage.bucket_name, Key=item.file_key
            )
            current_size = int(head_object.get("ContentLength") or 0)
            current_version_id = head_object.get("VersionId")
        except botocore.exceptions.ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code") or "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                size_missing = True
            else:
                raise

        # Lock mismatch => 409 + X-WOPI-Lock=current lock value (or "" if unlocked)
        if current_lock_value:
            if request_lock_value != current_lock_value:
                return Response(status=409, headers={X_WOPI_LOCK: current_lock_value})
        else:
            # File is currently unlocked.
            if request_lock_value:
                return Response(status=409, headers={X_WOPI_LOCK: ""})

            # Unlocked PutFile must follow ONLYOFFICE editnew semantics:
            # accept only if the current file is a 0-byte placeholder.
            if size_missing:
                # SeaweedFS S3 can be briefly inconsistent right after file creation.
                # If the DB says this item is still a 0-byte placeholder, accept unlocked
                # PutFile requests (ONLYOFFICE editnew semantics) even if the object is missing.
                #
                # However, we must not accept non-empty unlocked PutFile requests when the object
                # is missing: this should remain a 409 Conflict.
                if (item.size or 0) == 0:
                    current_size = 0
                else:
                    return Response(status=409, headers={X_WOPI_LOCK: ""})

            if int(current_size or 0) != 0:
                return Response(status=409, headers={X_WOPI_LOCK: ""})

        # SeaweedFS S3 exhibits ~60s latency when overwriting an existing 0-byte object.
        # To avoid surprising behavior on non-new files, apply the delete+put
        # workaround strictly to the editnew placeholder case (size==0 + CREATING).
        delete_placeholder = (
            not size_missing
            and int(current_size or 0) == 0
            and item.upload_state == ItemUploadStateChoices.CREATING
        )
        if delete_placeholder:
            try:
                delete_kwargs = {
                    "Bucket": default_storage.bucket_name,
                    "Key": item.file_key,
                }
                # When versioning is enabled, delete the exact 0-byte placeholder version
                # to avoid leaving an empty version around and to make subsequent PUT fast.
                if current_version_id:
                    delete_kwargs["VersionId"] = current_version_id

                s3_client.delete_object(**delete_kwargs)
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                logger.warning(
                    "wopi_putfile: placeholder delete failed (item_id=%s exc_class=%s)",
                    item.id,
                    exc.__class__.__name__,
                )

        put_at = time.monotonic()
        try:
            version_id, saved_size = stream_to_s3_object(
                s3_client=s3_client,
                bucket=default_storage.bucket_name,
                key=item.file_key,
                body_stream=request.stream,
                content_type=str(
                    request.content_type or item.mimetype or "application/octet-stream"
                ),
            )
        except RequestDataTooBig:
            return Response(status=413)
        save_ms = int((time.monotonic() - put_at) * 1000)
        update_fields = ["size", "updated_at"]
        if item.upload_state == ItemUploadStateChoices.CREATING:
            item.upload_state = ItemUploadStateChoices.READY
            update_fields.append("upload_state")

        head_ms = 0
        item.size = int(saved_size or 0)
        item.save(update_fields=update_fields)

        total_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            "wopi_putfile: ok (item_id=%s locked=%s unlocked_size=%s "
            "body_size=%s delete_placeholder=%s ms_total=%s ms_save=%s ms_head=%s)",
            item.id,
            bool(current_lock_value),
            "missing" if size_missing else str(int(current_size or 0)),
            body_size,
            delete_placeholder,
            total_ms,
            save_ms,
            head_ms,
        )
        return build_wopi_put_file_success_response(version=str(version_id or ""))

    def _detail_post_preflight(self, request, pk=None) -> Response | None:
        """Item detail POST actions require update permission."""

        _ = pk
        item = request.auth.item
        abilities = item.get_abilities(request.user)
        if not abilities["update"]:
            return Response(status=401)
        return None

    def _lock_service_or_response(self, request, pk=None) -> object | Response:
        """Return the item-backed lock service for shared lock lifecycle actions."""

        _ = pk
        item = request.auth.item
        return LockService(item)

    def _rename_file(self, request, pk=None):
        """
        Rename the file
        """
        item = request.auth.item
        abilities = item.get_abilities(request.user)

        if not abilities["update"]:
            return Response(status=401)

        new_filename = request.META.get("HTTP_X_WOPI_REQUESTEDNAME")

        if not new_filename:
            return Response(
                status=400,
                headers={X_WOPI_INVALIDFILENAMERROR: "No filename provided"},
            )

        # Convert it to utf-7 to avoid issues with special characters
        new_filename = new_filename.encode("ascii").decode("utf-7")
        lock_service = LockService(item)
        if lock_service.is_locked():
            current_lock_value = lock_service.get_lock(default="")
            lock_value = request.META.get(HTTP_X_WOPI_LOCK)
            if current_lock_value != lock_value:
                return Response(status=409, headers={X_WOPI_LOCK: current_lock_value})

        _, current_extension = splitext(item.filename)
        new_filename_with_extension = f"{new_filename}{current_extension}"

        parent_path = item.path[:-1]
        # Filter on siblings with the desired filename
        queryset = (
            Item.objects.filter(path__descendants=".".join(parent_path))
            .filter(path__depth=item.depth)
            .filter(filename=new_filename_with_extension)
            .exclude(id=item.id)
        )

        if queryset.exists():
            return Response(
                status=400,
                headers={X_WOPI_INVALIDFILENAMERROR: "Filename already exists"},
            )
        head_object = get_item_file_head_object(item)

        file_key = item.file_key
        item.filename = new_filename_with_extension
        item.title = new_filename

        # ensure renaming the file in the database and on the storage are done atomically
        with transaction.atomic():
            item.save(update_fields=["filename", "title", "updated_at"])

            # Rename the file in the storage
            s3_client = default_storage.connection.meta.client
            # Don't catch any s3 error, if failing let the exception raises to sentry
            # the transaction will be rolled back
            s3_client.copy_object(
                Bucket=default_storage.bucket_name,
                CopySource={
                    "Bucket": default_storage.bucket_name,
                    "Key": file_key,
                },
                Key=item.file_key,
                MetadataDirective="COPY",
            )

        try:
            s3_client.delete_object(
                Bucket=default_storage.bucket_name,
                Key=file_key,
                VersionId=head_object["VersionId"],
            )
        # pylint: disable=broad-exception-caught
        except Exception as e:  # noqa
            capture_exception(e)
            logger.warning("Error deleting old file for item %s in the storage: %s", item.id, e)

        if "application/json" in request.META.get("HTTP_ACCEPT", ""):
            return Response(
                data={"Name": new_filename}, status=200, content_type="application/json"
            )

        return Response(status=200)


class MountWopiViewSet(WopiFileContentRuntimeMixin, WopiLockRuntimeMixin, viewsets.ViewSet):
    """
    WOPI ViewSet for mount-backed files.

    This endpoint family does not echo mount paths; operator-facing logs rely on
    safe correlation hashes.
    """

    authentication_classes = [WopiMountAccessTokenAuthentication]
    permission_classes = [MountAccessTokenPermission]
    parser_classes = []

    detail_post_actions = WOPI_SHARED_DETAIL_POST_ACTIONS

    def get_file_id(self):
        """Get the file id from the URL path."""
        return uuid.UUID(self.kwargs.get("pk"))

    def _mount_capabilities(self, mount: dict) -> dict[str, bool]:
        """Return normalized capability flags for the given mount."""
        params = mount.get("params") if isinstance(mount.get("params"), dict) else {}
        return normalize_mount_capabilities((params or {}).get("capabilities"))

    def _wopi_mount_or_none(self, mount_id: str) -> dict | None:
        """Return the enabled mount only when mount.wopi is true."""
        mount = resolve_enabled_mount(mount_id)
        if not mount:
            return None
        if not bool(self._mount_capabilities(mount).get("mount.wopi")):
            return None
        return mount

    def _resolve_wopi_target(self, *, mount_id: str, normalized_path: str):
        """Return the shared mount-backed WOPI target or `(None, status)`."""

        mount = self._wopi_mount_or_none(mount_id)
        if not mount:
            return None, 404

        try:
            return (
                resolve_mount_wopi_target(
                    mount=mount,
                    mount_id=mount_id,
                    normalized_path=normalized_path,
                ),
                200,
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
            return None, 404
        except MountProviderError as exc:
            logger.info(
                "mount_wopi_stat: failed "
                "(failure_class=%s next_action_hint=%s mount_id=%s path_hash=%s)",
                exc.failure_class,
                exc.next_action_hint,
                mount_id,
                safe_str_hash(normalized_path),
            )
            status_code = 404 if exc.public_code == "mount.path.not_found" else 500
            return None, status_code
        except MountEntryNotAFileError:
            return None, 404

    # pylint: disable=unused-argument
    def retrieve(self, request, pk=None):
        """WOPI CheckFileInfo operation for mount-backed files."""
        ctx = request.auth
        mount_id = str(getattr(ctx, "mount_id", "") or "").strip()
        normalized_path = str(getattr(ctx, "normalized_path", "") or "")

        target, status_code = self._resolve_wopi_target(
            mount_id=mount_id,
            normalized_path=normalized_path,
        )
        if not target:
            return Response(status=status_code)

        size = 0 if target.entry.size is None else int(target.entry.size)

        properties = build_wopi_check_file_info_base(
            base_file_name=str(target.entry.name or "file"),
            owner_id=mount_id,
            user=request.user,
            size=size,
            version=target.version,
        )
        properties.update(
            {
                "UserCanWrite": True,
                "UserCanRename": False,
                "ReadOnly": False,
                "SupportsRename": False,
                "SupportsDeleteFile": False,
            }
        )

        return Response(properties, status=200)

    def _get_file_content(self, request, pk=None):
        """WOPI GetFile operation for mount-backed files (streaming)."""
        ctx = request.auth
        mount_id = str(getattr(ctx, "mount_id", "") or "").strip()
        normalized_path = str(getattr(ctx, "normalized_path", "") or "")

        target, status_code = self._resolve_wopi_target(
            mount_id=mount_id,
            normalized_path=normalized_path,
        )
        if not target:
            return Response(status=status_code)

        preflight_response = get_wopi_max_expected_size_preflight_response(
            actual_size=None if target.entry.size is None else int(target.entry.size),
            max_expected_size=request.META.get("HTTP_X_WOPI_MAXEXPECTEDSIZE"),
        )
        if preflight_response is not None:
            return preflight_response

        chunk_size = 64 * 1024

        def _stream():
            try:
                with target.provider.open_read(
                    mount=target.mount,
                    normalized_path=normalized_path,
                ) as f:
                    while True:
                        data = f.read(chunk_size)
                        if not data:
                            break
                        yield data
            except MountProviderError as exc:
                logger.info(
                    "mount_wopi_get_file: failed "
                    "(failure_class=%s next_action_hint=%s mount_id=%s path_hash=%s)",
                    exc.failure_class,
                    exc.next_action_hint,
                    mount_id,
                    safe_str_hash(normalized_path),
                )
                return
            except (OSError, ValueError):
                return

        return build_wopi_get_file_streaming_response(
            streaming_content=_stream(),
            content_type="application/octet-stream",
            version=target.version,
            size=None if target.entry.size is None else int(target.entry.size),
        )

    def _write_and_compute_version(
        self,
        *,
        target,
        request,
    ) -> tuple[int, str | None, int]:
        """Stream request bytes to the provider and return (status, version, bytes)."""
        ctx = request.auth
        mount_id = str(getattr(ctx, "mount_id", "") or "").strip()
        normalized_path = str(getattr(ctx, "normalized_path", "") or "")
        bytes_written = 0

        try:
            chunk_size = 64 * 1024
            stream = getattr(request, "_request", request)
            with target.provider.open_write(
                mount=target.mount,
                normalized_path=normalized_path,
            ) as f:
                while True:
                    chunk = stream.read(chunk_size)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    f.write(chunk)
            refreshed_target, status_code = self._resolve_wopi_target(
                mount_id=mount_id,
                normalized_path=normalized_path,
            )
            if not refreshed_target:
                return status_code, None, bytes_written
            return 200, refreshed_target.version, bytes_written
        except RequestDataTooBig:
            return 413, None, 0
        except MountProviderError as exc:
            logger.info(
                "mount_wopi_put_file: failed "
                "(failure_class=%s next_action_hint=%s mount_id=%s path_hash=%s)",
                exc.failure_class,
                exc.next_action_hint,
                mount_id,
                safe_str_hash(normalized_path),
            )
            return 500, None, bytes_written
        except (OSError, ValueError) as exc:
            logger.info(
                "mount_wopi_put_file: failed "
                "(failure_class=mount.wopi.save_failed "
                "next_action_hint=Verify mount provider connectivity and retry "
                "mount_id=%s path_hash=%s)",
                mount_id,
                safe_str_hash(normalized_path),
            )
            capture_exception(exc)
            return 500, None, bytes_written

    def _put_file_content(self, request, pk=None):
        """WOPI PutFile operation for mount-backed files (streaming)."""
        preflight_response = get_wopi_put_override_preflight_response(
            override=request.META.get(HTTP_X_WOPI_OVERRIDE)
        )
        if preflight_response is not None:
            return preflight_response

        ctx = request.auth
        mount_id = str(getattr(ctx, "mount_id", "") or "").strip()
        normalized_path = str(getattr(ctx, "normalized_path", "") or "")

        target, status_code = self._resolve_wopi_target(
            mount_id=mount_id,
            normalized_path=normalized_path,
        )
        if not target:
            return Response(status=status_code)

        lock_service = MountLockService(mount_id=mount_id, normalized_path=normalized_path)
        lock_value = request.META.get(HTTP_X_WOPI_LOCK)

        if lock_value:
            current_lock_value = lock_service.get_lock(default="")
            if current_lock_value != lock_value:
                return self._lock_conflict_response(current_lock_value=current_lock_value)
        else:
            body_size = int(request.META.get("CONTENT_LENGTH") or 0)
            if body_size > 0:
                return self._lock_conflict_response(current_lock_value="")

        status_code, version, bytes_written = self._write_and_compute_version(
            target=target, request=request
        )
        if status_code != 200 or not version:
            return Response(status=status_code)

        logger.info(
            "mount_wopi_put_file: ok (mount_id=%s path_hash=%s size=%sB)",
            mount_id,
            safe_str_hash(normalized_path),
            bytes_written,
        )
        return build_wopi_put_file_success_response(version=version)

    def _lock_service_or_response(self, request, pk=None) -> object | Response:
        """Return the mount-backed lock service for shared lock lifecycle actions."""

        _ = pk
        ctx = request.auth
        mount_id = str(getattr(ctx, "mount_id", "") or "").strip()
        normalized_path = str(getattr(ctx, "normalized_path", "") or "")
        if not self._wopi_mount_or_none(mount_id):
            return Response(status=404)
        return MountLockService(mount_id=mount_id, normalized_path=normalized_path)
