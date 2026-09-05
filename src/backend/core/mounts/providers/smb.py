"""SMB MountProvider (v1: stat + list_children)."""

from __future__ import annotations

import dataclasses
import errno
import posixpath
import stat as statlib
import threading
from contextlib import ExitStack, contextmanager, suppress
from datetime import datetime, timezone
from typing import Any

import smbclient
from smbprotocol.exceptions import (
    AccessDenied,
    BadNetworkName,
    LogonFailure,
    NoSuchFile,
    ObjectNameNotFound,
    ObjectPathNotFound,
    PasswordExpired,
    SharingViolation,
    SMBAuthenticationError,
    SMBConnectionClosed,
    SMBOSError,
    WrongPassword,
)
from smbprotocol.open import CreateOptions, FileAttributes

from core.mounts.paths import MountPathNormalizationError, normalize_mount_path
from core.mounts.providers.base import (
    MountBrowserStreamCapabilities,
    MountEntry,
    MountProviderError,
)
from core.services.secret_resolver import get_mount_secret_resolver
from core.utils.secret_resolver import SecretResolutionError


@dataclasses.dataclass(frozen=True, slots=True)
class _SmbConfig:
    server: str
    share: str
    username: str
    port: int
    domain: str | None
    base_path: str
    connect_timeout_seconds: int

    @property
    def auth_username(self) -> str:
        """Return the SMB auth username (domain\\username when domain is set)."""

        if not self.domain:
            return self.username
        return f"{self.domain}\\{self.username}"


_SESSION_LOCK = threading.Lock()
_SESSIONS: dict[str | tuple, "_SessionPool"] = {}
_PUBLIC_LOCATION_NOT_FOUND = ("Mount location not found.", "mount.provider.location_not_found")
_PUBLIC_AUTH_FAILED = ("Mount authentication failed.", "mount.provider.auth_failed")
_PUBLIC_UNREACHABLE = ("Mount is unreachable.", "mount.provider.unreachable")
_PUBLIC_OPERATION_FAILED = ("Mount operation failed.", "mount.operation.failed")


def _config_error(*, failure_class: str, next_action_hint: str) -> MountProviderError:
    return MountProviderError(
        failure_class=failure_class,
        next_action_hint=next_action_hint,
        public_message="Mount provider configuration is invalid.",
        public_code="mount.provider.invalid_config",
    )


# pylint: disable-next=too-many-branches
def _load_config(  # noqa: PLR0912
    mount: dict[str, Any],
) -> tuple[_SmbConfig, str | None, str | None]:
    # pylint: disable=too-many-branches
    params = mount.get("params") if isinstance(mount.get("params"), dict) else {}

    server = str(params.get("server") or "").strip()
    share = str(params.get("share") or "").strip()
    username = str(params.get("username") or "").strip()
    if not server:
        raise _config_error(
            failure_class="mount.smb.config.server_missing",
            next_action_hint="Set mounts[*].params.server for SMB mounts.",
        )
    if not share:
        raise _config_error(
            failure_class="mount.smb.config.share_missing",
            next_action_hint="Set mounts[*].params.share for SMB mounts.",
        )
    if not username:
        raise _config_error(
            failure_class="mount.smb.config.username_missing",
            next_action_hint="Set mounts[*].params.username for SMB mounts.",
        )

    port_raw = params.get("port", 445)
    port = port_raw if isinstance(port_raw, int) else None
    if port is None or port < 1 or port > 65535:
        raise _config_error(
            failure_class="mount.smb.config.port_invalid",
            next_action_hint="Set mounts[*].params.port to an integer between 1 and 65535.",
        )

    domain_raw = params.get("domain")
    if domain_raw is None:
        domain_raw = params.get("workgroup")
    domain = str(domain_raw).strip() if isinstance(domain_raw, str) else None
    if domain == "":
        domain = None

    base_path_raw = params.get("base_path", "/")
    if not isinstance(base_path_raw, str):
        raise _config_error(
            failure_class="mount.smb.config.base_path_invalid",
            next_action_hint=(
                "Set mounts[*].params.base_path to a mount path string like '/subdir'."
            ),
        )
    try:
        base_path = normalize_mount_path(base_path_raw)
    except MountPathNormalizationError as exc:
        raise _config_error(
            failure_class="mount.smb.config.base_path_invalid",
            next_action_hint="Set mounts[*].params.base_path to a valid mount path without '..'.",
        ) from exc

    connect_timeout_seconds_raw = params.get("connect_timeout_seconds", 60)
    connect_timeout_seconds = (
        connect_timeout_seconds_raw if isinstance(connect_timeout_seconds_raw, int) else None
    )
    if connect_timeout_seconds is None or connect_timeout_seconds < 1:
        raise _config_error(
            failure_class="mount.smb.config.timeout_invalid",
            next_action_hint="Set mounts[*].params.connect_timeout_seconds to an integer >= 1.",
        )

    if isinstance(mount.get("password"), str) and str(mount.get("password")).strip():
        raise _config_error(
            failure_class="mount.smb.config.password_forbidden",
            next_action_hint=(
                "Do not set mount passwords directly; use password_secret_ref and/or "
                "password_secret_path."
            ),
        )
    if isinstance(params.get("password"), str) and str(params.get("password")).strip():
        raise _config_error(
            failure_class="mount.smb.config.password_forbidden",
            next_action_hint=(
                "Do not set mount passwords directly; use password_secret_ref and/or "
                "password_secret_path."
            ),
        )

    secret_ref = mount.get("password_secret_ref") or params.get("password_secret_ref")
    secret_path = mount.get("password_secret_path") or params.get("password_secret_path")
    secret_ref = str(secret_ref).strip() if isinstance(secret_ref, str) else None
    secret_path = str(secret_path).strip() if isinstance(secret_path, str) else None
    if secret_ref == "":
        secret_ref = None
    if secret_path == "":
        secret_path = None

    config = _SmbConfig(
        server=server,
        share=share,
        username=username,
        port=port,
        domain=domain,
        base_path=base_path,
        connect_timeout_seconds=connect_timeout_seconds,
    )
    return config, secret_path, secret_ref


@dataclasses.dataclass
class _SessionGeneration:
    """One credential generation; keep its connections until readers finish."""

    version: tuple
    options: dict[str, Any] = dataclasses.field(repr=False)
    borrowers: int = 0


class _SessionPool:
    """Isolate SMB caches and retire rotated sessions without closing live files."""

    def __init__(self):
        self.lock = threading.Lock()
        self.current: _SessionGeneration | None = None

    @staticmethod
    def close(generation):
        """Dispose only this backend's retired connections."""
        smbclient.reset_connection_cache(
            connection_cache=generation.options["connection_cache"], fail_on_error=False
        )

    @contextmanager
    def borrow(self, config, secret_path, secret_ref):
        """Bind every operation to explicit credentials and a private cache."""
        retired = None
        with self.lock:
            resolved = get_mount_secret_resolver().resolve(
                secret_path=secret_path, secret_ref=secret_ref
            )
            version = (config, secret_path, secret_ref, resolved.version_sha256_16)
            if self.current is None or self.current.version != version:
                options = {
                    "username": config.auth_username,
                    "port": config.port,
                    "connection_timeout": config.connect_timeout_seconds,
                    "connection_cache": {},
                }
                try:
                    smbclient.register_session(config.server, password=resolved.value, **options)
                except Exception:  # noqa: BLE001
                    smbclient.reset_connection_cache(
                        connection_cache=options["connection_cache"], fail_on_error=False
                    )
                    raise MountProviderError(
                        failure_class="mount.session.init_failed",
                        next_action_hint="Verify backend credentials and connectivity, then retry.",
                        public_message="Connection/session initialization failed.",
                        public_code="mount.session.init_failed",
                    ) from None
                retired = self.current
                self.current = _SessionGeneration(version, options)
            generation = self.current
            generation.borrowers += 1
            close_retired = retired is not None and retired.borrowers == 0
        if close_retired:
            self.close(retired)
        # Password is held for this operation only, including transparent reconnects.
        options = {**generation.options, "password": resolved.value}
        try:
            yield options
        finally:
            with self.lock:
                generation.borrowers -= 1
                close_generation = generation is not self.current and generation.borrowers == 0
            if close_generation:
                self.close(generation)


@contextmanager
def _connection(mount):
    """Resolve current configuration and lend a credential-bound connection."""
    config, secret_path, secret_ref = _load_config(mount)
    key = mount.get("mount_id") or (config, secret_path, secret_ref)
    with _SESSION_LOCK:
        pool = _SESSIONS.setdefault(key, _SessionPool())
    try:
        with pool.borrow(config, secret_path, secret_ref) as options:
            yield config, options
    except SecretResolutionError as exc:
        raise MountProviderError(
            failure_class=exc.failure_class,
            next_action_hint=exc.next_action_hint,
            public_message=exc.public_message,
            public_code=exc.public_code,
        ) from None


def _combined_path(*, base_path: str, normalized_path: str) -> str:
    base = normalize_mount_path(base_path)
    target = normalize_mount_path(normalized_path)
    if base == "/":
        return target
    if target == "/":
        return base
    return normalize_mount_path(base.rstrip("/") + target)


def _unc_path(*, config: _SmbConfig, normalized_path: str) -> str:
    combined = _combined_path(base_path=config.base_path, normalized_path=normalized_path)
    rel = combined.lstrip("/")
    rel_win = rel.replace("/", "\\")
    base = f"\\\\{config.server}\\{config.share}"
    return f"{base}\\{rel_win}" if rel_win else base


def _map_exc(*, exc: Exception, op: str) -> MountProviderError:
    failure_class: str
    next_action_hint: str
    public_message: str
    public_code: str

    if isinstance(exc, BadNetworkName):
        failure_class = "mount.smb.env.share_not_found"
        next_action_hint = "Verify the SMB server/share name and retry the operation."
        public_message, public_code = _PUBLIC_LOCATION_NOT_FOUND
    elif isinstance(
        exc,
        (
            SMBAuthenticationError,
            LogonFailure,
            WrongPassword,
            PasswordExpired,
            AccessDenied,
        ),
    ):
        failure_class = "mount.smb.env.auth_failed"
        next_action_hint = "Verify SMB credentials (refs-only secrets) and retry the operation."
        public_message, public_code = _PUBLIC_AUTH_FAILED
    elif isinstance(exc, (SMBConnectionClosed, TimeoutError)) or (
        isinstance(exc, OSError)
        and getattr(exc, "errno", None)
        in {errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH, errno.ETIMEDOUT}
    ):
        failure_class = "mount.smb.env.unreachable"
        next_action_hint = "Verify the SMB server is reachable from the backend and retry."
        public_message, public_code = _PUBLIC_UNREACHABLE
    elif isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.ENOTEMPTY:
        failure_class = "mount.path.not_empty"
        next_action_hint = "Empty the folder before retrying the delete."
        public_message = "Mount path is not empty."
        public_code = "mount.path.not_empty"
    elif isinstance(
        exc,
        (
            SMBOSError,
            FileNotFoundError,
            NoSuchFile,
            ObjectNameNotFound,
            ObjectPathNotFound,
        ),
    ) or (isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.ENOENT):
        failure_class = "mount.path.not_found"
        next_action_hint = "Verify the path exists in the mount and retry."
        public_message = "Mount path not found."
        public_code = "mount.path.not_found"
    elif isinstance(exc, SharingViolation):
        failure_class = "mount.path.busy"
        next_action_hint = "Retry the operation after the current file access is released."
        public_message = "Mount file is busy."
        public_code = "mount.path.busy"
    elif isinstance(exc, FileExistsError) or (
        isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.EEXIST
    ):
        failure_class = "mount.path.already_exists"
        next_action_hint = "Choose a different target name/path and retry."
        public_message = "Mount path already exists."
        public_code = "mount.path.already_exists"
    else:
        mapping = {
            "stat": (
                "mount.smb.stat_failed",
                "Verify SMB mount configuration and connectivity, then retry the stat operation.",
            ),
            "list": (
                "mount.smb.list_failed",
                "Verify SMB mount configuration and connectivity, then retry the list operation.",
            ),
            "read": (
                "mount.smb.read_failed",
                "Verify SMB mount configuration and connectivity, then retry the read operation.",
            ),
            "write": (
                "mount.smb.write_failed",
                "Verify SMB mount configuration and connectivity, then retry the upload.",
            ),
            "mkdir": (
                "mount.smb.mkdir_failed",
                "Verify SMB mount configuration and connectivity, then retry folder creation.",
            ),
            "rename": (
                "mount.smb.rename_failed",
                "Verify SMB mount configuration and connectivity, then retry finalize.",
            ),
            "remove": (
                "mount.smb.remove_failed",
                "Verify SMB mount configuration and connectivity, then retry cleanup.",
            ),
        }
        failure_class, next_action_hint = mapping.get(
            op,
            (
                "mount.smb.operation_failed",
                "Verify SMB mount configuration and connectivity, then retry the operation.",
            ),
        )
        public_message, public_code = _PUBLIC_OPERATION_FAILED
    return MountProviderError(
        failure_class=failure_class,
        next_action_hint=next_action_hint,
        public_message=public_message,
        public_code=public_code,
    )


def stat(*, mount: dict, normalized_path: str) -> MountEntry:
    """Return metadata for a target path."""
    with _connection(mount) as (config, options):
        unc = _unc_path(config=config, normalized_path=normalized_path)
        try:
            st = smbclient.stat(
                unc, follow_symlinks=not mount.get("_deny_reparse", False), **options
            )
            if mount.get("_deny_reparse"):
                _reject_reparse(getattr(st, "st_file_attributes", 0))
        except Exception as exc:  # noqa: BLE001
            raise _map_exc(exc=exc, op="stat") from None

        is_dir = statlib.S_ISDIR(getattr(st, "st_mode", 0))
        entry_type = "folder" if is_dir else "file"
        name = (
            "/"
            if normalize_mount_path(normalized_path) == "/"
            else normalized_path.strip("/").split("/")[-1]
        )

        modified_at = None
        if getattr(st, "st_mtime", None) is not None:
            modified_at = datetime.fromtimestamp(float(st.st_mtime), tz=timezone.utc)

        size = None if is_dir else int(getattr(st, "st_size", 0) or 0)

        return MountEntry(
            entry_type=entry_type,
            normalized_path=normalize_mount_path(normalized_path),
            name=str(name),
            size=size,
            modified_at=modified_at,
            object_identity=f"{st.st_dev}:{st.st_ino}" if getattr(st, "st_ino", 0) else None,
        )


def list_children(*, mount: dict, normalized_path: str) -> list[MountEntry]:
    """List immediate child entries under a folder path."""
    with _connection(mount) as (config, options):
        parent = stat(mount=mount, normalized_path=normalized_path)
        if parent.entry_type != "folder":
            return []

        unc = _unc_path(config=config, normalized_path=normalized_path)
        try:
            raw_children = list(smbclient.scandir(unc, **options))
        except Exception as exc:  # noqa: BLE001
            raise _map_exc(exc=exc, op="list") from None

        children: list[MountEntry] = []
        for child in raw_children:
            name = str(getattr(child, "name", "") or "").strip()
            if not name:
                continue

            try:
                child_path = normalize_mount_path(
                    posixpath.join(normalize_mount_path(normalized_path), name)
                )
            except MountPathNormalizationError:
                continue

            try:
                st = (
                    child.stat(follow_symlinks=False)
                    if mount.get("_deny_reparse")
                    else child.stat()
                )
                if mount.get("_deny_reparse") and (
                    getattr(st, "st_file_attributes", 0)
                    & FileAttributes.FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    continue
            except Exception as exc:  # noqa: BLE001
                raise _map_exc(exc=exc, op="list") from None

            is_dir = statlib.S_ISDIR(getattr(st, "st_mode", 0))
            entry_type = "folder" if is_dir else "file"

            modified_at = None
            if getattr(st, "st_mtime", None) is not None:
                modified_at = datetime.fromtimestamp(float(st.st_mtime), tz=timezone.utc)

            size = None if is_dir else int(getattr(st, "st_size", 0) or 0)
            children.append(
                MountEntry(
                    entry_type=entry_type,
                    normalized_path=child_path,
                    name=name,
                    size=size,
                    modified_at=modified_at,
                    object_identity=f"{st.st_dev}:{st.st_ino}"
                    if getattr(st, "st_ino", 0)
                    else None,
                )
            )

        return sorted(
            children,
            key=lambda e: (
                0 if e.entry_type == "folder" else 1,
                str(e.name).casefold(),
                e.normalized_path,
            ),
        )


def supports_range_reads(*, _mount: dict) -> bool:
    """Return whether this provider supports range reads (v2: download)."""

    return True


def get_browser_stream_capabilities(*, mount: dict) -> MountBrowserStreamCapabilities:
    """Expose browser-stream capabilities for the SMB provider."""

    _ = mount
    return MountBrowserStreamCapabilities(
        browser_stream_mode="proxy",
        supports_random_access=True,
        supports_head_metadata=True,
        supports_stable_version=True,
    )


@contextmanager
def open_read(*, mount: dict, normalized_path: str):
    """
    Open a mount file for streaming reads.

    The returned file handle is suitable for `seek()` + chunked reads.
    """

    with _connection(mount) as (config, options):
        unc = _unc_path(config=config, normalized_path=normalized_path)
        try:
            # Text preview can issue multiple concurrent reads on the same path
            # (preview-info + text fetch). SMB defaults to exclusive handles, so
            # we must allow shared readers for stable mount-backed previews.
            if mount.get("_deny_reparse"):
                options["create_options"] = CreateOptions.FILE_OPEN_REPARSE_POINT
                options["buffering"] = 0
            f = smbclient.open_file(unc, mode="rb", share_access="r", **options)
            if mount.get("_deny_reparse"):
                try:
                    _reject_reparse(f.fd.file_attributes)
                except MountProviderError:
                    f.close()
                    raise
        except Exception as exc:  # noqa: BLE001
            raise _map_exc(exc=exc, op="read") from None

        try:
            yield f
        finally:
            with suppress(Exception):
                f.close()


@contextmanager
def open_write(*, mount: dict, normalized_path: str):
    """
    Open a mount file for streaming writes.

    The returned file handle is suitable for chunked writes.
    """

    with _connection(mount) as (config, options):
        unc = _unc_path(config=config, normalized_path=normalized_path)
        try:
            # Governed writes create private staging objects; never truncate a
            # name another NAS client could have substituted before this open.
            mode = "xb" if mount.get("_deny_reparse") else "wb"
            f = smbclient.open_file(unc, mode=mode, **options)
        except Exception as exc:  # noqa: BLE001
            raise _map_exc(exc=exc, op="write") from None

        try:
            yield f
        finally:
            f.close()


def mkdirs(*, mount: dict, normalized_path: str) -> None:
    """Create a folder path (and parents) on the SMB mount (best-effort)."""

    with _connection(mount) as (config, options):
        unc = _unc_path(config=config, normalized_path=normalized_path)
        try:
            smbclient.makedirs(unc, exist_ok=True, **options)
        except Exception as exc:  # noqa: BLE001
            raise _map_exc(exc=exc, op="mkdir") from None


def rename(*, mount: dict, src_normalized_path: str, dst_normalized_path: str) -> None:
    """Best-effort rename for deterministic finalize semantics."""

    with _connection(mount) as (config, options):
        src_unc = _unc_path(config=config, normalized_path=src_normalized_path)
        dst_unc = _unc_path(config=config, normalized_path=dst_normalized_path)
        try:
            smbclient.rename(src_unc, dst_unc, **options)
        except Exception as exc:  # noqa: BLE001
            raise _map_exc(exc=exc, op="rename") from None


rename_no_replace = rename


def replace(*, mount: dict, src_normalized_path: str, dst_normalized_path: str) -> None:
    """Atomically finalize a staged replacement using SMB's replace operation."""
    with _connection(mount) as (config, options):
        try:
            smbclient.replace(
                _unc_path(config=config, normalized_path=src_normalized_path),
                _unc_path(config=config, normalized_path=dst_normalized_path),
                **options,
            )
        except Exception as exc:  # noqa: BLE001
            raise _map_exc(exc=exc, op="replace") from None


def remove(*, mount: dict, normalized_path: str) -> None:
    """Remove a file or an empty folder at the given mount path."""

    with _connection(mount) as (config, options):
        unc = _unc_path(config=config, normalized_path=normalized_path)
        try:
            st = smbclient.stat(
                unc, follow_symlinks=not mount.get("_deny_reparse", False), **options
            )
            if statlib.S_ISDIR(getattr(st, "st_mode", 0)):
                smbclient.rmdir(unc, **options)
            else:
                smbclient.remove(unc, **options)
        except Exception as exc:  # noqa: BLE001
            raise _map_exc(exc=exc, op="remove") from None


def _reject_reparse(attributes):
    if attributes & FileAttributes.FILE_ATTRIBUTE_REPARSE_POINT:
        raise MountProviderError(
            failure_class="mount.access.denied",
            next_action_hint="Use a regular file or folder.",
            public_message="Storage path is not accessible.",
            public_code="mount.access.denied",
        )


@contextmanager
def confine(*, mount: dict, normalized_path: str):
    """Pin ancestor directories against replacement while a virtual IO runs."""
    with _connection(mount) as (config, options), ExitStack() as handles:
        root_config = dataclasses.replace(config, base_path="")
        parent = posixpath.dirname(normalize_mount_path(normalized_path))
        full_parent = normalize_mount_path(posixpath.join(config.base_path, parent.lstrip("/")))
        prefixes = ["/"]
        for part in full_parent.strip("/").split("/") if full_parent != "/" else []:
            prefixes.append(posixpath.join(prefixes[-1], part))
        try:
            for prefix in prefixes:
                directory = handles.enter_context(
                    smbclient.open_file(
                        _unc_path(config=root_config, normalized_path=prefix),
                        mode="rb",
                        file_type="dir",
                        buffering=0,
                        share_access="r",
                        create_options=CreateOptions.FILE_OPEN_REPARSE_POINT,
                        **options,
                    )
                )
                _reject_reparse(directory.fd.file_attributes)
        except MountProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _map_exc(exc=exc, op="access") from None
        yield


# Provider capability uses the common signature, independent of configuration.
# pylint: disable-next=unused-argument
def supports_virtual_roots(*, mount: dict) -> bool:
    """Virtual callers use pinned ancestors and refuse reparse points."""
    return True


def capacity(*, mount: dict) -> dict:
    """Read caller-visible volume availability without changing native NAS quotas."""
    with _connection(mount) as (config, options):
        try:
            volume = smbclient.stat_volume(_unc_path(config=config, normalized_path="/"), **options)
        except Exception as exc:  # noqa: BLE001
            raise _map_exc(exc=exc, op="capacity") from None
        return {
            "total_bytes": volume.total_size,
            "caller_available_bytes": volume.caller_available_size,
            "actual_available_bytes": volume.actual_available_size,
        }
