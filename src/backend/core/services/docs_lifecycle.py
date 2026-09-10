"""Durable document metadata synchronization; network calls never hold SQL locks."""

import hashlib
import json
from contextlib import nullcontext
from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.db.models import Case, F, Max, Q, Value, When
from django.utils import timezone

from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from suite_identity.access import require_access
from suite_identity.models import Account

from core.models import (
    DocsBinding,
    DocsCommand,
    Item,
    ItemAccess,
    ItemFavorite,
    StorageMoveJob,
    StorageReservation,
    StorageUsage,
)
from core.services.docs_anchors import can_recover, current_anchor, guard_locations
from core.services.docs_resources import enabled, placement, placement_capabilities
from core.services.item_activity import record_item_activity
from core.services.storage_namespace import advisory_guard
from core.services.storage_transfer_location import resolve_location


def queue_change(item, update_fields=None):
    """Called in the Item transaction; the periodic worker recovers lost dispatches."""
    if item.type != "docs":
        return
    if update_fields is not None and not set(update_fields).intersection(
        {
            "title",
            "path",
            "deleted_at",
            "ancestors_deleted_at",
            "hard_deleted_at",
            "link_reach",
            "link_role",
        }
    ):
        return
    state = (
        "purging" if item.hard_deleted_at else "trash" if item.ancestors_deleted_at else "active"
    )
    DocsBinding.objects.filter(item=item).exclude(state="purged").update(
        revision=F("revision") + 1,
        state=Case(
            When(applied_revision=0, then=Value("pending")),
            When(creation_context__initial_content_committed=False, then=Value("preparing")),
            default=Value(state),
        )
        if state == "active"
        else state,
        retry_at=timezone.now(),
        last_error="",
    )


def queue_tree_changes(item):
    """Bulk file-folder lifecycle changes also affect the documents placed inside."""
    if not enabled():
        return
    bindings = (
        DocsBinding.objects.filter(item__path__descendants=item.path)
        .exclude(state="purged")
        .exclude(item_id=item.pk)
    )
    for state, condition in (
        ("purging", {"item__hard_deleted_at__isnull": False}),
        (
            "trash",
            {"item__hard_deleted_at__isnull": True, "item__ancestors_deleted_at__isnull": False},
        ),
        (
            "active",
            {"item__hard_deleted_at__isnull": True, "item__ancestors_deleted_at__isnull": True},
        ),
    ):
        bindings.filter(**condition).update(
            revision=F("revision") + 1,
            state=Case(
                When(applied_revision=0, then=Value("pending")),
                When(creation_context__initial_content_committed=False, then=Value("preparing")),
                default=Value(state),
            )
            if state == "active"
            else state,
            retry_at=timezone.now(),
            last_error="",
        )


def create_document(  # noqa: PLR0912, PLR0913
    user,
    *,
    title,
    request_key,
    destination,
    space_id=None,
    document_id=None,
    initial_content=None,
):
    """Reserve one stable document at an existing authorized destination."""
    if not enabled():
        raise NotFound()
    from suite_identity.document_transport import actor_context  # noqa: PLC0415

    actor = actor_context(user)
    if actor is None:
        raise PermissionDenied()
    if not isinstance(title, str) or not title.strip() or len(title) > 255:
        raise ValidationError({"title": "Choose a title of at most 255 characters."})
    body = {
        "title": title.strip(),
        "destination": str(destination),
        "space": str(space_id or ""),
        "principal": actor["principal"],
        "document": str(document_id or ""),
        "initial_content": initial_content,
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    with advisory_guard(f"docs-create:{request_key}"):
        existing = DocsBinding.objects.filter(request_key=request_key).first()
        if existing and existing.request_hash != digest:
            raise ValidationError("This creation key already belongs to another request.")
        if existing and existing.state == "purged":
            error = APIException("This creation was purged. Use a new creation key.")
            error.status_code = 409
            raise error
        parent = Item.objects.filter(pk=destination, type="docs").first()
        location = None
        if parent:
            if not parent.get_abilities(user).get("children_create"):
                raise PermissionDenied()
        else:
            location = resolve_location(destination, user, space_id=space_id, destination=True)
            parent = location.reference if isinstance(location.reference, Item) else None
            if parent is None and not current_anchor(location.reference, location.backend):
                raise ValidationError("This document location cannot be verified.")
        if existing:
            return existing
        anchor = (
            placement(parent)
            if parent and parent.type == "docs"
            else (location.reference, location.space)
            if location
            else (None, None)
        )
        with guard_locations(anchor), transaction.atomic():
            if location and parent is None:
                location.reference.refresh_from_db()
                if not current_anchor(location.reference, location.backend):
                    raise ValidationError("This document location cannot be verified.")
            if parent:
                parent = Item.objects.select_for_update().get(pk=parent.pk)
                if not parent.get_abilities(user).get("children_create"):
                    raise PermissionDenied()
            item = Item.objects.create_child(
                parent=parent, type="docs", title=title.strip(), creator=user
            )
            ItemAccess.objects.create(item=item, user=user, role="owner")
            binding = DocsBinding.objects.create(
                item=item,
                sort_order=(
                    DocsBinding.objects.filter(
                        item__path__depth=item.depth,
                        **(
                            {"item__path__descendants": parent.path}
                            if parent
                            else {
                                "mounted_parent": location.reference if location else None,
                            }
                        ),
                    ).aggregate(value=Max("sort_order"))["value"]
                    or 0
                )
                + 1,
                document_id=document_id or uuid4(),
                request_key=request_key,
                request_hash=digest,
                mounted_parent=location.reference if location and parent is None else None,
                anchor_space=location.space if location and parent is None else None,
                creation_context={
                    "principal": actor["principal"],
                    "organization": actor["organization"],
                    "initial_content": initial_content,
                    "initial_content_committed": initial_content is None,
                    "destination": str(destination),
                    "space_id": str(space_id) if space_id else None,
                    "title": title.strip(),
                },
                retry_at=timezone.now(),
            )
            from core.services.docs_quota import initialize_usage  # noqa: PLC0415

            initialize_usage(item)
            record_item_activity(item=item, actor=user, action="created")
    return binding


def synchronize(binding_id):  # noqa: PLR0911, PLR0912
    """An exact revision is acknowledged only after the peer confirms persistence."""
    if not enabled():
        return False
    from suite_identity.document_transport import send  # noqa: PLC0415

    binding = DocsBinding.objects.select_related("item").get(pk=binding_id)
    if binding.creation_context.get("migration", {}).get("phase") == "staged":
        return False
    if binding.state == "purged" or binding.applied_revision == binding.revision:
        return True
    item = binding.item
    if item is None:
        raise ValidationError("The document pointer is missing.")
    active_writes = StorageReservation.objects.filter(
        resource_key__in=StorageUsage.objects.filter(item=item).values("key"),
        state__in=["reserved", "writing", "publishing"],
    )
    if binding.creation_context.get("aborting_initial"):
        active_writes = active_writes.exclude(pk=binding.request_key)
    if binding.state == "purging" and (
        DocsBinding.objects.filter(item__path__descendants=item.path)
        .exclude(pk=binding.pk)
        .exclude(state="purged")
        .exists()
        or active_writes.exists()
    ):
        DocsBinding.objects.filter(pk=binding.pk, revision=binding.revision).update(
            retry_at=timezone.now() + timedelta(seconds=30), last_error="purge_dependencies"
        )
        return False
    parent = item.parent() if item.depth > 1 else None
    parent_binding = (
        DocsBinding.objects.filter(item=parent).first()
        if parent and parent.type == "docs"
        else None
    )
    if parent_binding and parent_binding.applied_revision == 0:
        DocsBinding.objects.filter(pk=binding.pk, revision=binding.revision).update(
            retry_at=timezone.now() + timedelta(seconds=10), last_error="parent_pending"
        )
        return False
    payload = {
        "document_id": str(binding.document_id),
        "item_id": str(item.pk),
        "revision": binding.revision,
        "sort_order": binding.sort_order,
        "title": item.title,
        "link_reach": item.link_reach or "restricted",
        "link_role": item.link_role,
        "parent_id": str(parent_binding.document_id) if parent_binding else None,
        "creator": binding.creation_context.get("principal"),
        "state": "active" if binding.state in {"pending", "preparing"} else binding.state,
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
        "ancestors_deleted_at": item.ancestors_deleted_at.isoformat()
        if item.ancestors_deleted_at
        else None,
    }
    if binding.creation_context.get("aborting_initial"):
        payload["abort_request_key"] = str(binding.request_key)
    try:
        result = send("/api/v1.0/internal/drive/apply/", payload, purpose="mutation")
        if (
            not isinstance(result, dict)
            or type(result.get("revision")) is not int
            or result.get("revision") != binding.revision
            or result.get("item_id") != str(item.pk)
            or (binding.state == "purging" and result.get("state") != "purged")
        ):
            raise APIException("Document revision was not acknowledged.")
    except APIException as error:
        DocsBinding.objects.filter(pk=binding.pk, revision=binding.revision).update(
            retry_at=timezone.now() + timedelta(seconds=30),
            last_error=f"peer_{error.status_code}",
        )
        return False
    with transaction.atomic():
        current = (
            DocsBinding.objects.select_for_update()
            .filter(pk=binding.pk, revision=binding.revision)
            .first()
        )
        if current is None:
            return False
        if binding.state == "purging":
            from core.services.storage_quota import (  # noqa: PLC0415
                guard_metadata_change,
                retire_usage,
            )

            usages = StorageUsage.objects.filter(item=item)
            guard_metadata_change(usages)
            retire_usage(usages)
        state = "purged" if binding.state == "purging" else payload["state"]
        if state == "active" and current.creation_context.get("initial_content"):
            if not StorageReservation.objects.filter(
                pk=current.request_key, state="committed"
            ).exists():
                state = "preparing"
        acknowledged = DocsBinding.objects.filter(pk=binding.pk, revision=binding.revision).update(
            applied_revision=binding.revision,
            **({"mounted_parent": None, "anchor_space": None} if state == "purged" else {}),
            state=state,
            retry_at=None,
            last_error="",
        )
        if state == "purged" and current.creation_context.get("aborting_initial"):
            StorageMoveJob.objects.filter(
                kind="docs_copy",
                copy_entries__publication__document_id=str(current.document_id),
            ).exclude(state__in=["done", "failed"]).update(
                state="failed",
                reason="An unpublished copy was cancelled. Completed documents are retained.",
                updated_at=timezone.now(),
            )
    return bool(acknowledged)


def _apply_change(item, user, data, *, destination=None):  # noqa: PLR0912
    """Mutate authorized metadata while the caller holds the item and binding locks."""
    action = data["action"]
    if action == "cancel_creation":
        binding = DocsBinding.objects.get(item=item)
        binding.creation_context["aborting_initial"] = True
        binding.save(update_fields=["creation_context", "updated_at"])
        now = timezone.now()
        # This unpublished leaf retains its reservation until Docs confirms deletion.
        # Ordinary trash/purge guards intentionally prohibit interrupting writers.
        Item.objects.filter(pk=item.pk).update(
            deleted_at=now,
            ancestors_deleted_at=now,
            hard_deleted_at=now,
            updated_at=now,
        )
        item.refresh_from_db()
        queue_change(item)
        record_item_activity(item=item, actor=user, action="trashed")
    elif action in {"move", "recover"}:
        from core.services.docs_moves import apply  # noqa: PLC0415

        apply(item, user, destination, data)
    elif action == "rename":
        if item.title == data["title"]:
            return
        old_name = item.title
        item.title = data["title"]
        item.save(update_fields=["title"])
        record_item_activity(
            item=item,
            actor=user,
            action="renamed",
            payload={"old_name": old_name, "new_name": item.title},
        )
    elif action == "trash":
        item.soft_delete()
        record_item_activity(item=item, actor=user, action="trashed")
    elif action == "favorite":
        if data["favorite"]:
            ItemFavorite.objects.get_or_create(item=item, user=user)
        else:
            ItemFavorite.objects.filter(item=item, user=user).delete()
    elif action == "link_configuration":
        old_reach, old_role = item.link_reach or "restricted", item.link_role
        fields = [field for field in ("link_reach", "link_role") if field in data]
        for field in fields:
            setattr(item, field, data[field])
        item.save(update_fields=fields)
        record_item_activity(
            item=item,
            actor=user,
            action="share_link_updated",
            payload={
                "old_reach": old_reach,
                "old_role": old_role,
                "new_reach": item.link_reach or "restricted",
                "new_role": item.link_role,
            },
        )
    elif action == "restore":
        if item.ancestors().filter(ancestors_deleted_at__isnull=False).exists():
            raise ValidationError("Restore the parent folder before this document.")
        item.restore()
        record_item_activity(item=item, actor=user, action="restored")
    elif action in {"grant_access", "update_access", "revoke_access"}:
        from core.services.docs_sharing import change_access  # noqa: PLC0415

        change_access(item, user, data)
    elif action in {"invite", "update_invitation", "revoke_invitation", "resend_invitation"}:
        from core.services.docs_invitations import change  # noqa: PLC0415

        change(item, user, data)
        queue_change(item)
    else:
        raise ValidationError("Unknown document operation.")


def _existing_command(user, data, digest):
    """Only the original actor and exact intent can retrieve a command receipt."""
    receipt = DocsCommand.objects.select_related("binding").filter(pk=data["request_key"]).first()
    if receipt is None:
        return None
    if receipt.actor_id != user.pk or receipt.request_hash != digest:
        raise PermissionDenied("This operation key belongs to another request.")
    return receipt.binding


def change_document(user, data):
    """Serialize retries by operation key without holding a SQL transaction over IO."""
    if not enabled():
        raise NotFound()
    require_access(user)
    if data["action"] == "cancel_creation" and data.get("creation_key"):
        tombstone = _cancel_unreceived_creation(user, data)
        if tombstone:
            return _receipt(tombstone)
    if data["action"] == "create" or not data.get("request_key"):
        return _change_document(user, data)
    intent = {field: value for field, value in data.items() if field != "revision"}
    digest = hashlib.sha256(json.dumps(intent, sort_keys=True, default=str).encode()).hexdigest()
    with (
        advisory_guard(f"docs-command:{data['request_key']}"),
        advisory_guard("docs-tree-placement")
        if data["action"] in {"move", "recover"}
        else nullcontext(),
    ):
        binding = _existing_command(user, data, digest)
        if binding:
            synchronize(binding.pk)
            binding.refresh_from_db()
            return _receipt(binding)
        return _change_document(user, data, digest=digest)


def _cancel_unreceived_creation(user, data):
    """Fence an absent creation against a delayed request using its original lock."""
    from suite_identity.document_transport import actor_context  # noqa: PLC0415

    actor = actor_context(user)
    if actor is None:
        raise PermissionDenied()
    with advisory_guard(f"docs-create:{data['creation_key']}"):
        binding = DocsBinding.objects.filter(request_key=data["creation_key"]).first()
        if binding:
            if (
                binding.document_id != data["document_id"]
                or binding.creation_context.get("principal") != actor["principal"]
                or binding.creation_context.get("organization") != actor["organization"]
            ):
                raise PermissionDenied()
            return binding if binding.state == "purged" else None
        if DocsBinding.objects.filter(document_id=data["document_id"]).exists():
            raise PermissionDenied()
        return DocsBinding.objects.create(
            document_id=data["document_id"],
            request_key=data["creation_key"],
            state="purged",
            revision=1,
            applied_revision=1,
            creation_context={
                "principal": actor["principal"],
                "organization": actor["organization"],
            },
        )


def _change_document(user, data, *, digest=None):
    """Apply a user command to the authority, then attempt its durable projection."""
    action = data["action"]
    if action == "create":
        binding = create_document(
            user,
            title=data["title"],
            request_key=data["request_key"],
            destination=data["destination"],
            space_id=data.get("space_id"),
            document_id=data.get("document_id"),
            initial_content=data.get("initial_content"),
        )
    else:
        binding = DocsBinding.objects.filter(document_id=data["document_id"]).first()
        if binding is None or binding.item_id is None:
            raise NotFound()
        if action not in {"cancel_creation", "recover"}:
            placement_capabilities(binding.item, user)
        destination = None
        if action in {"move", "recover"}:
            from core.services.docs_moves import prepare  # noqa: PLC0415

            destination = prepare(binding.item, user, data)
        locations = [placement(binding.item)]
        if destination:
            parent, location = destination
            locations.append(
                placement(parent)
                if parent and parent.type == "docs"
                else (location.reference, location.space)
                if location
                else (None, None)
            )
        with (
            guard_locations(*locations, allow_maintenance=action == "recover"),
            transaction.atomic(),
        ):
            item = Item.objects.select_for_update().get(pk=binding.item_id)
            binding = DocsBinding.objects.select_for_update().get(pk=binding.pk)
            ability = {
                "cancel_creation": "cancel_creation",
                "rename": "update",
                "move": "move",
                "recover": "recover",
                "trash": "destroy",
                "restore": "restore",
                "favorite": "favorite",
                "link_configuration": "link_configuration",
                "grant_access": "accesses_manage",
                "update_access": "accesses_manage",
                "revoke_access": "accesses_manage",
                "invite": "accesses_manage",
                "update_invitation": "accesses_manage",
                "revoke_invitation": "accesses_manage",
                "resend_invitation": "accesses_manage",
            }[action]
            allowed = (
                binding.state in {"pending", "preparing"}
                and item.creator_id == user.pk
                and not item.children().exists()
                if action == "cancel_creation"
                else can_recover(item, user)
                if action == "recover"
                else item.get_abilities(user).get(ability)
            )
            if not allowed:
                raise PermissionDenied()
            if (
                action != "favorite"
                and data.get("revision") is not None
                and data["revision"] != binding.revision
            ):
                error = APIException("The document changed. Refresh before retrying.")
                error.status_code = 409
                raise error
            _apply_change(item, user, data, destination=destination)
            if digest:
                binding.refresh_from_db()
                DocsCommand.objects.create(
                    id=data["request_key"],
                    binding=binding,
                    actor=user,
                    request_hash=digest,
                    revision=binding.revision,
                )
    synchronize(binding.pk)
    binding.refresh_from_db()
    return _receipt(binding)


def _receipt(binding):
    """Expose operation state without copying titles or sharing data into receipts."""
    return {
        "document_id": str(binding.document_id),
        "item_id": str(binding.item_id) if binding.item_id else None,
        "revision": binding.revision,
        "applied_revision": binding.applied_revision,
        "state": binding.state,
    }


def command_status(user, request_key):
    """The initiating user can recover status even after trashing the document."""
    if not enabled():
        raise NotFound()
    require_access(user)
    if not user.is_authenticated:
        raise PermissionDenied()
    receipt = (
        DocsCommand.objects.select_related("binding").filter(pk=request_key, actor=user).first()
    )
    creator = Q(item__creator=user)
    account = Account.objects.filter(user=user, active=True).first()
    if account:
        creator |= Q(
            creation_context__principal=str(account.principal_id),
            creation_context__organization=str(account.organization_id),
        )
    binding = (
        receipt.binding
        if receipt
        else DocsBinding.objects.filter(creator, request_key=request_key).first()
    )
    if binding is None:
        raise NotFound()
    return _receipt(binding)


def pending_creations(user, *, offset=0, limit=50):
    """Recover the caller's unpublished work without needing a browser-local key."""
    if not enabled():
        raise NotFound()
    require_access(user)
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied()
    bindings = (
        DocsBinding.objects.filter(item__creator=user)
        .filter(
            Q(state__in=["pending", "preparing"])
            | Q(state="purging", creation_context__aborting_initial=True)
        )
        .select_related("item")
        .order_by("created_at", "pk")
    )
    count = bindings.count()
    results = []
    for binding in bindings[offset : offset + limit]:
        context = binding.creation_context
        results.append(
            {
                **_receipt(binding),
                "request_key": str(binding.request_key),
                "title": context.get("title", binding.item.title),
                "destination": context.get("destination"),
                "space_id": context.get("space_id"),
                "initial_content": context.get("initial_content") is not None,
            }
        )
    return {
        "results": results,
        "count": count,
        "next_offset": offset + limit if offset + limit < count else None,
    }
