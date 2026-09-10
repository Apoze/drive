"""Bounded technical observations of document locations, never content ownership."""

import hashlib
import time
from contextlib import ExitStack, contextmanager
from copy import copy

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import Exists, OuterRef, Q

from rest_framework.exceptions import APIException

from core.models import DocsBinding, StorageUsage
from core.mounts.providers.base import MountProviderError
from core.mounts.registry import get_mount_provider
from core.services.storage_spaces import native_connection, within


@contextmanager
def guard_locations(*locations, allow_maintenance=False):
    """Fence document placement against native directory moves and deletions."""
    from core.models import StorageResource  # noqa: PLC0415
    from core.services.storage_namespace import namespace_guard  # noqa: PLC0415

    backends = {
        str(space.backend.namespace): space.backend
        for parent, space in locations
        if isinstance(parent, StorageResource) and space
    }
    with ExitStack() as guards:
        for namespace in sorted(backends):
            guards.enter_context(
                namespace_guard(backends[namespace], allow_maintenance=allow_maintenance)
            )
        yield


def recovery_reason(binding):
    """An outage is not proof of deletion; report it without changing any state."""
    from core.services.storage_resources import space_root  # noqa: PLC0415

    anchor, space = binding.mounted_parent, binding.anchor_space
    if anchor is None or space is None:
        return None
    if anchor.missing:
        return "missing"
    if not space.enabled or not space.backend.enabled or not within(anchor.path, space_root(space)):
        return "outside_scope"
    try:
        return None if current_anchor(anchor, space.backend) else "unverified_identity"
    except APIException as exc:
        if exc.status_code != 503:
            raise
        return "unavailable"


def can_recover(item, user):
    """Only a current documentary owner can relocate an orphan, never a NAS operator."""
    from suite_identity.access import require_access  # noqa: PLC0415

    from core.services.storage_access import principal  # noqa: PLC0415

    if not settings.DOCS_DRIVE_ENABLED or not user.is_authenticated or not user.is_active:
        return False
    require_access(user)
    binding = DocsBinding.objects.select_related("mounted_parent", "anchor_space__backend").get(
        item=item
    )
    return (
        binding.state in {"active", "trash"}
        and not item.hard_deleted_at
        and item.accesses.filter(principal(user), role="owner").exists()
        and recovery_reason(binding) in {"missing", "outside_scope", "unverified_identity"}
    )


def recovery_page(user, *, offset=0, limit=50):
    """Scan owned anchors in bounded pages; do not reveal sibling storage contents."""
    from rest_framework.exceptions import PermissionDenied  # noqa: PLC0415
    from suite_identity.access import require_access  # noqa: PLC0415

    from core.models import ItemAccess  # noqa: PLC0415
    from core.services.storage_access import principal  # noqa: PLC0415

    require_access(user)
    if not settings.DOCS_DRIVE_ENABLED or not user.is_authenticated or not user.is_active:
        raise PermissionDenied()
    ownership = ItemAccess.objects.filter(
        principal(user), item_id=OuterRef("item_id"), role="owner"
    )
    candidates = (
        DocsBinding.objects.alias(owned=Exists(ownership))
        .filter(owned=True, mounted_parent__isnull=False, state__in=["active", "trash"])
        .select_related("item", "mounted_parent", "anchor_space__backend")
        .order_by("pk")
    )
    rows = list(candidates[offset : offset + limit + 1])
    results = []
    for binding in rows[:limit]:
        if reason := recovery_reason(binding):
            results.append(
                {
                    "document_id": str(binding.document_id),
                    "title": binding.item.title,
                    "revision": binding.revision,
                    "state": binding.state,
                    "reason": reason,
                    "can_recover": reason != "unavailable",
                }
            )
    return {"results": results, "next_offset": offset + limit if len(rows) > limit else None}


def prepare_folder_deletion(backend, path, actor):
    """Snapshot the native anchor only after checking every affected document."""
    from rest_framework.exceptions import PermissionDenied  # noqa: PLC0415

    from core.models import Item, StorageResource  # noqa: PLC0415

    if not settings.DOCS_DRIVE_ENABLED:
        return None
    anchor = StorageResource.objects.filter(namespace=backend.namespace, path=path).first()
    if anchor is None:
        return None
    roots = DocsBinding.objects.filter(mounted_parent=anchor)
    descendants = roots.filter(item__path__ancestors=OuterRef("path"))
    documents = Item.objects.alias(anchored=Exists(descendants)).filter(
        anchored=True, ancestors_deleted_at__isnull=True, hard_deleted_at__isnull=True
    )
    for item in documents.iterator(chunk_size=100):
        if not item.get_abilities(actor).get("destroy"):
            raise PermissionDenied("Moving this folder to trash requires managing its documents.")
    return str(anchor.pk)


def finish_folder_deletion(anchor_id, actor):
    """A proven, journaled deletion trashes references; it never purges content."""
    from core.services.item_activity import record_item_activity  # noqa: PLC0415

    for binding in (
        DocsBinding.objects.filter(
            mounted_parent_id=anchor_id, item__ancestors_deleted_at__isnull=True
        )
        .select_related("item")
        .order_by("pk")
        .iterator(chunk_size=100)
    ):
        binding.item.soft_delete()
        record_item_activity(item=binding.item, actor=actor, action="trashed")


def subtree_usages(backend, path):
    """Logical document bytes belong to their mounted anchor's subtree."""
    if not settings.DOCS_DRIVE_ENABLED:
        return StorageUsage.objects.none()
    anchors = DocsBinding.objects.filter(
        Q(mounted_parent__path=path) | Q(mounted_parent__path__startswith=path.rstrip("/") + "/"),
        mounted_parent__namespace=backend.namespace,
        item__path__ancestors=OuterRef("item__path"),
    )
    return (
        StorageUsage.objects.filter(item__type="docs")
        .alias(anchored=Exists(anchors))
        .filter(anchored=True)
    )


def moved_attributions(backend, source, target, spaces):
    """Derive document budgets without charging their bytes to a native connection."""
    from core.mounts.providers.base import MountEntry  # noqa: PLC0415
    from core.services.docs_quota import attribution  # noqa: PLC0415
    from core.services.docs_resources import placement  # noqa: PLC0415
    from core.services.storage_inventory import mount_record  # noqa: PLC0415

    for usage in (
        subtree_usages(backend, source)
        .select_related("item__creator")
        .order_by("key")
        .iterator(chunk_size=100)
    ):
        anchor, _ = placement(usage.item)
        planned = copy(anchor)
        planned.path = target + anchor.path[len(source) :]
        location = mount_record(
            backend,
            MountEntry(entry_type="folder", normalized_path=planned.path, name=anchor.name),
            actor=usage.item.creator,
            lookup_existing=False,
            spaces=spaces,
            canonical_path=planned.path,
        )
        if not location["space"]:
            from core.services.storage_quota import StorageWriteConflict  # noqa: PLC0415

            raise StorageWriteConflict("Choose an allocated destination for these documents.")
        yield (
            usage,
            {
                "path": usage.path,
                **attribution(usage.item, placement_override=(planned, location["space"])),
            },
        )


def current_anchor(resource, backend):
    """Reject stale identities; share a ten-second stat across a folder's documents.

    A cache miss inside a transaction fails closed: callers must preflight before
    locking. Neither a failed stat nor an outage deletes the documentary data.
    """
    if (
        resource.missing
        or resource.kind != "folder"
        or not resource.provider_identity
        or resource.namespace != backend.namespace
        or not within(resource.path, backend.namespace_root)
    ):
        return False
    fingerprint = repr(
        (
            resource.pk,
            resource.path,
            resource.provider_identity,
            resource.updated_at,
            backend.pk,
            backend.configuration_generation,
            backend.updated_at,
        )
    )
    key = "docs-anchor:" + hashlib.sha256(fingerprint.encode()).hexdigest()
    observation = cache.get(key)
    if isinstance(observation, dict) and observation.get("deadline", 0) > time.time():
        if observation["valid"]:
            resource._docs_anchor_deadline = observation["deadline"]  # noqa: SLF001
        return observation["valid"]
    unavailable = APIException("Document location cannot be verified. Retry shortly.")
    unavailable.status_code = 503
    if connection.in_atomic_block:
        raise unavailable
    try:
        mount = {**native_connection(backend), "_deny_reparse": True}
        path = resource.path[len(backend.namespace_root.rstrip("/")) :] or "/"
        entry = get_mount_provider(mount["provider"]).stat(mount=mount, normalized_path=path)
    except MountProviderError as exc:
        if exc.public_code in {"mount.path.not_found", "mount.access.denied"}:
            cache.set(key, {"valid": False, "deadline": time.time() + 10}, timeout=10)
            return False
        raise unavailable from None
    valid = entry.entry_type == "folder" and entry.object_identity == resource.provider_identity
    deadline = time.time() + 10
    if valid:
        resource._docs_anchor_deadline = deadline  # noqa: SLF001
    cache.set(key, {"valid": valid, "deadline": deadline}, timeout=10)
    return valid
