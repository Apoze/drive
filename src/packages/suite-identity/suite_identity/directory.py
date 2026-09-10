"""Validate a complete paginated snapshot before atomically projecting its rights."""

import json
import sqlite3
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from uuid import UUID

from django.conf import settings
from django.dispatch import Signal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .http import read_credential, read_json
from .models import Account, DirectoryState, GroupMapping, IdentityBinding

# Consumers may materialize domain permissions atomically with a complete snapshot.
directory_synchronized = Signal()


class SnapshotError(Exception):
    """Safe error code only: never propagate URLs, credentials or response bodies."""


def fetch_page(parameters):
    """Fetch a scoped page without leaking the key or following redirects."""
    try:
        token = read_credential(settings.SUITE_DIRECTORY_TOKEN_FILE)
        return read_json(
            settings.SUITE_DIRECTORY_URL + "?" + urlencode(parameters),
            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
            limit=2 * 1024 * 1024,
        )
    except HTTPError as exc:
        raise SnapshotError(
            "snapshot_changed" if exc.code == 409 else "directory_http_error"
        ) from None
    except (URLError, OSError, ValueError):
        raise SnapshotError("directory_unavailable") from None


def check_page(page, *, kind, revision):
    if not isinstance(page, dict) or (
        page.get("version") != 1
        or page.get("app_id") != settings.SUITE_APP_ID
        or page.get("organization_id") != str(UUID(settings.SUITE_ORGANIZATION_ID))
        or page.get("kind") != kind
        or type(page.get("revision")) is not int
        or page["revision"] < 1
        or (revision is not None and page["revision"] != revision)
        or not isinstance(page.get("results"), list)
        or len(page["results"]) > 200
        or "next" not in page
    ):
        raise SnapshotError("invalid_snapshot")
    return page["revision"]


def read_snapshot(db, fetch):
    """Spool bounded pages on private temporary disk, not the Python heap."""
    db.execute("CREATE TABLE records (kind TEXT, id TEXT, body TEXT, PRIMARY KEY(kind,id))")
    revision = None
    for kind in ("principals", "groups", "memberships", "identities"):
        cursor = None
        while True:
            params = {"kind": kind}
            if revision is not None:
                params["revision"] = revision
            if cursor:
                params["after"] = cursor
            page = fetch(params)
            revision = check_page(page, kind=kind, revision=revision)
            previous = UUID(cursor).int if cursor else -1
            for row in page["results"]:
                try:
                    row_id = str(UUID(row["id"]))
                    if UUID(row_id).int <= previous:
                        raise ValueError
                    previous = UUID(row_id).int
                    db.execute(
                        "INSERT INTO records VALUES(?,?,?)",
                        (kind, row_id, json.dumps(row)),
                    )
                except (KeyError, ValueError, TypeError, sqlite3.IntegrityError):
                    raise SnapshotError("invalid_snapshot_order") from None
            if page["next"] is None:
                break
            if len(page["results"]) != 200 or page["next"] != row_id:
                raise SnapshotError("invalid_snapshot_cursor")
            cursor = page["next"]
    final = fetch({"kind": "revision", "revision": revision})
    check_page(final, kind="revision", revision=revision)
    return revision


def rows(db, kind):
    for (body,) in db.execute("SELECT body FROM records WHERE kind=? ORDER BY id", (kind,)):
        yield json.loads(body)


def _uuid(value):
    return UUID(value)


def project_principals(db, organization_id, revision, verified_at):
    """Preserve local users and reject regressing revocation epochs."""
    User = get_user_model()
    accounts = {
        str(a.principal_id): a for a in Account.objects.filter(organization_id=organization_id)
    }
    seen_accounts = set()
    for row in rows(db, "principals"):
        principal = _uuid(row["id"])
        if (
            type(row["active"]) is not bool
            or type(row["session_version"]) is not int
            or row["session_version"] < 0
        ):
            raise SnapshotError("invalid_principal")
        account = accounts.get(str(principal))
        is_new = account is None
        if is_new:
            if Account.objects.filter(principal_id=principal).exists():
                raise SnapshotError("organization_collision")
            if settings.SUITE_APP_ID == "people":
                user = User.objects.get(pk=principal)
            else:
                user = User(
                    sub="suite-" + str(principal),
                    **getattr(settings, "SUITE_USER_DEFAULTS", {}),
                )
                user.set_unusable_password()
                # No invitation conversion or email matching during provisioning.
                user.save()
            account = Account(user=user, principal_id=principal, organization_id=organization_id)
        if row["session_version"] < account.session_version:
            raise SnapshotError("older_session_version")
        account.active = row["active"]
        account.session_version = row["session_version"]
        auth_not_before = row.get("auth_not_before")
        parsed_epoch = parse_datetime(auth_not_before) if isinstance(auth_not_before, str) else None
        if auth_not_before is not None and (
            parsed_epoch is None or timezone.is_naive(parsed_epoch)
        ):
            raise SnapshotError("invalid_authentication_epoch")
        if account.auth_not_before and (
            parsed_epoch is None or parsed_epoch < account.auth_not_before
        ):
            raise SnapshotError("older_authentication_epoch")
        account.auth_not_before = parsed_epoch
        account.checked_at = verified_at
        account.revision = revision
        if is_new:
            account.save()
        else:
            account.save(
                update_fields=[
                    "active",
                    "session_version",
                    "auth_not_before",
                    "checked_at",
                    "revision",
                ]
            )
        accounts[str(principal)] = account
        seen_accounts.add(account.user_id)
    Account.objects.filter(organization_id=organization_id).exclude(
        user_id__in=seen_accounts
    ).update(active=False, checked_at=verified_at, revision=revision, group_ids=[])
    return accounts, seen_accounts


def project_groups(db, organization_id):
    """Map stable team UUIDs without replacing local group primary keys."""
    mappings = {
        str(g.group_id): g for g in GroupMapping.objects.filter(organization_id=organization_id)
    }
    seen_groups = set()
    for row in rows(db, "groups"):
        group_id = _uuid(row["id"])
        if not isinstance(row["name"], str) or not 1 <= len(row["name"]) <= 100:
            raise SnapshotError("invalid_group")
        mapping = mappings.get(str(group_id))
        if mapping is None:
            if GroupMapping.objects.filter(group_id=group_id).exists():
                raise SnapshotError("group_organization_collision")
            local = Group.objects.create(name="suite-" + str(group_id))
            mapping = GroupMapping(
                group_id=group_id,
                organization_id=organization_id,
                local_group=local,
            )
        mapping.display_name, mapping.active = row["name"], True
        mapping.save()
        mappings[str(group_id)] = mapping
        seen_groups.add(group_id)
    GroupMapping.objects.filter(organization_id=organization_id).exclude(
        group_id__in=seen_groups
    ).update(active=False)
    return mappings, seen_groups


def project_memberships(db, accounts, mappings, seen_accounts, seen_groups):
    """Reconcile only managed groups after validating both membership endpoints."""
    User = get_user_model()
    # Only People-managed groups are reconciled; unrelated local groups survive.
    through = User.groups.through
    through.objects.filter(group_id__in=[g.local_group_id for g in mappings.values()]).delete()
    memberships = {}
    pending = []
    for row in rows(db, "memberships"):
        account, group = (
            accounts.get(row["principal_id"]),
            mappings.get(row["group_id"]),
        )
        if (
            account is None
            or group is None
            or group.group_id not in seen_groups
            or account.user_id not in seen_accounts
        ):
            raise SnapshotError("unresolved_membership")
        if account.active:
            memberships.setdefault(account.user_id, set()).add(str(group.group_id))
            pending.append(through(user_id=account.user_id, group_id=group.local_group_id))
            if len(pending) == 200:
                through.objects.bulk_create(pending, ignore_conflicts=True)
                pending.clear()
    through.objects.bulk_create(pending, ignore_conflicts=True)
    for account in accounts.values():
        account.group_ids = sorted(memberships.get(account.user_id, []))
    Account.objects.bulk_update(accounts.values(), ["group_ids"], batch_size=200)


def project_identities(db, accounts, seen_accounts):
    """Reject reassignment of an issuer/subject to a different local user."""
    seen_identities = set()
    for row in rows(db, "identities"):
        account = accounts.get(row["principal_id"])
        if (
            account is None
            or account.user_id not in seen_accounts
            or type(row["enabled"]) is not bool
        ):
            raise SnapshotError("unresolved_identity")
        identity, _ = IdentityBinding.objects.get_or_create(
            issuer=row["issuer"],
            subject=row["subject"],
            defaults={"user_id": account.user_id},
        )
        if identity.user_id != account.user_id:
            raise SnapshotError("identity_collision")
        identity.enabled = row["enabled"]
        identity.full_clean()
        identity.save(update_fields=["enabled"])
        seen_identities.add(identity.pk)
    IdentityBinding.objects.filter(user_id__in=[a.user_id for a in accounts.values()]).exclude(
        pk__in=seen_identities
    ).update(enabled=False)


def apply_snapshot(db, revision, verified_at):
    """Collisions roll back the whole import; absence only matters after completeness."""
    organization_id = UUID(settings.SUITE_ORGANIZATION_ID)
    with transaction.atomic():
        state, _ = DirectoryState.objects.get_or_create(organization_id=organization_id)
        state = DirectoryState.objects.select_for_update().get(pk=state.pk)
        if revision < state.revision:
            raise SnapshotError("older_snapshot")
        # A worker that started earlier must never overwrite a newer verification.
        if state.checked_at and verified_at < state.checked_at:
            raise SnapshotError("older_verification")
        # ponytail: O(n) account/group metadata; spool SQL joins if directory scale requires it.
        accounts, seen_accounts = project_principals(db, organization_id, revision, verified_at)
        mappings, seen_groups = project_groups(db, organization_id)
        project_memberships(db, accounts, mappings, seen_accounts, seen_groups)
        project_identities(db, accounts, seen_accounts)
        state.revision, state.checked_at, state.last_error = revision, verified_at, ""
        state.save()
        directory_synchronized.send(sender=DirectoryState, organization_id=organization_id)


def synchronize(fetch=fetch_page):
    """Failures never renew a lease or replace a valid projection with emptiness."""
    verified_at = timezone.now()
    try:
        page = fetch({"kind": "revision"})
        revision = check_page(page, kind="revision", revision=None)
        with transaction.atomic():
            state = (
                DirectoryState.objects.select_for_update()
                .filter(organization_id=settings.SUITE_ORGANIZATION_ID)
                .first()
            )
            if state and state.revision == revision:
                if state.checked_at and verified_at < state.checked_at:
                    raise SnapshotError("older_verification")
                Account.objects.filter(organization_id=state.organization_id).update(
                    checked_at=verified_at
                )
                state.checked_at, state.last_error = verified_at, ""
                state.save(update_fields=["checked_at", "last_error"])
                directory_synchronized.send(sender=DirectoryState, organization_id=state.organization_id)
                return revision
        with tempfile.TemporaryDirectory(prefix="suite-directory-") as folder:
            with sqlite3.connect(str(Path(folder) / "snapshot.sqlite")) as db:
                revision = read_snapshot(db, fetch)
                apply_snapshot(db, revision, verified_at)
        return revision
    except SnapshotError as exc:
        DirectoryState.objects.filter(organization_id=settings.SUITE_ORGANIZATION_ID).update(
            last_error=str(exc)
        )
        raise
