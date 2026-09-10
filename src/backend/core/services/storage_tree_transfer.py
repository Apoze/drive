"""Journal folder attribution in bounded batches around one native rename."""

import posixpath
from dataclasses import replace

from django.db import transaction
from django.db.models import Func, OuterRef, Q, Subquery
from django.utils import timezone

from core.models import (
    Item,
    StorageBackend,
    StorageMoveJob,
    StorageQuota,
    StorageReservation,
    StorageSpace,
    StorageTransferEntry,
    StorageUsage,
    User,
)
from core.mounts.providers.base import MountEntry
from core.mounts.registry import get_mount_provider
from core.services import storage_inventory as inventory
from core.services import storage_quota as quota
from core.services.docs_anchors import moved_attributions, subtree_usages
from core.services.storage_namespace import namespace_guard
from core.services.storage_spaces import namespace_path, native_connection, within
from wopi.utils import compute_mount_entry_version


@transaction.atomic
def ensure_subtree_idle(backend, path):
    """Recover a crashed child writer before moving or deleting its parent."""
    canonical = namespace_path(backend, path)
    quota.guard_metadata_change(
        StorageUsage.objects.filter(
            Q(path=canonical) | Q(path__startswith=canonical.rstrip("/") + "/"),
            backend__namespace=backend.namespace,
        )
    )
    quota.guard_metadata_change(subtree_usages(backend, canonical))


def attribution(record):
    """Persist stable IDs, never model objects or NAS credentials."""
    return {
        "path": record["path"],
        "organization": record["organization"],
        "owner_id": str(record["owner"].pk) if record["owner"] else None,
        "space_id": str(record["space"].pk) if record["space"] else None,
    }


@transaction.atomic
def prepare_transfer(operation, records):
    """Reserve aggregate target growth and persist each object's transfer once."""
    operation = StorageReservation.objects.select_for_update().get(pk=operation.pk)
    initial_charges = dict(operation.scope_reservations)
    charges = dict(initial_charges)
    rows = []

    def flush():
        if (
            StorageReservation.objects.filter(
                resource_key__in=[row.usage.key for row in rows],
                state__in=["reserved", "writing", "publishing"],
            )
            .exclude(pk=operation.pk)
            .exists()
        ):
            raise quota.StorageWriteConflict(
                "Finish active file operations before moving their folder."
            )
        StorageTransferEntry.objects.bulk_create(rows)
        rows.clear()

    for usage, destination in records:
        targets = sorted(set(destination["scope_keys"]))
        for key in set(targets) - set(usage.scope_keys):
            charges[key] = charges.get(key, 0) + usage.size
        rows.append(
            StorageTransferEntry(
                operation=operation,
                usage=usage,
                size=usage.size,
                source_scopes=usage.scope_keys,
                target_scopes=targets,
                target_attribution=attribution(destination),
            )
        )
        if len(rows) >= 500:
            flush()
    flush()
    quota.ensure_accounts(charges)
    accounts = quota.lock_accounts(charges)
    growth = {key: amount - initial_charges.get(key, 0) for key, amount in charges.items()}
    for amount in set(growth.values()):
        quota.reserve_growth(
            [account for account in accounts if growth[account.key] == amount], amount
        )
    operation.scope_reservations = charges
    operation.policy_revisions.update(
        {account.key: account.policy_revision for account in accounts}
    )
    operation.save(update_fields=["scope_reservations", "policy_revisions", "updated_at"])


@transaction.atomic
def _commit_batch(operation_id):
    operation = StorageReservation.objects.select_for_update().get(pk=operation_id)
    entries = list(
        operation.transfer_entries.filter(applied=False)
        .select_related("usage")
        .order_by("usage__key")[:500]
    )
    if not entries:
        return False
    usages = {
        usage.pk: usage
        for usage in StorageUsage.objects.select_for_update()
        .filter(
            pk__in=[entry.usage_id for entry in entries],
        )
        .order_by("key")
    }
    deltas, released = {}, {}
    for entry in entries:
        usage = usages[entry.usage_id]
        if usage.size != entry.size or set(usage.scope_keys) != set(entry.source_scopes):
            raise quota.StorageWriteConflict(
                "Transfer metadata changed; reconciliation is required."
            )
        for key in set(entry.target_scopes) - set(entry.source_scopes):
            deltas[key] = deltas.get(key, 0) + entry.size
            released[key] = released.get(key, 0) + entry.size
        for key in set(entry.source_scopes) - set(entry.target_scopes):
            deltas[key] = deltas.get(key, 0) - entry.size
        usage.scope_keys = entry.target_scopes
        for field, value in entry.target_attribution.items():
            setattr(usage, field, value)
        usage.attribution_conflict = False
        usage.observed_at = timezone.now()
        entry.applied = True
    accounts = quota.lock_accounts(deltas)
    for account in accounts:
        account.used_bytes += deltas[account.key]
        amount = released.get(account.key, 0)
        account.reserved_bytes -= amount
        operation.scope_reservations[account.key] = (
            operation.scope_reservations.get(account.key, 0) - amount
        )
        if (
            min(
                account.used_bytes,
                account.reserved_bytes,
                operation.scope_reservations[account.key],
            )
            < 0
        ):
            raise quota.StorageWriteConflict("Storage accounting requires reconciliation.")
    StorageQuota.objects.bulk_update(accounts, ["used_bytes", "reserved_bytes"])
    StorageUsage.objects.bulk_update(
        list(usages.values()),
        [
            "scope_keys",
            "path",
            "organization",
            "owner_id",
            "space_id",
            "attribution_conflict",
            "observed_at",
        ],
    )
    StorageTransferEntry.objects.bulk_update(entries, ["applied"])
    operation.save(update_fields=["scope_reservations", "updated_at"])
    return True


def finish_transfer(operation_id, *, version):
    """Retry after any committed batch; shared budgets keep their original charge."""
    while _commit_batch(operation_id):
        pass
    operation = StorageReservation.objects.get(pk=operation_id)
    relocate_recovery_paths(operation)
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_resources import relocate_resources  # noqa: PLC0415

    relocate_resources(operation)
    quota.commit(operation_id, size=operation.publication["size"], version=version)
    if operation.publication.get("kind") == "reclassify":
        StorageBackend.objects.filter(namespace=operation.publication["namespace"]).update(
            maintenance=False,
            attribution_pending=False,
        )


def enter_maintenance(backend):
    """Drain app writers and retain read access before administrative changes."""
    with namespace_guard(backend, exclusive=True, allow_maintenance=True):
        connections = [
            str(pk)
            for pk in StorageBackend.objects.filter(namespace=backend.namespace).values_list(
                "pk", flat=True
            )
        ]
        if StorageReservation.objects.filter(
            Q(publication__backend_id__in=connections)
            | Q(publication__connection_id__in=connections)
            | Q(publication__source_connection_id__in=connections),
            state__in=["reserved", "writing", "publishing"],
        ).exists():
            raise quota.StorageWriteConflict(
                "Reconcile outstanding publications before maintenance."
            )
        StorageBackend.objects.filter(namespace=backend.namespace).update(maintenance=True)


def _reclassify_s3_backend(backend):
    """Rebind each logical tree to its deepest root while writes remain fenced."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_migration import rebind_usage  # noqa: PLC0415

    with namespace_guard(backend, exclusive=True, allow_maintenance=True):
        roots = (
            StorageSpace.objects.filter(
                backend=backend, root_item__path__ancestors=OuterRef("path")
            )
            .annotate(root_depth=Func("root_item__path", function="nlevel"))
            .order_by("-root_depth", "pk")
        )
        items = Item.objects.filter(storage_backend=backend)
        if (
            items.alias(owning_space=Subquery(roots.values("pk")[:1]))
            .filter(owning_space__isnull=True)
            .exists()
        ):
            raise quota.StorageWriteConflict("Assign a space to every logical tree first.")
        with transaction.atomic():
            quota.guard_metadata_change(StorageUsage.objects.filter(backend=backend))
            items.update(storage_space_id=Subquery(roots.values("pk")[:1]))
        for usage in (
            StorageUsage.objects.filter(backend__namespace=backend.namespace, item__isnull=False)
            .select_related("item__creator", "item__storage_backend", "item__storage_space__owner")
            .iterator(chunk_size=500)
        ):
            rebind_usage(usage, inventory.item_attribution(usage.item))
        StorageBackend.objects.filter(namespace=backend.namespace).update(
            maintenance=False, attribution_pending=False
        )


def reclassify_backend(backend_id, actor_id, *, job_id=None):
    """Apply changed owning roots atomically in batches, then resume writes."""
    backend = StorageBackend.objects.get(pk=backend_id, maintenance=True)
    actor = User.objects.get(Q(is_staff=True) | Q(is_superuser=True), pk=actor_id, is_active=True)
    if backend.family == "s3":
        _reclassify_s3_backend(backend)
        return
    with namespace_guard(backend, exclusive=True, allow_maintenance=True):
        connections = StorageBackend.objects.filter(namespace=backend.namespace)
        for connection in connections:
            inventory.scan_backend(connection.pk)
        spaces = list(
            StorageSpace.objects.select_related("backend", "owner").filter(
                backend__namespace=backend.namespace
            )
        )
        owners = {space.owner_id for space in spaces if space.owner_id}
        for owner in User.objects.filter(pk__in=owners | {actor.pk}):
            inventory.refresh_policy(owner, organization=backend.organization)
        mount = {**native_connection(backend), "_deny_reparse": True}
        provider = get_mount_provider(mount["provider"])
        root = inventory.observe_entry(backend, provider.stat(mount=mount, normalized_path="/"))

        def destination(usage):
            entry = MountEntry(
                entry_type="file",
                normalized_path=usage.path,
                name=posixpath.basename(usage.path),
                size=usage.size,
            )
            return inventory.mount_record(
                backend,
                entry,
                actor=usage.owner,
                spaces=spaces,
                canonical_path=usage.path,
                lookup_existing=False,
            )

        target = destination(root)
        records = (
            (usage, destination(usage))
            for usage in StorageUsage.objects.filter(
                backend__namespace=backend.namespace,
            )
            .exclude(version="missing")
            .exclude(pk=root.pk)
            .select_related("owner")
            .order_by("key")
            .iterator(chunk_size=500)
        )
        with transaction.atomic():
            operation = quota.admit(
                key=root.key, actor=actor, size=root.size, target_scopes=target["scope_keys"]
            )
            prepare_transfer(operation, records)
            quota.begin_publication(
                operation.pk,
                size=root.size,
                observed_version=root.version,
                publication={
                    "kind": "reclassify",
                    **({"admin_job_id": str(job_id)} if job_id else {}),
                    "namespace": str(backend.namespace),
                    "backend_id": str(backend.pk),
                    "path": "/",
                    "source_identity": root.provider_identity,
                    "target_attribution": attribution(target),
                },
            )
            if job_id:
                # pylint: disable-next=import-outside-toplevel,cyclic-import
                from core.models import StorageAdminJob  # noqa: PLC0415

                StorageAdminJob.objects.filter(pk=job_id).update(operation=operation)
        finish_transfer(operation.pk, version=root.version)


def relocate_recovery_paths(operation):
    """Keep retained copies reachable after a native folder move, across aliases."""
    publication = operation.publication
    if publication.get("kind") not in {"tree_move", "delete"} or not publication.get("source_path"):
        return
    backend = StorageBackend.objects.get(pk=publication["backend_id"])
    source = namespace_path(backend, publication["source_path"])
    target = posixpath.join(
        backend.namespace_root, (publication.get("backup_path") or publication["path"]).lstrip("/")
    )
    connections = {
        str(connection.pk): connection
        for connection in StorageBackend.objects.filter(namespace=backend.namespace)
    }
    # Retained versions move with their parent directory. Rewriting is idempotent.
    for previous in (
        StorageReservation.objects.filter(
            Q(publication__backend_id__in=list(connections))
            | Q(publication__native_source__backend_id__in=list(connections)),
        )
        .exclude(pk=operation.pk)
        .iterator(chunk_size=500)
    ):
        changed = False
        nested = previous.publication.get("native_source", {})
        info = nested if nested.get("backend_id") in connections else previous.publication
        connection = connections[info["backend_id"]]
        paths = {}
        for field in ("path", "temp_path", "backup_path"):
            path = info.get(field)
            if not path:
                continue
            canonical = namespace_path(connection, path)
            if within(canonical, source):
                canonical = target + canonical[len(source) :]
                changed = True
            paths[field] = canonical
        if changed:
            if any(not within(path, backend.namespace_root) for path in paths.values()):
                raise quota.StorageWriteConflict(
                    "A retained version needs a connection covering its new location."
                )
            info.update(
                {
                    field: "/" + path[len(backend.namespace_root.rstrip("/")) :].lstrip("/")
                    for field, path in paths.items()
                }
            )
            info["backend_id"] = str(backend.pk)
            info["retained_generation"] = backend.configuration_generation
            if "canonical_path" in info:
                info["canonical_path"] = namespace_path(backend, info["path"])
            previous.save(update_fields=["publication", "updated_at"])


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def move_tree(  # noqa: PLR0913
    *, space, actor, provider, mount, source, destination_path, job_id=None
):
    """Caller holds the namespace exclusively through native IO and accounting."""
    backend = space.backend
    src = source.normalized_path
    ensure_subtree_idle(backend, src)
    if within(destination_path, src):
        raise quota.StorageWriteConflict("A folder cannot be moved inside itself.")
    inventory.scan_backend(backend.pk, root_path=src)
    source = provider.stat(mount=mount, normalized_path=src)
    usage = inventory.observe_entry(backend, source)
    parent = inventory.observe_entry(
        backend, provider.stat(mount=mount, normalized_path=posixpath.dirname(destination_path))
    )
    spaces = list(
        StorageSpace.objects.select_related("backend", "owner").filter(
            backend__namespace=backend.namespace
        )
    )
    destination = inventory.mount_record(
        backend,
        replace(source, normalized_path=destination_path, object_identity=None),
        actor=usage.owner or actor,
        lookup_existing=False,
        spaces=spaces,
        canonical_path=posixpath.join(parent.path, posixpath.basename(destination_path)),
    )
    inventory.refresh_policy(
        destination["owner"] or actor, organization=destination["organization"]
    )
    for _, document_target in moved_attributions(backend, usage.path, destination["path"], spaces):
        if document_target["owner"]:
            inventory.refresh_policy(
                document_target["owner"], organization=document_target["organization"]
            )
    descendants = (
        StorageUsage.objects.filter(
            backend__namespace=backend.namespace,
            path__startswith=usage.path.rstrip("/") + "/",
        )
        .exclude(version="missing")
        .select_related("owner")
        .order_by("key")
    )

    def records():
        yield from moved_attributions(backend, usage.path, destination["path"], spaces)
        for child in descendants.iterator(chunk_size=500):
            path = destination["path"] + child.path[len(usage.path) :]
            entry = MountEntry(
                entry_type="file",
                normalized_path=path,
                name=posixpath.basename(path),
                size=child.size,
            )
            yield (
                child,
                inventory.mount_record(
                    backend,
                    entry,
                    actor=child.owner or actor,
                    lookup_existing=False,
                    spaces=spaces,
                    canonical_path=path,
                ),
            )

    with transaction.atomic():
        operation = quota.admit(
            key=usage.key,
            actor=actor,
            size=usage.size,
            target_scopes=destination["scope_keys"],
            publication_key=quota.resource_key(f"path:{backend.namespace}:{destination['path']}"),
        )
        operation.publication = {
            "kind": "tree_move",
            "namespace": str(backend.namespace),
            "backend_id": str(backend.pk),
            "source_path": src,
            "path": destination_path,
            "source_identity": source.object_identity,
            "target_attribution": attribution(destination),
        }
        operation.save(update_fields=["publication", "updated_at"])
        prepare_transfer(operation, records())
        if job_id:
            StorageMoveJob.objects.filter(pk=job_id, actor=actor).update(operation=operation)
    publishing = False
    try:
        latest = provider.stat(mount=mount, normalized_path=src)
        quota.begin_publication(
            operation.pk,
            observed_version=compute_mount_entry_version(latest),
            size=usage.size,
            publication=operation.publication,
        )
        publishing = True
        provider.rename_no_replace(
            mount=mount, src_normalized_path=src, dst_normalized_path=destination_path
        )
        final = provider.stat(mount=mount, normalized_path=destination_path)
        if final.object_identity != source.object_identity:
            raise quota.StorageWriteConflict("Folder publication requires reconciliation.")
        finish_transfer(operation.pk, version=compute_mount_entry_version(final))
    except Exception:
        if not publishing:
            quota.cancel(operation.pk)
        raise
