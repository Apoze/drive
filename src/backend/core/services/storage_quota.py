"""Logical-byte accounting and durable admission shared by S3 and mount writes.

No transaction in this module performs storage IO. Callers stage bytes, fence
publication, publish, then commit. Uncertain publications remain reserved until
the storage reconciler has observed their outcome.
"""

import hashlib
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from rest_framework.exceptions import APIException

from core.models import StorageQuota, StorageReservation, StorageUsage, User


class StorageQuotaExceeded(APIException):
    """The requested positive growth exceeds an application budget."""

    status_code = 413
    default_detail = "Storage quota exceeded."
    default_code = "storage.quota.exceeded"


class StorageWriteConflict(APIException):
    """A resource or operation changed before publication could be admitted."""

    status_code = 409
    default_detail = "Storage changed; refresh and retry."
    default_code = "storage.write.conflict"


def resource_key(identity):
    """Bound keys even for long provider paths; never expose paths in errors."""
    return hashlib.sha256(identity.encode()).hexdigest()


def guard_metadata_change(usages):
    """Fence deletion/renaming against admitted S3 publications in the same DB transaction."""
    if not transaction.get_connection().in_atomic_block:
        raise StorageWriteConflict("Metadata changes require a transaction.")
    for _ in (
        usages.select_for_update()
        .order_by("key")
        .values_list("key", flat=True)
        .iterator(chunk_size=500)
    ):
        pass
    if StorageReservation.objects.filter(
        resource_key__in=usages.values("key"), state__in=["reserved", "writing", "publishing"]
    ).exists():
        raise StorageWriteConflict("A storage operation is still using this item.")


def _byte_count(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 2**53 - 1:
        raise ValueError("Byte counts must be non-negative safe integers.")
    return value


def lock_accounts(keys):
    """Lock every affected account in the same order across workers."""
    keys = sorted(set(keys))
    accounts = list(StorageQuota.objects.select_for_update().filter(key__in=keys).order_by("key"))
    if len(accounts) != len(keys):
        raise StorageWriteConflict("Storage accounting is not initialized.")
    return accounts


def ensure_accounts(keys):
    """Create unlimited local scopes; policy synchronization supplies their ceilings."""
    StorageQuota.objects.bulk_create(
        [StorageQuota(key=key) for key in sorted(set(keys))], ignore_conflicts=True
    )


@transaction.atomic
def apply_policy(policies, *, revision, origin="", version=0):
    """Apply a complete set of limits without discarding admitted reservations."""
    policies = dict(policies)
    if origin:
        # Resource policies form a complete snapshot. Removing an exception
        # restores inheritance instead of leaving an obsolete local limit.
        retired = (
            StorageQuota.objects.filter(policy_origin=origin)
            .filter(
                Q(key__startswith="backend:")
                | Q(key__startswith="space:")
                | Q(key__startswith="user-backend:")
            )
            .exclude(key__in=policies)
            .values_list("key", flat=True)
        )
        policies.update({key: {"limit_bytes": None, "growth_blocked": False} for key in retired})
    ensure_accounts(policies)
    now = timezone.now()
    accounts = lock_accounts(policies)
    if any(
        account.policy_origin == origin and account.policy_version > version for account in accounts
    ):
        raise StorageWriteConflict("A newer storage policy is already applied.")
    for account in accounts:
        policy = policies[account.key]
        limit = policy["limit_bytes"]
        if limit is not None:
            _byte_count(limit)
        blocked = policy.get("growth_blocked", False)
        if not isinstance(blocked, bool):
            raise ValueError("growth_blocked must be a boolean.")
        account.limit_bytes = limit
        account.growth_blocked = blocked
        account.policy_revision = revision
        account.policy_origin = origin
        account.policy_version = version
        account.policy_applied_at = now
    StorageQuota.objects.bulk_update(
        accounts,
        [
            "limit_bytes",
            "growth_blocked",
            "policy_revision",
            "policy_applied_at",
            "policy_origin",
            "policy_version",
        ],
    )


def pending_native_paths(backend, paths):
    """Uncommitted move destinations are held by the source's existing charge."""
    candidates = {resource_key(f"path:{backend.namespace}:{path}"): path for path in paths}
    if not candidates:
        return set()
    return {
        candidates[key]
        for key in StorageReservation.objects.filter(
            publication_key__in=candidates,
            state__in=["reserved", "writing", "publishing"],
            publication__move_job_id__isnull=False,
        ).values_list("publication_key", flat=True)
    }


@transaction.atomic
# pylint: disable-next=too-many-branches
def observe_usage(  # noqa: PLR0912
    *, key, size, scope_keys, version=None, observed_before=None, **attribution
):
    """Reconcile observed bytes, including external growth beyond a quota.

    Existing attribution is stable. Readers and later writers do not become
    owners implicitly; an ownership transfer is a separate administrative action.
    """
    _byte_count(size)
    scope_keys = sorted(set(scope_keys))
    ensure_accounts(scope_keys)
    StorageUsage.objects.bulk_create(
        [StorageUsage(key=key, **attribution, size=0, scope_keys=scope_keys)], ignore_conflicts=True
    )
    lookup = (
        {"native_key": attribution["native_key"]} if attribution.get("native_key") else {"key": key}
    )
    try:
        usage = StorageUsage.objects.select_for_update().get(**lookup)
    except StorageUsage.DoesNotExist:
        try:
            usage = StorageUsage.objects.select_for_update().get(key=key)
        except StorageUsage.DoesNotExist:
            raise StorageWriteConflict() from None
    if observed_before is not None and usage.observed_at >= observed_before:
        return usage
    if StorageReservation.objects.filter(
        resource_key=usage.key, state__in=["reserved", "writing", "publishing"]
    ).exists():
        # A temporarily missing public path is not deletion during publication.
        return usage
    if (
        usage.size == 0
        and usage.provider_identity.startswith("path:")
        and not StorageReservation.objects.filter(
            resource_key=key, state__in=["reserved", "writing", "publishing"]
        ).exists()
    ):
        usage.scope_keys = scope_keys
        for field in ("owner", "space", "organization"):
            if field in attribution:
                setattr(usage, field, attribution[field])
    accounts = lock_accounts(usage.scope_keys)
    delta = size - usage.size
    for account in accounts:
        account.used_bytes += delta
        if account.used_bytes < 0:
            raise StorageWriteConflict("Storage accounting requires reconciliation.")
    StorageQuota.objects.bulk_update(accounts, ["used_bytes"])
    usage.size = size
    space = attribution.get("space")
    if space and space.attribute_to_creator and usage.owner_id is None:
        usage.attribution_conflict = True
    if version is not None:
        usage.version = version
        if version == "missing":
            usage.native_key = None
    # Path and scan metadata can change without transferring quota ownership.
    for field in ("path", "native_key", "provider_identity", "scan_generation"):
        if field in attribution:
            setattr(usage, field, attribution[field])
    usage.save()
    return usage


@transaction.atomic
# pylint: disable-next=too-many-branches
def observe_inventory_batch(records, *, started, generation):  # noqa: PLR0912
    """Reconcile bounded metadata batches with one lock/update per affected budget."""
    unique = {}
    for record in records:
        identity = record.get("native_key") or record["key"]
        if identity in unique and unique[identity]["space"] != record["space"]:
            unique[identity]["attribution_conflict"] = True
        else:
            unique.setdefault(identity, record)
    records = {record["key"]: record for record in unique.values()}
    if not records:
        return
    for record in records.values():
        _byte_count(record["size"])
    keys = sorted(records)
    StorageUsage.objects.bulk_create(
        [
            StorageUsage(**{**records[key], "size": 0, "scan_generation": generation})
            for key in keys
        ],
        ignore_conflicts=True,
    )
    usages = list(StorageUsage.objects.select_for_update().filter(key__in=keys).order_by("key"))
    busy = set(
        StorageReservation.objects.filter(
            resource_key__in=keys, state__in=["reserved", "writing", "publishing"]
        ).values_list("resource_key", flat=True)
    )
    deltas = {}
    changed = []
    now = timezone.now()
    for usage in usages:
        if usage.key in busy:
            continue
        # A concurrent Drive write or newer scan takes precedence over this snapshot.
        if usage.observed_at > started and usage.scan_generation != generation:
            continue
        record = records[usage.key]
        for scope in usage.scope_keys:
            deltas[scope] = deltas.get(scope, 0) + record["size"] - usage.size
        space_id = record["space"].pk if record["space"] else None
        usage.attribution_conflict |= usage.space_id != space_id or record.get(
            "attribution_conflict", False
        )
        if record["space"] and record["space"].attribute_to_creator and usage.owner_id is None:
            usage.attribution_conflict = True
        for field in ("size", "version", "path", "native_key", "provider_identity"):
            setattr(usage, field, record[field])
        usage.scan_generation = generation
        usage.observed_at = now
        changed.append(usage)
    ensure_accounts(deltas)
    accounts = lock_accounts(deltas)
    for account in accounts:
        account.used_bytes += deltas[account.key]
        if account.used_bytes < 0:
            raise StorageWriteConflict("Storage accounting requires reconciliation.")
    StorageQuota.objects.bulk_update(accounts, ["used_bytes"])
    StorageUsage.objects.bulk_update(
        changed,
        [
            "size",
            "version",
            "path",
            "native_key",
            "provider_identity",
            "scan_generation",
            "observed_at",
            "attribution_conflict",
        ],
    )


@transaction.atomic
def retire_usage(queryset):
    """Release logical bytes after a bulk Item deletion, keeping active reservations."""
    usages = list(queryset.select_for_update().exclude(size=0).order_by("key"))
    deltas = {}
    for usage in usages:
        for key in usage.scope_keys:
            deltas[key] = deltas.get(key, 0) + usage.size
        usage.size = 0
    accounts = lock_accounts(deltas)
    for account in accounts:
        account.used_bytes -= deltas[account.key]
        if account.used_bytes < 0:
            raise StorageWriteConflict("Storage accounting requires reconciliation.")
    StorageQuota.objects.bulk_update(accounts, ["used_bytes"])
    StorageUsage.objects.bulk_update(usages, ["size"])


@transaction.atomic
def bind_native_identity(key, *, native_key, provider_identity):
    """Merge a scanner's view of a just-published inode into its logical object."""
    rows = list(
        StorageUsage.objects.select_for_update()
        .filter(
            Q(key=key) | Q(native_key=native_key),
        )
        .order_by("key")
    )
    duplicate = next((row for row in rows if row.key != key), None)
    if duplicate:
        if StorageReservation.objects.filter(
            resource_key=duplicate.key, state__in=["reserved", "writing", "publishing"]
        ).exists():
            raise StorageWriteConflict("Storage identity requires reconciliation.")
        retire_usage(StorageUsage.objects.filter(pk=duplicate.pk))
        StorageUsage.objects.filter(pk=duplicate.pk).update(native_key=None, version="missing")
    StorageUsage.objects.filter(key=key).update(
        native_key=native_key, provider_identity=provider_identity
    )


def reserve_growth(accounts, growth):
    """Reserve the same growth in already locked quota scopes."""
    if growth <= 0:
        return
    for account in accounts:
        if account.growth_blocked or (
            account.limit_bytes is not None
            and account.used_bytes + account.reserved_bytes + growth > account.limit_bytes
        ):
            raise StorageQuotaExceeded()
    for account in accounts:
        account.reserved_bytes += growth
    StorageQuota.objects.bulk_update(accounts, ["reserved_bytes"])


@transaction.atomic
# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def admit(  # noqa: PLR0913
    *,
    key,
    actor,
    size,
    operation_id=None,
    lifetime=timedelta(hours=1),
    target_scopes=None,
    publication_key=None,
):
    """Reserve only logical growth, idempotently, before transferring any bytes."""
    _byte_count(size)
    if getattr(settings, "STORAGE_MIGRATION_MODE", False):
        raise StorageWriteConflict("Storage migration is in progress; writes are paused.")
    if (
        getattr(settings, "STORAGE_GOVERNANCE_ENABLED", False)
        and not StorageQuota.objects.filter(
            key="backend:s3",
            accounting_ready_at__isnull=False,
        ).exists()
    ):
        raise StorageWriteConflict("Storage accounting must be initialized before writes.")
    operation_id = operation_id or uuid.uuid4()
    # One actor may write files charged to different owners and namespaces.
    actor_id = actor.pk if actor else None
    if actor and not User.objects.select_for_update(no_key=True).get(pk=actor.pk).is_active:
        raise StorageWriteConflict("This account is inactive.")
    publication_key = publication_key or key
    usage = StorageUsage.objects.select_for_update().get(key=key)
    if actor is None and (not usage.item_id or usage.item.type != "docs"):
        raise StorageWriteConflict("An authenticated writer is required for file storage.")
    target_scopes = sorted(set(target_scopes if target_scopes is not None else usage.scope_keys))
    existing = StorageReservation.objects.filter(pk=operation_id).first()
    if existing:
        identity_matches = (
            existing.actor_id == actor_id
            and existing.resource_key == key
            and existing.publication_key == publication_key
            and existing.target_scope_keys == target_scopes
        )
        if (
            not identity_matches
            or existing.previous_size + existing.reserved_bytes < size
            or existing.state in {StorageReservation.State.CANCELLED}
            or existing.expires_at <= timezone.now()
        ):
            raise StorageWriteConflict()
        return existing
    if (
        StorageReservation.objects.filter(
            Q(actor=actor) if actor else Q(actor__isnull=True, resource_key=key),
            state__in=["reserved", "writing", "publishing"],
        ).count()
        >= settings.STORAGE_MAX_ACTIVE_WRITES_PER_USER
    ):
        raise StorageWriteConflict("Too many active writes. Wait for a transfer to finish.")
    if StorageReservation.objects.filter(
        Q(publication_key=publication_key) | Q(resource_key=key),
        state__in=["reserved", "writing", "publishing"],
    ).exists():
        raise StorageWriteConflict()
    ensure_accounts(target_scopes)
    accounts = lock_accounts([*usage.scope_keys, *target_scopes])
    growth = max(0, size - usage.size)
    charges = {
        account.key: (growth if account.key in usage.scope_keys else size)
        for account in accounts
        if account.key in target_scopes
    }
    for amount in set(charges.values()):
        reserve_growth(
            [account for account in accounts if charges.get(account.key) == amount], amount
        )
    return _create_operation(
        id=operation_id,
        resource_key=key,
        publication_key=publication_key,
        actor=actor,
        scope_keys=usage.scope_keys,
        target_scope_keys=target_scopes,
        scope_reservations=charges,
        previous_size=usage.size,
        reserved_bytes=growth,
        expected_version=usage.version,
        policy_revisions={account.key: account.policy_revision for account in accounts},
        expires_at=timezone.now() + lifetime,
    )


def _create_operation(**fields):
    try:
        with transaction.atomic():
            return StorageReservation.objects.create(**fields)
    except (IntegrityError, ValidationError):
        raise StorageWriteConflict() from None


def _locked_operation(operation_id):
    key = StorageReservation.objects.only("resource_key").get(pk=operation_id).resource_key
    usage = StorageUsage.objects.select_for_update().get(key=key)
    operation = StorageReservation.objects.select_for_update().get(pk=operation_id)
    return (
        usage,
        operation,
        lock_accounts(
            [
                *operation.scope_keys,
                *operation.target_scope_keys,
                *operation.scope_reservations,
            ]
        ),
    )


@transaction.atomic
def record_staging(operation_id, publication):
    """Journal temporary paths before IO; cancelled/expired workers cannot restart."""
    _, operation, _ = _locked_operation(operation_id)
    if operation.state not in {"reserved", "writing"} or operation.expires_at <= timezone.now():
        raise StorageWriteConflict()
    operation.state = StorageReservation.State.WRITING
    operation.publication = {**operation.publication, **publication, "cleanup_pending": True}
    operation.save(update_fields=["state", "publication", "updated_at"])
    return operation


@transaction.atomic
def extend(operation_id, *, size, window_bytes=0):
    """Admit an unknown-length stream increment before writing that increment."""
    _byte_count(size)
    _, operation, accounts = _locked_operation(operation_id)
    if operation.state not in {"reserved", "writing"} or operation.expires_at <= timezone.now():
        raise StorageWriteConflict()
    if set(operation.target_scope_keys) != set(operation.scope_keys):
        raise StorageWriteConflict("A quota transfer cannot be extended as a file upload.")
    growth = max(0, size - operation.previous_size - operation.reserved_bytes)
    if growth and window_bytes:
        available = min(
            (
                max(0, account.limit_bytes - account.used_bytes - account.reserved_bytes)
                for account in accounts
                if account.limit_bytes is not None
            ),
            default=growth + window_bytes,
        )
        growth = max(growth, min(growth + window_bytes, available))
    reserve_growth(accounts, growth)
    operation.reserved_bytes += growth
    operation.scope_reservations = {account.key: operation.reserved_bytes for account in accounts}
    operation.state = StorageReservation.State.WRITING
    operation.save(update_fields=["reserved_bytes", "scope_reservations", "state", "updated_at"])
    return operation


@transaction.atomic
def begin_publication(operation_id, *, observed_version, size, publication):
    """Fence stale operations before storage publication; persist recovery metadata."""
    _byte_count(size)
    usage, operation, _ = _locked_operation(operation_id)
    if (
        operation.state not in {"reserved", "writing"}
        or operation.expires_at <= timezone.now()
        or observed_version != operation.expected_version
        or usage.version != operation.expected_version
        or size > operation.previous_size + operation.reserved_bytes
    ):
        raise StorageWriteConflict()
    operation.state = StorageReservation.State.PUBLISHING
    operation.publication = {**publication, "size": size}
    operation.save(update_fields=["state", "publication", "updated_at"])


@transaction.atomic
def commit(operation_id, *, size, version):
    """Confirm the observed publication and release its reservation exactly once."""
    _byte_count(size)
    usage, operation, accounts = _locked_operation(operation_id)
    if operation.state == StorageReservation.State.COMMITTED:
        return
    if (
        operation.state != StorageReservation.State.PUBLISHING
        or operation.publication["size"] != size
    ):
        raise StorageWriteConflict()
    for account in accounts:
        account.used_bytes += (size if account.key in operation.target_scope_keys else 0) - (
            usage.size if account.key in usage.scope_keys else 0
        )
        account.reserved_bytes -= operation.scope_reservations.get(account.key, 0)
        if min(account.used_bytes, account.reserved_bytes) < 0:
            raise StorageWriteConflict("Storage accounting requires reconciliation.")
    StorageQuota.objects.bulk_update(accounts, ["used_bytes", "reserved_bytes"])
    usage.size = size
    usage.version = version
    if version == "missing":
        usage.native_key = None
    usage.scope_keys = operation.target_scope_keys
    target = operation.publication.get("target_attribution", {})
    if target:
        usage.attribution_conflict = False
    for field in ("owner_id", "space_id", "organization", "path"):
        if field in target:
            setattr(usage, field, target[field])
    usage.save()
    operation.state = StorageReservation.State.COMMITTED
    operation.save(update_fields=["state", "updated_at"])


@transaction.atomic
def cancel(operation_id, *, publication_ruled_out=False):
    """Release only when the caller has stopped IO and ruled out publication."""
    _, operation, accounts = _locked_operation(operation_id)
    if operation.state in {"committed", "cancelled"}:
        return
    if operation.state == "publishing" and not publication_ruled_out:
        raise StorageWriteConflict("Publication outcome must be reconciled first.")
    for account in accounts:
        account.reserved_bytes -= operation.scope_reservations.get(account.key, 0)
        if account.reserved_bytes < 0:
            raise StorageWriteConflict("Storage accounting requires reconciliation.")
    StorageQuota.objects.bulk_update(accounts, ["reserved_bytes"])
    operation.state = StorageReservation.State.CANCELLED
    operation.save(update_fields=["state", "updated_at"])
