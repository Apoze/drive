"""Resolve virtual roots and file permissions without exposing NAS credentials."""

import posixpath
from uuid import UUID

from django.conf import settings
from django.db.models import Q

from core.models import StorageBackend, StorageSpace, User
from core.mounts.paths import normalize_mount_path
from core.mounts.providers.base import MountProviderError


def within(path, root):
    """Component-aware containment; /alice-2 is not inside /alice."""
    return path == root or path.startswith(root.rstrip("/") + "/")


def namespace_path(backend, path):
    """Canonicalize connection-relative paths, including a view of a namespace subroot."""
    return posixpath.normpath(posixpath.join(backend.namespace_root, path.lstrip("/")))


def denied():
    """Keep resource existence and native paths out of authorization failures."""
    return MountProviderError(
        failure_class="mount.access.denied",
        next_action_hint="Request access to this storage space.",
        public_message="Storage path is not accessible.",
        public_code="mount.access.denied",
    )


def native_connection(backend):
    """Reuse the configured provider and secret references for this connection."""
    if backend.family != "mount":
        raise denied()
    if backend.managed:
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_connections import validate_configuration  # noqa: PLC0415

        validate_configuration(backend, check_network=True)
        params = dict(backend.configuration["params"])
        if "server" in params:
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_network import validate_destination  # noqa: PLC0415

            params["server"] = validate_destination(params["server"], params.get("port", 445))[0]
        return {
            "mount_id": str(backend.pk),
            "display_name": backend.name,
            "provider": backend.configuration["provider"],
            "enabled": backend.enabled,
            "params": {
                **params,
                "capabilities": {"mount.share_link": True, **params.get("capabilities", {})},
                "password_secret_ref": f"storage:{backend.pk}",
            },
        }
    for mount in getattr(settings, "MOUNTS_REGISTRY", []):
        if mount.get("mount_id") == backend.registry_id and mount.get("enabled", True):
            return {**mount, "mount_id": str(backend.pk)}
    raise denied()


def _grants(space, user):
    if not user or not user.is_authenticated or not user.is_active:
        return []
    identity = (user.pk, tuple(user.teams))
    if getattr(space, "_grant_user_id", None) != identity:
        # pylint: disable-next=protected-access
        space._grant_user_id = identity  # noqa: SLF001
        # pylint: disable-next=protected-access
        space._resolved_grants = list(  # noqa: SLF001
            space.grants.filter(Q(user=user) | Q(team__in=user.teams))
        )
    # pylint: disable-next=protected-access
    return space._resolved_grants  # noqa: SLF001


def resolve_space_mount(mount_id, user):
    """Return an authorized virtual mount, or None without leaking its existence."""
    try:
        space_id = UUID(str(mount_id))
    except (TypeError, ValueError, AttributeError):
        return None
    if not user or not user.is_authenticated or not user.is_active:
        return None
    space = (
        StorageSpace.objects.select_related("backend")
        .filter(pk=space_id, enabled=True, backend__enabled=True, backend__family="mount")
        .first()
    )
    if not space:
        return None
    grants = list(_grants(space, user))
    owner = not space.explicit_access and space.owner_id == user.pk
    if not owner and not grants:
        return None
    try:
        native = native_connection(space.backend)
    except MountProviderError:
        return None
    capabilities = dict((native.get("params") or {}).get("capabilities") or {})
    writable = not space.backend.maintenance and (owner or any(grant.writable for grant in grants))
    shareable = space.allow_sharing and (owner or any(grant.shareable for grant in grants))
    if not writable:
        for action in ("create_folder", "move", "rename", "delete", "upload", "duplicate"):
            capabilities[f"mount.{action}"] = False
    capabilities.setdefault("mount.export", True)
    capabilities["mount.share_link"] = bool(capabilities.get("mount.share_link") and shareable)
    return {
        "mount_id": str(space.pk),
        "display_name": space.name,
        "provider": "virtual",
        "enabled": True,
        "params": {"capabilities": capabilities},
        "space_id": str(space.pk),
        "actor_id": str(user.pk),
        "storage_status": {
            "maintenance": space.backend.maintenance,
            "inventory_updated_at": space.backend.inventory_completed_at,
        },
    }


def visible_space_mounts(user):
    """Discover only spaces with an explicit grant or personal ownership."""
    if not user or not user.is_authenticated or not user.is_active:
        return []
    spaces = StorageSpace.objects.filter(
        Q(owner=user, explicit_access=False)
        | Q(grants__user=user)
        | Q(grants__team__in=user.teams),
        enabled=True,
        backend__enabled=True,
    ).distinct()
    return [mount for space in spaces if (mount := resolve_space_mount(space.pk, user))]


def context(mount):
    """Revalidate activity and grants on every operation, including token-based IO."""
    user = User.objects.filter(pk=mount.get("actor_id"), is_active=True).first()
    resolved = resolve_space_mount(mount.get("space_id"), user)
    if not resolved:
        raise denied()
    space = StorageSpace.objects.select_related("backend", "owner").get(pk=resolved["space_id"])
    return space, user, native_connection(space.backend)


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def authorize(space, user, path, *, write=False, share=False, traverse=False):  # noqa: PLR0913
    """Permissions are additive; ownership of a view does not alter quota attribution."""
    path = normalize_mount_path(path)
    if not user or not user.is_authenticated or not user.is_active:
        raise denied()
    if not space.enabled or not space.backend.enabled:
        raise denied()
    if (write and space.backend.maintenance) or (share and not space.allow_sharing):
        raise denied()
    if not space.explicit_access and space.owner_id == user.pk:
        return path
    for grant in _grants(space, user):
        root = normalize_mount_path(grant.path)
        allowed = within(path, root) or (
            traverse and not (write or share) and within(path=root, root=path)
        )
        if allowed and (not write or grant.writable) and (not share or grant.shareable):
            return path
    raise denied()


def native_path(space, path):
    """Translate only after normalization; virtual clients never receive this path."""
    path = normalize_mount_path(path)
    # Reject Windows aliases/alternate data streams even when the current provider
    # is case-sensitive; a space can later move to another filesystem provider.
    if any(":" in part or part.endswith((".", " ")) for part in path.split("/") if part):
        raise denied()
    return normalize_mount_path(posixpath.join(space.root_path, path.lstrip("/")))


def registered_backend_ids():
    """Registered connections are no longer exposed as unrestricted legacy mounts."""
    return set(StorageBackend.objects.values_list("registry_id", flat=True))


def can_share_mount(mount, path):
    """Revalidate a virtual share without revealing a revoked target's existence."""
    if not mount or not mount.get("space_id"):
        return bool(mount)
    try:
        space, user, _ = context(mount)
        authorize(space, user, path, share=True)
    except MountProviderError:
        return False
    return True
