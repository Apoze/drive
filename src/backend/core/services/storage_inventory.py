"""Durable metadata inventory and attribution, separate from NAS credentials."""

import posixpath
import re
import uuid
from contextlib import contextmanager, nullcontext
from itertools import batched

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from core.entitlements import get_entitlements_backend
from core.models import (
    Item,
    StorageBackend,
    StorageInventoryEntry,
    StorageMoveJob,
    StorageQuota,
    StorageReservation,
    StorageSpace,
    StorageUsage,
)
from core.mounts.providers.base import MountProviderError
from core.mounts.registry import get_mount_provider
from core.services import storage_quota as quota
from core.services.storage_namespace import advisory_guard, namespace_guard
from core.services.storage_spaces import native_connection, within
from wopi.utils import compute_mount_entry_version

from drive.celery_app import app


def organization_for(user):
    """Use the trusted OIDC organization claim or an explicitly configured instance."""
    claim = getattr(settings, "ENTITLEMENTS_BACKEND_PARAMETERS", {}).get(
        "organization_claim", "siret"
    )
    organization = user.claims.get(claim) if user else None
    return str(organization or getattr(settings, "STORAGE_ORGANIZATION_ID", "local"))


def refresh_policy(user):
    """Sync configured limits; admission remains in Drive's transactional counters."""
    backend = get_entitlements_backend()
    policy_reader = getattr(backend, "get_storage_policy", None)
    if policy_reader:
        policy = policy_reader(user)
        policies = {
            f"organization:{organization_for(user)}": policy["organization"],
            f"user:{user.pk}": policy["account"],
        }
        prefixes = {
            "storage_backend": "backend",
            "storage_space": "space",
            "user_backend": "user-backend",
        }
        for resource in policy.get("resources", []):
            prefix = prefixes.get(resource.get("type"))
            identity = resource.get("id")
            if (
                prefix is None
                or not isinstance(identity, str)
                or not re.fullmatch(r"[a-zA-Z0-9:-]{1,200}", identity)
            ):
                raise ValueError("DeployCenter returned an invalid storage scope.")
            policies[f"{prefix}:{identity}"] = {
                "limit_bytes": resource["limit_bytes"],
                "growth_blocked": resource["growth_blocked"],
            }
        quota.apply_policy(
            policies,
            revision=policy["revision"],
            origin=f"deploycenter:{backend.service_id}:{organization_for(user)}",
            version=policy["version"],
        )
        # Report asynchronously so ST acknowledgement latency cannot slow file IO.
        report_key = f"storage-policy-report:{user.pk}:{policy['revision']}"
        if cache.add(report_key, True, timeout=300):
            transaction.on_commit(
                lambda: app.send_task(
                    "core.tasks.storage.acknowledge_policy",
                    args=[str(user.pk), policy["revision"]],
                )
            )
    elif limit_reader := getattr(backend, "get_storage_limit", None):
        quota.apply_policy(
            {f"user:{user.pk}": {"limit_bytes": limit_reader(user)}}, revision="local"
        )


def item_usage(item, *, initial_size=None):
    """Keep regular S3 items on their native storage; only account their metadata."""
    owner = item.creator
    organization = organization_for(owner)
    scopes = [f"organization:{organization}", "backend:s3"]
    if owner:
        scopes.append(f"user:{owner.pk}")
    return quota.observe_usage(
        key=quota.resource_key(f"item:{item.pk}"),
        size=0
        if item.hard_deleted_at
        else (int(item.size or 0) if initial_size is None else initial_size),
        scope_keys=scopes,
        organization=organization,
        owner=owner,
        item=item,
    )


def initialize_items():
    """Import historical S3 metadata before enabling shared admission budgets."""
    quota.ensure_accounts(["backend:s3"])
    for item in Item.objects.filter(type="file").select_related("creator").iterator(chunk_size=500):
        item_usage(item)
    StorageQuota.objects.filter(key="backend:s3").update(accounting_ready_at=timezone.now())


def audit_accounting():
    """Compare durable counters with their journals before an offline activation."""
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH used AS (
                SELECT scope, sum(size) AS bytes
                FROM core_storageusage,
                     jsonb_array_elements_text(scope_keys) AS scope GROUP BY scope
            ), held AS (
                SELECT scope.key AS scope, sum(scope.value::bigint) AS bytes
                FROM core_storagereservation,
                     jsonb_each_text(scope_reservations) AS scope
                WHERE state IN ('reserved', 'writing', 'publishing') GROUP BY scope.key
            )
            SELECT count(*) FROM core_storagequota AS budget
            FULL JOIN used ON budget.key = used.scope
            FULL JOIN held ON coalesce(budget.key, used.scope) = held.scope
            WHERE budget.key IS NULL
               OR budget.used_bytes != coalesce(used.bytes, 0)
               OR budget.reserved_bytes != coalesce(held.bytes, 0)
        """)
        mismatches = cursor.fetchone()[0]
    return {
        "counter_mismatches": mismatches,
        "items_without_accounting": Item.objects.filter(
            type="file", storageusage__isnull=True
        ).count(),
        "attribution_conflicts": StorageUsage.objects.filter(attribution_conflict=True).count(),
        "active_operations": StorageReservation.objects.filter(
            state__in=["reserved", "writing", "publishing"]
        ).count(),
        "active_folder_moves": StorageMoveJob.objects.filter(
            state__in=["queued", "running"]
        ).count(),
        "unready_s3": int(
            not StorageQuota.objects.filter(
                key="backend:s3", accounting_ready_at__isnull=False
            ).exists()
        ),
        "unready_backends": StorageBackend.objects.filter(enabled=True)
        .filter(
            Q(inventory_completed_at__isnull=True)
            | Q(maintenance=True)
            | Q(attribution_pending=True)
        )
        .count(),
    }


def resource_metrics(organization, user):
    """Publish existing budget scopes with friendly names; no paths or credentials."""
    labels = {"backend:s3": ("storage_backend", "s3", "Drive — S3")}
    for backend in StorageBackend.objects.filter(organization=organization):
        labels[f"backend:{backend.namespace}"] = (
            "storage_backend",
            str(backend.namespace),
            backend.name,
        )
        identity = f"{user.pk}:{backend.namespace}"
        labels[f"user-backend:{identity}"] = (
            "user_backend",
            identity,
            f"{user.email or user.pk} — {backend.name}",
        )
    for space in StorageSpace.objects.filter(backend__organization=organization).only("pk", "name"):
        labels[f"space:{space.pk}"] = ("storage_space", str(space.pk), space.name)
    budgets = {budget.key: budget for budget in StorageQuota.objects.filter(key__in=labels)}
    rows = []
    for key, (kind, identity, label) in labels.items():
        budget = budgets.get(key)
        rows.append(
            {
                "account": {"type": kind, "id": identity, "display_name": label[:255]},
                "metrics": {
                    "storage_used": budget.used_bytes if budget else 0,
                    "storage_reserved": budget.reserved_bytes if budget else 0,
                },
            }
        )
    return rows


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def mount_record(  # noqa: PLR0913
    backend,
    entry,
    *,
    actor=None,
    generation=None,
    spaces=None,
    lookup_existing=True,
    canonical_path=None,
):
    """Choose the owning root independently of the mount through which it was seen."""
    path = entry.normalized_path
    if spaces is None:
        spaces = list(
            StorageSpace.objects.select_related("backend", "owner").filter(
                backend__namespace=backend.namespace
            )
        )
    # Namespace roots let two credentials expose different prefixes of the same NAS.
    canonical = canonical_path or posixpath.join(backend.namespace_root, path.lstrip("/"))
    identity = entry.object_identity or f"path:{canonical}"
    native_key = quota.resource_key(f"mount:{backend.namespace}:{identity}")
    existing = (
        StorageUsage.objects.filter(
            native_key=native_key,
        ).first()
        if lookup_existing
        else None
    )
    if lookup_existing and existing is None:
        replacement = (
            StorageUsage.objects.filter(
                backend__namespace=backend.namespace,
                path=canonical,
            )
            .exclude(version="missing")
            .order_by("key")
            .first()
        )
        if replacement:
            # A single path cannot distinguish replacement from rename + recreation.
            raise quota.StorageWriteConflict(
                "Storage changed externally; refresh its inventory before writing."
            )
    if existing and generation is None:
        canonical = existing.path
    containing = [
        space
        for space in spaces
        if within(
            canonical, posixpath.join(space.backend.namespace_root, space.root_path.lstrip("/"))
        )
    ]
    containing.sort(
        key=lambda space: (len(space.backend.namespace_root) + len(space.root_path), str(space.pk)),
        reverse=True,
    )
    space = containing[0] if containing else None
    owner = space.owner if space else None
    if (
        space
        and owner is None
        and space.attribute_to_creator
        and actor
        and not entry.object_identity
    ):
        owner = actor
    keys = [f"organization:{backend.organization}", f"backend:{backend.namespace}"]
    keys += [f"space:{ancestor.pk}" for ancestor in containing]
    if owner:
        keys += [f"user:{owner.pk}", f"user-backend:{owner.pk}:{backend.namespace}"]
    key = quota.resource_key(f"usage:{uuid.uuid4()}")
    # A replacement has a new native inode, but its logical attribution remains.
    if existing:
        key = existing.key
    return {
        "key": key,
        "native_key": native_key,
        "size": int(entry.size or 0),
        "scope_keys": keys,
        "organization": backend.organization,
        "backend": backend,
        "space": space,
        "owner": owner,
        "path": canonical,
        "provider_identity": identity,
        "version": compute_mount_entry_version(entry),
        "scan_generation": generation,
    }


def observe_entry(backend, entry, *, actor=None, generation=None, canonical_path=None):
    """Record one observed object without taking ownership from a previous writer."""
    record = mount_record(
        backend, entry, actor=actor, generation=generation, canonical_path=canonical_path
    )
    existing = StorageUsage.objects.filter(key=record["key"]).first()
    if existing and existing.space_id != (record["space"].pk if record["space"] else None):
        StorageUsage.objects.filter(pk=existing.pk).update(attribution_conflict=True)
    return quota.observe_usage(**record)


@contextmanager
def inventory_lock(namespace):
    """PostgreSQL releases the session lock if a worker crashes or disconnects."""
    with advisory_guard(f"inventory:{namespace}"):
        yield


def scan_backend(backend_id, *, root_path="/"):
    """Serialize aliases of one namespace without a crash-prone time lease."""
    backend = StorageBackend.objects.get(pk=backend_id, enabled=True)
    with namespace_guard(backend, allow_maintenance=True), inventory_lock(backend.namespace):
        _scan_backend(backend_id, root_path=root_path)


def _canonical_scan_root(provider, mount, path):
    """Use native directory spelling, so path aliases cannot bypass owning roots."""
    canonical = "/"
    for component in path.strip("/").split("/") if path != "/" else ():
        target = provider.stat(mount=mount, normalized_path=posixpath.join(canonical, component))
        children = getattr(provider, "iter_children", provider.list_children)
        match = next(
            (
                entry
                for entry in children(mount=mount, normalized_path=canonical)
                if entry.object_identity == target.object_identity
            ),
            None,
        )
        if not match or not target.object_identity:
            raise quota.StorageWriteConflict("Directory identity changed during inventory.")
        canonical = posixpath.join(canonical, match.name)
    return canonical


def _check_configured_roots(backend, spaces, provider, mount, root_path):
    """A live root with different spelling needs correction before enabling writes."""
    coverage = posixpath.join(backend.namespace_root, root_path.lstrip("/"))
    roots = [
        posixpath.join(space.backend.namespace_root, space.root_path.lstrip("/"))
        for space in spaces
    ]
    roots = [root for root in roots if within(root, coverage)]
    observed = set(
        StorageInventoryEntry.objects.filter(
            namespace=backend.namespace, record__path__in=roots
        ).values_list("record__path", flat=True)
    )
    for root in set(roots) - observed:
        relative_root = posixpath.relpath(root, backend.namespace_root)
        relative = "/" if relative_root == "." else "/" + relative_root
        try:
            actual = _canonical_scan_root(provider, mount, relative)
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                continue
            raise
        if actual != relative:
            StorageBackend.objects.filter(namespace=backend.namespace).update(
                inventory_completed_at=None
            )
            raise quota.StorageWriteConflict(
                "Correct the configured storage root spelling before writing."
            )


def _apply_snapshot(backend, spaces, *, started, generation):
    """Resolve replacements against the entire scan, including later batches."""
    snapshot = StorageInventoryEntry.objects.filter(namespace=backend.namespace)
    spaces_by_id = {str(space.pk): space for space in spaces}
    rows = snapshot.order_by("pk").values_list("record", flat=True).iterator(chunk_size=500)
    for records in batched(rows, 500, strict=False):
        existing = dict(
            StorageUsage.objects.filter(
                native_key__in=[record["native_key"] for record in records],
            ).values_list("native_key", "key")
        )
        paths = {
            path: (key, native)
            for path, key, native in StorageUsage.objects.filter(
                backend__namespace=backend.namespace,
                path__in=[record["path"] for record in records],
            )
            .exclude(version="missing")
            .values_list("path", "key", "native_key")
        }
        still_present = set(
            snapshot.filter(
                native_key__in=[native for _, native in paths.values()],
            ).values_list("native_key", flat=True)
        )
        for record in records:
            candidate, native = paths.get(record["path"], (None, None))
            record["key"] = existing.get(
                record["native_key"],
                candidate if candidate and native not in still_present else record["key"],
            )
            record["backend"] = backend
            record["space"] = spaces_by_id.get(record.pop("space_id"))
            record["scan_generation"] = generation
        quota.observe_inventory_batch(records, started=started, generation=generation)


# Keep the metadata discovery and publication order visible in one routine.
# pylint: disable-next=too-many-statements,too-many-locals
def _scan_backend(backend_id, *, root_path="/"):  # noqa: PLR0915
    """Rescan metadata. Incomplete scans never infer deletions or release reservations."""
    generation = uuid.uuid4()
    started = timezone.now()
    with transaction.atomic():
        backend = StorageBackend.objects.select_for_update().get(pk=backend_id, enabled=True)
        backend.inventory_generation = generation
        backend.save(update_fields=["inventory_generation", "updated_at"])
    try:
        # A crashed scan leaves metadata only. Restart discovery without inferring
        # deletions from its incomplete snapshot. Disk grows with metadata, not RAM.
        StorageInventoryEntry.objects.filter(namespace=backend.namespace).delete()
        mount = {**native_connection(backend), "_deny_reparse": True}
        provider = get_mount_provider(mount["provider"])
        root_path = _canonical_scan_root(provider, mount, root_path)
        spaces = list(
            StorageSpace.objects.select_related("backend", "owner").filter(
                backend__namespace=backend.namespace
            )
        )
        batch = []

        def flush():
            entries = []
            for entry_record in batch:
                record = dict(entry_record)
                record.pop("backend")
                record.pop("scan_generation")
                record["owner_id"] = str(record.pop("owner").pk) if record["owner"] else None
                record.pop("owner", None)
                record["space_id"] = str(record.pop("space").pk) if record["space"] else None
                record.pop("space", None)
                entries.append(
                    StorageInventoryEntry(
                        namespace=backend.namespace, native_key=record["native_key"], record=record
                    )
                )
            StorageInventoryEntry.objects.bulk_create(entries, batch_size=500)
            batch.clear()

        private_bytes = 0
        pending = [(root_path, False)]
        while pending:
            path, private = pending.pop()
            confine = getattr(provider, "confine", None)
            guard = confine(mount=mount, normalized_path=f"{path}/_") if confine else nullcontext()
            with guard:
                entry = provider.stat(mount=mount, normalized_path=path)
                if not private:
                    batch.append(
                        mount_record(
                            backend,
                            entry,
                            generation=generation,
                            spaces=spaces,
                            lookup_existing=False,
                        )
                    )
                children = getattr(provider, "iter_children", provider.list_children)
                for child in children(mount=mount, normalized_path=path):
                    private_child = private or child.name.startswith(".drive-txn-")
                    if child.entry_type == "folder":
                        pending.append((child.normalized_path, private_child))
                    if private_child:
                        private_bytes += int(child.size or 0)
                        continue
                    batch.append(
                        mount_record(
                            backend,
                            child,
                            generation=generation,
                            spaces=spaces,
                            lookup_existing=False,
                        )
                    )
                    if len(batch) >= 500:
                        flush()
            if len(batch) >= 500:
                flush()
        flush()
        _check_configured_roots(backend, spaces, provider, mount, root_path)
        _apply_snapshot(backend, spaces, started=started, generation=generation)
        # Objects written since scan start may not have been visited. Keep them.
        missing = StorageUsage.objects.filter(backend=backend, observed_at__lt=started).exclude(
            scan_generation=generation
        )
        if root_path != "/":
            canonical_root = posixpath.join(backend.namespace_root, root_path.lstrip("/"))
            missing = missing.filter(
                Q(path=canonical_root) | Q(path__startswith=canonical_root.rstrip("/") + "/")
            )
        for usage in missing.iterator(chunk_size=500):
            quota.observe_usage(
                key=usage.key,
                size=0,
                scope_keys=usage.scope_keys,
                organization=usage.organization,
                version="missing",
                observed_before=started,
            )
        if root_path == "/":
            capacity_reader = getattr(provider, "capacity", None)
            capacity = capacity_reader(mount=mount) if capacity_reader else {}
            StorageBackend.objects.filter(pk=backend.pk, inventory_generation=generation).update(
                inventory_completed_at=timezone.now(),
                capacity={
                    **capacity,
                    "private_logical_bytes": private_bytes,
                    "observed_at": timezone.now().isoformat(),
                },
            )
    finally:
        StorageInventoryEntry.objects.filter(namespace=backend.namespace).delete()
        StorageBackend.objects.filter(pk=backend_id, inventory_generation=generation).update(
            inventory_generation=None
        )
