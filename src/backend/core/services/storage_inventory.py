"""Durable metadata inventory and attribution, separate from NAS credentials."""

import posixpath
import re
import uuid
from contextlib import contextmanager, nullcontext
from datetime import datetime
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
    StorageResource,
    StorageSpace,
    StorageUsage,
)
from core.mounts.providers.base import MountEntry, MountProviderError
from core.mounts.registry import get_mount_provider
from core.services import storage_quota as quota
from core.services.storage_namespace import advisory_guard, namespace_guard
from core.services.storage_spaces import namespace_path, native_connection, within
from wopi.utils import compute_mount_entry_version

from drive.celery_app import app


def organization_for(user):
    """Use the trusted OIDC organization claim or an explicitly configured instance."""
    claim = getattr(settings, "ENTITLEMENTS_BACKEND_PARAMETERS", {}).get(
        "organization_claim", "siret"
    )
    organization = user.claims.get(claim) if user else None
    return str(organization or getattr(settings, "STORAGE_ORGANIZATION_ID", "local"))


def _apply_storage_policy(backend, policy, organization, user=None):
    """Absent resource overrides are unlimited within the authoritative organization."""
    if "instance" in policy:
        instance = policy["instance"]
        quota.apply_policy(
            {"instance:drive": instance},
            revision=f"instance:{instance['version']}",
            origin=f"deploycenter:{backend.service_id}:instance",
            version=instance["version"],
        )
    prefixes = {
        "storage_backend": "backend",
        "storage_space": "space",
        "user_backend": "user-backend",
    }
    policies = {
        f"{prefixes[row['account']['type']]}:{row['account']['id']}": {
            "limit_bytes": None,
            "growth_blocked": False,
        }
        for row in resource_metrics(organization, user)
        if row["account"]["type"] in prefixes
    }
    policies[f"organization:{organization}"] = policy["organization"]
    if user:
        policies[f"user:{user.pk}"] = policy["account"]
    explicit_scopes = {(row["type"], row["id"]) for row in policy.get("resources", [])}
    for resource in policy.get("resources", []):
        prefix, identity = prefixes.get(resource.get("type")), resource.get("id")
        if (
            prefix is None
            or not isinstance(identity, str)
            or not re.fullmatch(r"[a-zA-Z0-9:-]{1,200}", identity)
        ):
            raise ValueError("DeployCenter returned an invalid storage scope.")
        if (prefix == "backend" and identity == "s3") or (
            prefix == "user-backend" and identity.endswith(":s3")
        ):
            # Historical limits remain global; ST overrides belong to one organization.
            namespaces = list(
                StorageBackend.objects.filter(organization=organization, legacy_s3=True)
                .values_list("namespace", flat=True)
                .distinct()[:2]
            )
            if len(namespaces) != 1:
                raise ValueError(
                    "The legacy S3 policy needs an unambiguous organization connection."
                )
            identity = identity.removesuffix("s3") + str(namespaces[0])
            if (resource["type"], identity) in explicit_scopes:
                continue
        scope = f"{prefix}:{identity}"
        if prefix == "user-backend":
            _, separator, namespace = identity.partition(":")
            if not separator or f"backend:{namespace}" not in policies:
                continue
        elif scope not in policies:
            # Removed resources and foreign organizations cannot acquire policy ownership.
            continue
        policies[f"{prefix}:{identity}"] = {
            "limit_bytes": resource["limit_bytes"],
            "growth_blocked": resource["growth_blocked"],
        }
    quota.apply_policy(
        policies,
        revision=policy["revision"],
        origin=f"deploycenter:{backend.service_id}:{organization}",
        version=policy["version"],
    )


def refresh_policy(user, *, organization=None):
    """Sync the owner's allocation and the destination's independent organization."""
    backend = get_entitlements_backend()
    policy_reader = getattr(backend, "get_storage_policy", None)
    if policy_reader:
        policy = policy_reader(user)
        user_organization = organization_for(user)
        _apply_storage_policy(backend, policy, user_organization, user)
        report_key = f"storage-policy-report:{user.pk}:{policy['revision']}"
        if cache.add(report_key, True, timeout=300):
            transaction.on_commit(
                lambda: app.send_task(
                    "core.tasks.storage.acknowledge_policy",
                    args=[str(user.pk), policy["revision"]],
                )
            )
        if organization and organization != user_organization:
            refresh_organization_policy(organization)
    elif limit_reader := getattr(backend, "get_storage_limit", None):
        quota.apply_policy(
            {f"user:{user.pk}": {"limit_bytes": limit_reader(user)}}, revision="local"
        )


def refresh_organization_policy(organization):
    """Refresh shared storage even when its organization has no active members."""
    backend = get_entitlements_backend()
    reader = getattr(backend, "get_organization_storage_policy", None)
    if not callable(reader):
        return
    policy = reader(organization)
    _apply_storage_policy(backend, policy, organization)
    report_key = f"storage-policy-report:organization:{organization}:{policy['revision']}"
    if cache.add(report_key, True, timeout=300):
        transaction.on_commit(
            lambda: app.send_task(
                "core.tasks.storage.acknowledge_organization_policy",
                args=[organization, policy["revision"]],
            )
        )


def item_usage(item, *, initial_size=None):
    """Keep regular S3 items on their native storage; only account their metadata."""
    location = item_attribution(item)
    try:
        key = item.storageusage.key
    except StorageUsage.DoesNotExist:
        key = quota.resource_key(f"item:{item.pk}")
    return quota.observe_usage(
        key=key,
        size=0
        if item.hard_deleted_at
        else (int(item.size or 0) if initial_size is None else initial_size),
        item=item,
        **location,
    )


def item_attribution(item):
    """New objects inherit their space's budget; later editors never become owners."""
    backend = item.storage_backend if item.storage_backend_id else None
    space = item.storage_space if item.storage_space_id else None
    owner = space.owner if space and not space.attribute_to_creator else item.creator
    organization = backend.organization if backend else organization_for(owner)
    identities = [str(backend.namespace)] if backend else []
    if not backend or backend.legacy_s3:
        identities.append("s3")
    scopes = ["instance:drive", f"organization:{organization}"]
    scopes.extend(f"backend:{identity}" for identity in identities)
    if space:
        scopes.extend(
            f"space:{identity}"
            for identity in StorageSpace.objects.filter(
                backend=backend, root_item__path__ancestors=space.root_item.path
            ).values_list("pk", flat=True)
        )
    if owner:
        scopes.append(f"user:{owner.pk}")
        scopes.extend(f"user-backend:{owner.pk}:{identity}" for identity in identities)
    return {
        "scope_keys": scopes,
        "organization": organization,
        "owner": owner,
        "backend": backend,
        "space": space,
    }


def initialize_items():
    """Import historical S3 metadata before enabling shared admission budgets."""
    quota.ensure_accounts(["backend:s3"])
    for item in (
        Item.objects.filter(type="file")
        .select_related("creator", "storage_backend", "storage_space__owner", "storageusage")
        .iterator(chunk_size=500)
    ):
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
        "unready_backends": StorageBackend.objects.filter(enabled=True, family="mount")
        .filter(
            Q(inventory_completed_at__isnull=True)
            | Q(maintenance=True)
            | Q(attribution_pending=True)
        )
        .count(),
    }


def resource_metrics(organization, user):
    """Publish existing budget scopes with friendly names; no paths or credentials."""
    labels = {
        "instance:drive": ("storage_instance", "drive", "Drive — Instance"),
    }
    for backend in StorageBackend.objects.filter(organization=organization):
        backend_identity = str(backend.namespace)
        labels[f"backend:{backend_identity}"] = (
            "storage_backend",
            backend_identity,
            backend.name,
        )
        if user:
            identity = f"{user.pk}:{backend_identity}"
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
    canonical = canonical_path or namespace_path(backend, path)
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
        if within(canonical, namespace_path(space.backend, space.root_path))
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
    keys = [
        "instance:drive",
        f"organization:{backend.organization}",
        f"backend:{backend.namespace}",
    ]
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
    if quota.pending_native_paths(backend, [record["path"]]):
        raise quota.StorageWriteConflict("This destination's transfer needs recovery.")
    existing = StorageUsage.objects.filter(key=record["key"]).first()
    if existing and existing.space_id != (record["space"].pk if record["space"] else None):
        StorageUsage.objects.filter(pk=existing.pk).update(attribution_conflict=True)
    usage = quota.observe_usage(**record)
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_resources import observe_resources  # noqa: PLC0415

    observe_resources(backend, [entry], generation=generation)
    return usage


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
    coverage = namespace_path(backend, root_path)
    roots = [namespace_path(space.backend, space.root_path) for space in spaces]
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
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_resources import observe_resources  # noqa: PLC0415

    snapshot = StorageInventoryEntry.objects.filter(namespace=backend.namespace)
    spaces_by_id = {str(space.pk): space for space in spaces}
    rows = snapshot.order_by("pk").values_list("record", flat=True).iterator(chunk_size=500)
    for batch in batched(rows, 500, strict=False):
        pending = quota.pending_native_paths(backend, [record["path"] for record in batch])
        records = [record for record in batch if record["path"] not in pending]
        resource_entries = []
        for record in records:
            metadata = record.pop("resource_metadata", None)
            if metadata:
                resource_entries.append(
                    MountEntry(
                        "file",
                        metadata["path"],
                        metadata["name"],
                        record["size"],
                        datetime.fromisoformat(metadata["modified_at"])
                        if metadata["modified_at"]
                        else None,
                        record["provider_identity"],
                    )
                )
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
        observe_resources(backend, resource_entries, generation=generation)


# Keep the metadata discovery and publication order visible in one routine.
# pylint: disable-next=too-many-statements,too-many-locals
def _scan_backend(backend_id, *, root_path="/"):  # noqa: PLR0915
    """Rescan metadata. Incomplete scans never infer deletions or release reservations."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_resources import observe_resources  # noqa: PLC0415

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
        metadata = []

        def flush():
            observe_resources(
                backend,
                (entry for entry in metadata if entry.entry_type == "folder"),
                generation=generation,
            )
            by_path = {namespace_path(backend, entry.normalized_path): entry for entry in metadata}
            entries = []
            for entry_record in batch:
                record = dict(entry_record)
                source = by_path[record["path"]]
                record["resource_metadata"] = {
                    "path": source.normalized_path,
                    "name": source.name,
                    "modified_at": source.modified_at.isoformat() if source.modified_at else None,
                }
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
            metadata.clear()

        private_bytes = 0
        pending = [(root_path, False)]
        while pending:
            path, private = pending.pop()
            confine = getattr(provider, "confine", None)
            guard = confine(mount=mount, normalized_path=f"{path}/_") if confine else nullcontext()
            with guard:
                entry = provider.stat(mount=mount, normalized_path=path)
                if not private:
                    metadata.append(entry)
                children = getattr(provider, "iter_children", provider.list_children)
                for child in children(mount=mount, normalized_path=path):
                    private_child = private or child.name.startswith(".drive-txn-")
                    if child.entry_type == "folder":
                        pending.append((child.normalized_path, private_child))
                        continue
                    if private_child:
                        private_bytes += int(child.size or 0)
                        continue
                    metadata.append(child)
                    batch.append(
                        mount_record(
                            backend,
                            child,
                            generation=generation,
                            spaces=spaces,
                            lookup_existing=False,
                        )
                    )
                    if len(batch) >= 500 or len(metadata) >= 500:
                        flush()
            if len(batch) >= 500 or len(metadata) >= 500:
                flush()
        flush()
        _check_configured_roots(backend, spaces, provider, mount, root_path)
        _apply_snapshot(backend, spaces, started=started, generation=generation)
        canonical_root = namespace_path(backend, root_path)
        StorageResource.objects.filter(
            Q(path=canonical_root) | Q(path__startswith=canonical_root.rstrip("/") + "/"),
            namespace=backend.namespace,
            updated_at__lt=started,
        ).exclude(generation=generation).update(missing=True)
        # Objects written since scan start may not have been visited. Keep them.
        missing = StorageUsage.objects.filter(backend=backend, observed_at__lt=started).exclude(
            scan_generation=generation
        )
        if root_path != "/":
            canonical_root = namespace_path(backend, root_path)
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
