"""Stage native metadata without changing Docs content or inventing principals."""

import json
from functools import lru_cache
from pathlib import Path
from uuid import UUID, uuid5

from django.conf import settings
from django.core.management.base import CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.test.utils import override_settings

from suite_identity.document_inventory import indexed_inventory, records
from suite_identity.document_inventory import write_artifact as _write_plan
from suite_identity.models import Account, GroupMapping

from core.models import Item, StorageResource, StorageSpace
from core.services.storage_resources import space_root
from core.services.storage_spaces import within

NAMESPACE = UUID("86a502a3-193a-47b4-b7eb-8573272dc589")


def document_item_id(document_id):
    """Repeat the same mapping across interrupted attempts and reviewed snapshots."""
    return uuid5(NAMESPACE, "document:" + str(UUID(str(document_id))))


def _source_user(database, native_id):
    if native_id is None:
        return None
    association = next(records(database, "account", user=native_id), None)
    if association is None or association["organization_id"] != str(settings.SUITE_ORGANIZATION_ID):
        raise CommandError("A referenced native user has no matching People principal.")
    account = (
        Account.objects.select_related("user")
        .filter(
            principal_id=association["principal_id"], organization_id=association["organization_id"]
        )
        .first()
    )
    if account is None:
        raise CommandError("A referenced People principal has no associated Drive account.")
    if "active" in association and association["active"] != account.active:
        raise CommandError("Refresh directory associations before migrating a changed account.")
    if "group_ids" in association:
        expected_groups = {_source_group(identifier) for identifier in association["group_ids"]}
        actual_groups = set(account.user.teams)
        if expected_groups != actual_groups or set(association["group_ids"]) != set(
            account.group_ids
        ):
            raise CommandError("Refresh directory memberships before migrating this account.")
    return account.user


def _source_group(native_id):
    association = GroupMapping.objects.filter(
        group_id=native_id, organization_id=settings.SUITE_ORGANIZATION_ID
    ).first()
    if association is None:
        raise CommandError("A referenced People group has no associated Drive group.")
    return f"group:{association.local_group_id}"


def _destination(user, requested):
    """Explicit common destinations; only an unambiguous owner gets a default."""
    if requested:
        space = (
            StorageSpace.objects.select_related("backend", "root_item")
            .filter(pk=requested["space_id"], enabled=True, backend__enabled=True)
            .first()
        )
        if space is None:
            raise CommandError("The migration destination is unavailable.")
        destination_id = UUID(requested["destination"])
        if space.backend.family == "s3":
            target = Item.objects.filter(
                pk=destination_id,
                type="folder",
                storage_space=space,
                ancestors_deleted_at__isnull=True,
                hard_deleted_at__isnull=True,
            ).first()
        else:
            target = StorageResource.objects.filter(
                pk=destination_id,
                namespace=space.backend.namespace,
                kind="folder",
                missing=False,
            ).first()
            if target is not None and not within(target.path, space_root(space)):
                target = None
        if target is None:
            raise CommandError("The chosen folder is not in the selected storage space.")
        return {
            "destination": str(destination_id),
            "space_id": str(space.pk),
            "parent_path": str(target.path),
            "backend_generation": space.backend.configuration_generation,
        }
    if user is None:
        raise CommandError(
            "A document with group or multiple owners needs an explicit destination."
        )
    spaces = list(
        StorageSpace.objects.select_related("root_item", "backend")
        .filter(
            owner=user,
            enabled=True,
            backend__enabled=True,
            backend__family="s3",
            root_item__isnull=False,
            root_item__ancestors_deleted_at__isnull=True,
        )
        .order_by("pk")[:2]
    )
    if len(spaces) != 1:
        raise CommandError("Choose an explicit personal destination for this document.")
    space = spaces[0]
    if not space.root_item.get_abilities(user).get("children_create"):
        raise CommandError("The owner's personal storage is not writable.")
    return {
        "destination": str(uuid5(NAMESPACE, f"folder:{space.pk}:{user.pk}")),
        "space_id": str(space.pk),
        "parent_path": str(space.root_item.path),
        "backend_generation": space.backend.configuration_generation,
        "create_folder": {
            "parent": str(space.root_item_id),
            "owner": str(user.pk),
            "title": "Documents Docs",
        },
    }


def plan(inventory, output, placements=None):
    """Resolve only durable identifiers; ambiguous or missing associations stay explicit."""
    requested = {}
    if placements:
        source = Path(placements)
        if source.stat().st_size > 1024 * 1024:
            raise CommandError("The destination choices exceed their size limit.")
        requested = json.loads(source.read_text())
        if not isinstance(requested, dict):
            raise CommandError("Destination choices must be keyed by native root UUID.")
    with indexed_inventory(inventory) as (database, checkpoint, receipt):
        if checkpoint.get("schema") not in {None, "native-docs-inventory"}:
            raise CommandError("Expected a native Docs inventory, not another migration artifact.")
        if checkpoint.get("organization") != str(settings.SUITE_ORGANIZATION_ID):
            raise CommandError("The inventory belongs to another organization.")
        source_user = lru_cache(maxsize=1024)(lambda identifier: _source_user(database, identifier))
        source_group = lru_cache(maxsize=1024)(_source_group)

        def rows():
            yield from records(database, "issue")
            for kind, fields in (
                ("document", ("creator_id",)),
                ("access", ("user_id",)),
                ("invitation", ("issuer_id",)),
                ("favorite", ("user_id",)),
                ("visit", ("user_id",)),
                ("request", ("user_id",)),
            ):
                for row in records(database, kind):
                    try:
                        for field in fields:
                            source_user(row[field])
                        if kind == "access" and row["team"]:
                            source_group(row["team"])
                    except (CommandError, ValueError) as error:
                        yield {
                            "kind": "issue",
                            "code": "unmapped_drive_association",
                            "reference": row["id"],
                            "detail": str(error),
                        }
            roots = set()
            for document in records(database, "document"):
                if document["depth"] != 1:
                    continue
                if document["id"] in requested:
                    roots.add(document["id"])
                owners = [
                    row
                    for row in records(database, "access", document=document["id"])
                    if row["role"] == "owner"
                ]
                try:
                    user = (
                        source_user(owners[0]["user_id"])
                        if len(owners) == 1 and owners[0]["user_id"]
                        else None
                    )
                    destination = _destination(user, requested.get(document["id"]))
                    yield {"kind": "migration_root", "document_id": document["id"], **destination}
                except (CommandError, KeyError, ValueError, TypeError) as error:
                    yield {
                        "kind": "issue",
                        "code": "destination_required",
                        "document_id": document["id"],
                        "detail": str(error),
                    }
            for unknown in set(requested) - roots:
                yield {"kind": "issue", "code": "unknown_root", "document_id": unknown}

        return _write_plan(
            output,
            {
                "id": checkpoint["id"],
                "organization": checkpoint["organization"],
                "inventory_sha256": receipt["sha256"],
                "frozen_inventory": checkpoint.get("coherent_checkpoint", False),
            },
            rows(),
        )


def _checked_destination(decision):
    """A reviewed folder and connection must still identify the same destination."""
    from django.db import transaction  # noqa: PLC0415

    from core.models import ItemAccess, User  # noqa: PLC0415
    from core.services.docs_anchors import current_anchor  # noqa: PLC0415

    space = StorageSpace.objects.select_related("backend", "root_item").get(pk=decision["space_id"])
    if (
        not space.enabled
        or not space.backend.enabled
        or space.backend.maintenance
        or space.backend.configuration_generation != decision["backend_generation"]
    ):
        raise CommandError("The reviewed destination connection changed or is unavailable.")
    folder = decision.get("create_folder")
    if folder:
        parent = Item.objects.get(pk=folder["parent"], type="folder", storage_space=space)
        owner = User.objects.get(pk=folder["owner"])
        if str(parent.path) != decision["parent_path"] or not parent.get_abilities(owner).get(
            "children_create"
        ):
            raise CommandError("The reviewed personal destination changed or is not writable.")
        with transaction.atomic():
            Item.objects.select_for_update().get(pk=parent.pk)
            target = Item.objects.filter(pk=decision["destination"]).first()
            if target is None:
                target = Item.objects.create_child(
                    parent=parent,
                    id=decision["destination"],
                    type="folder",
                    title=folder["title"],
                    creator=owner,
                )
                ItemAccess.objects.create(item=target, user=owner, role="owner")
            if (
                target.type != "folder"
                or target.parent().pk != parent.pk
                or target.creator_id != owner.pk
                or target.ancestors_deleted_at
            ):
                raise CommandError("The retained migration folder no longer matches its plan.")
    elif space.backend.family == "s3":
        target = Item.objects.get(
            pk=decision["destination"],
            type="folder",
            storage_space=space,
            ancestors_deleted_at__isnull=True,
            hard_deleted_at__isnull=True,
        )
        if str(target.path) != decision["parent_path"]:
            raise CommandError("The reviewed destination moved.")
    else:
        target = StorageResource.objects.get(
            pk=decision["destination"],
            namespace=space.backend.namespace,
            kind="folder",
            missing=False,
        )
        if (
            target.path != decision["parent_path"]
            or not within(target.path, space_root(space))
            or not current_anchor(target, space.backend)
        ):
            raise CommandError("The reviewed mounted destination cannot be verified.")
    return target, space


def _stage_document(database, document, checkpoint, receipt, destination, source_user, plan_digest):  # noqa: PLR0912, PLR0913, PLR0915
    """Commit one complete metadata record; retries never reset a later document."""
    from datetime import timedelta  # noqa: PLC0415

    from django.db import transaction  # noqa: PLC0415
    from django.utils.dateparse import parse_datetime  # noqa: PLC0415

    from core.models import (  # noqa: PLC0415
        DocsBinding,
        DocsInvitation,
        Invitation,
        ItemAccess,
        ItemFavorite,
        LinkTrace,
    )
    from core.services.docs_anchors import guard_locations  # noqa: PLC0415
    from core.services.docs_quota import initialize_usage  # noqa: PLC0415

    charge = next(records(database, "charge", document=document["id"]), None)
    if not charge or type(charge.get("size")) is not int or charge["size"] < 0:
        raise CommandError("A document has no verified logical-byte inventory.")
    step = checkpoint["tree_step"]
    if (
        not isinstance(document.get("path"), str)
        or type(document.get("depth")) is not int
        or document["depth"] < 1
        or len(document["path"]) != step * document["depth"]
        or any(c not in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in document["path"])
    ):
        raise CommandError("Invalid native document tree path.")
    parent_document = (
        next(records(database, "document", path=document["path"][:-step]), None)
        if document["depth"] > 1
        else None
    )
    if document["depth"] > 1 and parent_document is None:
        raise CommandError("A document has no inventoried parent.")
    target, space = destination
    parent = (
        Item.objects.get(pk=document_item_id(parent_document["id"]))
        if parent_document
        else target
        if isinstance(target, Item)
        else None
    )
    creator = source_user(document["creator_id"])
    with (
        override_settings(DOCS_DRIVE_ENABLED=True),
        guard_locations((target, space)),
        transaction.atomic(),
    ):
        binding = DocsBinding.objects.select_for_update().filter(document_id=document["id"]).first()
        if binding:
            migration = binding.creation_context.get("migration", {})
            if (
                migration.get("id") != checkpoint["id"]
                or migration.get("inventory_sha256") != receipt["sha256"]
                or migration.get("plan_sha256") != plan_digest
            ):
                raise CommandError(
                    "This document belongs to another migration or existing integration."
                )
            if migration.get("phase") != "rolled_back":
                return binding
            if binding.item_id is not None or binding.state != "purged":
                raise CommandError("The rollback journal no longer matches its pointer.")
            binding.delete()
        if parent is not None:
            Item.objects.select_for_update().get(pk=parent.pk)
        item = Item.objects.create_child(
            parent=parent,
            id=document_item_id(document["id"]),
            type="docs",
            title=document["title"],
            creator=creator,
            link_reach=document["link_reach"],
            link_role=document["link_role"],
        )
        dates = {
            field: parse_datetime(document[field]) if document[field] else None
            for field in ("created_at", "updated_at", "deleted_at", "ancestors_deleted_at")
        }
        if any(dates[field] is None for field in ("created_at", "updated_at")):
            raise CommandError("A document has invalid creation or modification dates.")
        Item.objects.filter(pk=item.pk).update(title=document["title"], **dates)
        item.refresh_from_db()
        association = (
            next(records(database, "account", user=document["creator_id"]), None)
            if creator
            else None
        )
        binding = DocsBinding.objects.create(
            item=item,
            document_id=document["id"],
            request_key=uuid5(NAMESPACE, "request:" + document["id"]),
            sort_order=int(document["path"][-step:], 36),
            state="pending",
            retry_at=None,
            mounted_parent=target if parent is None else None,
            anchor_space=space if parent is None else None,
            creation_context={
                "principal": association["principal_id"] if association else None,
                "organization": checkpoint["organization"],
                "initial_content_committed": True,
                "migration": {
                    "id": checkpoint["id"],
                    "inventory_sha256": receipt["sha256"],
                    "plan_sha256": plan_digest,
                    "phase": "staged",
                },
            },
        )
        for access in records(database, "access", document=document["id"]):
            ItemAccess.objects.create(
                id=uuid5(NAMESPACE, "access:" + access["id"]),
                item=item,
                user=source_user(access["user_id"]),
                team=_source_group(access["team"]) if access["team"] else "",
                role=access["role"],
            )
        for invitation in records(database, "invitation", document=document["id"]):
            row = Invitation.objects.create(
                id=uuid5(NAMESPACE, "invitation:" + invitation["id"]),
                item=item,
                issuer=source_user(invitation["issuer_id"]),
                email=invitation["email"],
                role=invitation["role"],
            )
            created_at = parse_datetime(invitation["created_at"])
            Invitation.objects.filter(pk=row.pk).update(created_at=created_at)
            DocsInvitation.objects.create(
                invitation=row,
                context={
                    "status": "pending",
                    "delivery": "sent",
                    "nonce": str(uuid5(NAMESPACE, "invitation-nonce:" + invitation["id"])),
                    "expires": int(
                        (
                            created_at
                            + timedelta(seconds=checkpoint["invitation_validity_seconds"])
                        ).timestamp()
                    ),
                    "legacy_native_id": invitation["id"],
                    "migration_id": checkpoint["id"],
                },
            )
        for kind, model in (("favorite", ItemFavorite), ("visit", LinkTrace)):
            for reference in records(database, kind, document=document["id"]):
                relation = model.objects.create(
                    id=uuid5(NAMESPACE, kind + ":" + reference["id"]),
                    item=item,
                    user=source_user(reference["user_id"]),
                )
                model.objects.filter(pk=relation.pk).update(
                    **{
                        field: parse_datetime(reference[field])
                        for field in ("created_at", "updated_at")
                        if field in reference
                    }
                )
        initialize_usage(item, size=charge["size"], version=charge["version"])
        # Grant signals revise documents; staging always remains hidden and
        # the native attachment will acknowledge the final imported revision.
        binding.refresh_from_db()
        binding.retry_at = None
        binding.state = "pending"
        binding.save(update_fields=["retry_at", "state"])
        return binding


def stage(inventory, migration_plan):
    """Prepare every document without switching authority or touching native content."""
    if settings.DOCS_DRIVE_ENABLED:
        raise CommandError("Stage legacy documents before enabling the Drive integration.")
    with (
        indexed_inventory(inventory) as (database, checkpoint, receipt),
        indexed_inventory(migration_plan) as (decisions, planned, planned_receipt),
    ):
        if (
            planned.get("schema") != "drive-docs-migration"
            or planned.get("inventory_sha256") != receipt["sha256"]
            or planned.get("id") != checkpoint["id"]
        ):
            raise CommandError("The migration plan does not match this inventory.")
        if (
            checkpoint.get("organization") != str(settings.SUITE_ORGANIZATION_ID)
            or not checkpoint.get("coherent_checkpoint")
            or not checkpoint.get("content_metadata")
        ):
            raise CommandError("A confirmed frozen inventory with logical byte counts is required.")
        if planned_receipt["counts"].get("issue") or receipt["counts"].get("issue"):
            raise CommandError("Resolve every inventory and destination issue before staging.")
        if type(checkpoint.get("tree_step")) is not int or not 1 <= checkpoint["tree_step"] <= 16:
            raise CommandError("Invalid native tree segment size.")
        if receipt["counts"].get("binding"):
            raise CommandError(
                "Already integrated documents require their existing migration journal."
            )
        source_user = lru_cache(maxsize=1024)(lambda identifier: _source_user(database, identifier))
        last_root, destination, count = None, None, 0
        for record in database.execute(
            "SELECT data FROM records WHERE kind = 'document' ORDER BY path"
        ):
            document = json.loads(record["data"])
            root_path = document["path"][: checkpoint["tree_step"]]
            if root_path != last_root:
                root = next(records(database, "document", path=root_path), None)
                decision = (
                    next(records(decisions, "migration_root", document=root["id"]), None)
                    if root
                    else None
                )
                if decision is None:
                    raise CommandError("A document root has no reviewed destination.")
                destination = _checked_destination(decision)
                last_root = root_path
            _stage_document(
                database,
                document,
                checkpoint,
                receipt,
                destination,
                source_user,
                planned_receipt["sha256"],
            )
            count += 1
        return count


def _legacy_grants(database, document, step):
    from core.services.docs_resources import highest_role  # noqa: PLC0415

    grants, links = {}, []
    for length in range(step, len(document["path"]) + 1, step):
        ancestor = next(records(database, "document", path=document["path"][:length]))
        if not ancestor["ancestors_deleted_at"]:
            links.append(ancestor)
        for row in records(database, "access", document=ancestor["id"]):
            key = (
                ("user", str(_source_user(database, row["user_id"]).pk))
                if row["user_id"]
                else ("group", _source_group(row["team"]))
            )
            grants[key] = highest_role((grants.get(key), row["role"]))
    return grants, links


def _compare_document(database, document, binding, step):
    """Compare symbolic grants and actual placement caps without publishing staged rows."""
    from copy import copy  # noqa: PLC0415

    from django.contrib.auth.models import AnonymousUser  # noqa: PLC0415

    from core.models import ItemAccess, User  # noqa: PLC0415
    from core.services.docs_resources import document_abilities, highest_role  # noqa: PLC0415

    grants, links = _legacy_grants(database, document, step)
    actual = {}
    for access in ItemAccess.objects.filter(item__path__ancestors=binding.item.path):
        key = ("user", str(access.user_id)) if access.user_id else ("group", access.team)
        actual[key] = highest_role((actual.get(key), access.role))
    if actual != grants:
        raise CommandError("The destination changes inherited user or group roles.")
    projected = copy(binding.item)
    projected.docs_binding = copy(binding)
    projected.docs_binding.state = "trash" if document["ancestors_deleted_at"] else "active"
    reaches = {"restricted": 0, "authenticated": 1, "public": 2}
    reach = max((row["link_reach"] for row in links), key=reaches.get, default="restricted")
    link_role = highest_role(row["link_role"] for row in links if row["link_reach"] == reach)

    def actors():
        yield AnonymousUser()
        yield from User.objects.filter(is_active=True).iterator(chunk_size=100)

    with override_settings(DOCS_DRIVE_ENABLED=True, SUITE_IDENTITY_ENABLED=False):
        for user in actors():
            role = (
                highest_role(
                    (
                        grants.get(("user", str(user.pk))),
                        *(grants.get(("group", team)) for team in user.teams),
                    )
                )
                if user.is_authenticated
                else None
            )
            effective = highest_role(
                (
                    role,
                    link_role
                    if reach == "public" or (reach == "authenticated" and user.is_authenticated)
                    else None,
                )
            )
            readable = bool(effective) and not document["ancestors_deleted_at"]
            expected = {
                "retrieve": bool(readable or role == "owner"),
                "update": bool(readable and effective in {"editor", "administrator", "owner"}),
                "comment": bool(readable and effective != "reader"),
                "accesses_manage": bool(
                    not document["ancestors_deleted_at"] and role in {"administrator", "owner"}
                ),
                "restore": bool(role == "owner" and document["deleted_at"]),
            }
            observed = document_abilities(projected, user)
            if any(bool(observed.get(key)) != value for key, value in expected.items()):
                raise CommandError("The selected placement changes effective document permissions.")


def compare(inventory, migration_plan, output):
    """Produce the exact, private attachment manifest only after every check passes."""
    from core.models import DocsBinding, StorageUsage  # noqa: PLC0415

    with (
        indexed_inventory(inventory) as (database, checkpoint, receipt),
        indexed_inventory(migration_plan) as (_decisions, planned, planned_receipt),
    ):
        if (
            planned.get("inventory_sha256") != receipt["sha256"]
            or planned.get("id") != checkpoint["id"]
        ):
            raise CommandError("The migration plan does not match this inventory.")

        def rows():
            for document in records(database, "document"):
                binding = DocsBinding.objects.select_related("item").get(document_id=document["id"])
                journal = binding.creation_context.get("migration", {})
                if (
                    journal.get("phase") not in {"staged", "active"}
                    or journal.get("inventory_sha256") != receipt["sha256"]
                    or journal.get("plan_sha256") != planned_receipt["sha256"]
                ):
                    raise CommandError("A document is not staged from this reviewed plan.")
                for field in (
                    "title",
                    "link_reach",
                    "link_role",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                    "ancestors_deleted_at",
                ):
                    current = json.loads(
                        json.dumps(getattr(binding.item, field), cls=DjangoJSONEncoder)
                    )
                    if current != document[field]:
                        raise CommandError("Staged document metadata changed after preparation.")
                charge = next(records(database, "charge", document=document["id"]))
                usage = StorageUsage.objects.get(item=binding.item)
                if (
                    usage.size != charge["size"]
                    or usage.version != charge["version"]
                    or usage.attribution_conflict
                ):
                    raise CommandError("Document quota accounting does not match the inventory.")
                _compare_document(database, document, binding, checkpoint["tree_step"])
                yield {
                    "kind": "attachment",
                    "document_id": document["id"],
                    "drive_item_id": str(binding.item_id),
                    "revision": binding.revision,
                    "sort_order": binding.sort_order,
                    "state": "trash" if document["ancestors_deleted_at"] else "active",
                }

        return _write_plan(
            output,
            {
                "schema": "drive-docs-attachment",
                "id": checkpoint["id"],
                "organization": checkpoint["organization"],
                "inventory_sha256": receipt["sha256"],
                "plan_sha256": planned_receipt["sha256"],
            },
            rows(),
        )


def finalize(inventory, migration_plan, attachment, native_receipt, output, *, rollback=False):  # noqa: PLR0913, PLR0915
    """Confirm both journals before activating pointers, or remove only imported metadata."""
    from tempfile import TemporaryDirectory  # noqa: PLC0415

    from django.db import transaction  # noqa: PLC0415

    from core.models import DocsBinding  # noqa: PLC0415
    from core.services.storage_namespace import advisory_guard  # noqa: PLC0415

    if settings.DOCS_DRIVE_ENABLED:
        raise CommandError("Suspend the integrated environment before migration finalization.")
    with (
        advisory_guard("docs-tree-placement"),
        indexed_inventory(attachment) as (manifest, prepared, receipt),
        indexed_inventory(native_receipt) as (confirmed, native, native_digest),
    ):
        if (
            native.get("schema") != ("native-docs-detached" if rollback else "native-docs-attached")
            or native.get("attachment_sha256") != receipt["sha256"]
            or any(
                native.get(key) != prepared.get(key)
                for key in ("id", "organization", "inventory_sha256", "plan_sha256")
            )
            or native_digest["counts"] != receipt["counts"]
        ):
            raise CommandError("Native completion does not match the reviewed attachment.")
        for row in records(manifest, "attachment"):
            if next(records(confirmed, "attachment", document=row["document_id"]), None) != row:
                raise CommandError("Native and Drive attachment records differ.")
        completed_rollback = (
            rollback
            and not DocsBinding.objects.filter(creation_context__migration__id=prepared["id"])
            .exclude(creation_context__migration__phase="rolled_back")
            .exists()
        )
        if completed_rollback:
            for row in records(manifest, "attachment"):
                retained = DocsBinding.objects.filter(
                    document_id=row["document_id"],
                    state="purged",
                    item__isnull=True,
                    revision=row["revision"],
                    creation_context__migration__plan_sha256=prepared["plan_sha256"],
                    creation_context__migration__inventory_sha256=prepared["inventory_sha256"],
                    creation_context__migration__previous_item_id=row["drive_item_id"],
                ).exists()
                if not retained or Item.objects.filter(pk=row["drive_item_id"]).exists():
                    raise CommandError("The rollback journal no longer matches its receipt.")
        else:
            with TemporaryDirectory(prefix="docs-migration-compare-") as directory:
                current = Path(directory) / "comparison.jsonl"
                compare(inventory, migration_plan, current)
                with indexed_inventory(current) as (_db, _checkpoint, current_receipt):
                    if current_receipt["sha256"] != receipt["sha256"]:
                        raise CommandError("Drive metadata changed after permission comparison.")

        def rows():
            if completed_rollback:
                yield from records(manifest, "attachment")
                return
            with transaction.atomic():
                # A single SQL transaction gives rollback an all-or-nothing boundary;
                # content remains untouched and all network comparisons precede it.
                bindings = (
                    DocsBinding.objects.select_for_update(of=("self",))
                    .select_related("item")
                    .filter(creation_context__migration__id=prepared["id"])
                    .order_by("-item__path")
                )
                count = 0
                for binding in bindings.iterator(chunk_size=100):
                    Item.objects.select_for_update().get(pk=binding.item_id)
                    row = next(records(manifest, "attachment", document=binding.document_id), None)
                    if (
                        row is None
                        or binding.revision != row["revision"]
                        or str(binding.item_id) != row["drive_item_id"]
                    ):
                        raise CommandError("An imported document changed during finalization.")
                    if rollback:
                        _rollback_binding(binding)
                    else:
                        binding.creation_context["migration"]["phase"] = "active"
                        binding.applied_revision = binding.revision
                        binding.state = row["state"]
                        binding.retry_at = None
                        binding.save(
                            update_fields=[
                                "creation_context",
                                "applied_revision",
                                "state",
                                "retry_at",
                            ]
                        )
                    count += 1
                    yield row
                if count != receipt["counts"].get("attachment", 0):
                    raise CommandError("The imported document count changed.")
                if rollback:
                    with indexed_inventory(migration_plan) as (destinations, _head, _receipt):
                        for decision in records(destinations, "migration_root"):
                            folder = decision.get("create_folder")
                            if folder:
                                item = Item.objects.filter(
                                    pk=decision["destination"],
                                    creator_id=folder["owner"],
                                    type="folder",
                                ).first()
                                if (
                                    item
                                    and not Item.objects.filter(path__descendants=item.path)
                                    .exclude(pk=item.pk)
                                    .exists()
                                ):
                                    Item.objects.filter(pk=item.pk).delete()

        return _write_plan(
            output,
            {**prepared, "schema": "drive-docs-rolled-back" if rollback else "drive-docs-active"},
            rows(),
        )


def _rollback_binding(binding):
    """Keep an audit tombstone after retiring only the imported pointer's charge."""
    from core.models import StorageUsage  # noqa: PLC0415
    from core.services.storage_quota import guard_metadata_change, observe_usage  # noqa: PLC0415

    usage = StorageUsage.objects.select_for_update().get(item=binding.item)
    guard_metadata_change(StorageUsage.objects.filter(pk=usage.pk))
    observe_usage(key=usage.key, size=0, scope_keys=usage.scope_keys)
    usage.delete()
    item = binding.item
    binding.creation_context["migration"].update(phase="rolled_back", previous_item_id=str(item.pk))
    binding.item = None
    binding.state = "purged"
    binding.mounted_parent = None
    binding.anchor_space = None
    binding.save(
        update_fields=["creation_context", "item", "state", "mounted_parent", "anchor_space"]
    )
    Item.objects.filter(pk=item.pk).delete()


def discard(inventory, migration_plan, native_receipt, output):
    """A failed comparison can be undone before any native attachment or activation."""
    from django.db import transaction  # noqa: PLC0415

    from core.models import DocsBinding  # noqa: PLC0415
    from core.services.storage_namespace import advisory_guard  # noqa: PLC0415

    if settings.DOCS_DRIVE_ENABLED:
        raise CommandError("Suspend document integration before discarding a stage.")
    with (
        advisory_guard("docs-tree-placement"),
        indexed_inventory(inventory) as (_db, checkpoint, receipt),
        indexed_inventory(migration_plan) as (destinations, planned, plan_receipt),
        indexed_inventory(native_receipt) as (_native_db, native, _native_receipt),
    ):
        if native.get("schema") != "native-docs-unbound" or any(
            row.get("inventory_sha256") != receipt["sha256"]
            or row.get("id") != checkpoint["id"]
            or row.get("organization") != str(settings.SUITE_ORGANIZATION_ID)
            for row in (native, planned)
        ):
            raise CommandError("The unbound receipt and plan must match the frozen inventory.")

        def rows():
            bindings = (
                DocsBinding.objects.select_for_update(of=("self",))
                .select_related("item")
                .filter(creation_context__migration__id=checkpoint["id"])
                .order_by("-item__path")
            )
            for binding in bindings.iterator(chunk_size=100):
                journal = binding.creation_context["migration"]
                if (
                    journal.get("plan_sha256") != plan_receipt["sha256"]
                    or journal.get("inventory_sha256") != receipt["sha256"]
                    or journal.get("phase") not in {"staged", "rolled_back"}
                    or binding.applied_revision
                ):
                    raise CommandError(
                        "An imported document was activated or belongs to another plan."
                    )
                if binding.item_id:
                    Item.objects.select_for_update().get(pk=binding.item_id)
                    _rollback_binding(binding)
                yield {"kind": "discarded", "document_id": str(binding.document_id)}
            for decision in records(destinations, "migration_root"):
                folder = decision.get("create_folder")
                if folder:
                    item = Item.objects.filter(
                        pk=decision["destination"], creator_id=folder["owner"], type="folder"
                    ).first()
                    if (
                        item
                        and not Item.objects.filter(path__descendants=item.path)
                        .exclude(pk=item.pk)
                        .exists()
                    ):
                        Item.objects.filter(pk=item.pk).delete()

        with transaction.atomic():
            return _write_plan(
                output,
                {
                    "schema": "drive-docs-discarded",
                    "id": checkpoint["id"],
                    "inventory_sha256": receipt["sha256"],
                    "plan_sha256": plan_receipt["sha256"],
                    "organization": checkpoint["organization"],
                },
                rows(),
            )
