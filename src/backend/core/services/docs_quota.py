"""Charge native document bytes to existing logical budgets, never NAS capacity."""

from copy import copy

from django.db import transaction
from django.utils import timezone

from rest_framework.exceptions import NotFound, PermissionDenied

from core.models import DocsBinding, Item, StorageReservation, StorageSpace, StorageUsage
from core.services import storage_quota as quota
from core.services.docs_resources import enabled, placement, placement_capabilities
from core.services.storage_inventory import item_attribution, refresh_policy
from core.services.storage_spaces import namespace_path, within


def attribution(item, *, placement_override=None):
    """Derive the initial owner from placement, independently of the last editor."""
    parent, space = placement_override or placement(item)
    projected = copy(item)
    projected.storage_space = space
    projected.storage_backend = (
        space.backend if space else (parent.storage_backend if isinstance(parent, Item) else None)
    )
    if space and space.backend.family == "mount":
        owner = item.creator if space.attribute_to_creator else space.owner
        scopes = [
            "instance:drive",
            f"organization:{space.backend.organization}",
        ]
        scopes.extend(
            f"space:{ancestor.pk}"
            for ancestor in StorageSpace.objects.filter(
                backend__namespace=space.backend.namespace,
                backend__organization=space.backend.organization,
            ).select_related("backend")
            if within(parent.path, namespace_path(ancestor.backend, ancestor.root_path))
        )
        if owner:
            scopes.append(f"user:{owner.pk}")
        result = {
            "owner": owner,
            "organization": space.backend.organization,
            "space": space,
            "scope_keys": scopes,
        }
    else:
        result = item_attribution(projected)
    result["backend"] = None
    result["scope_keys"] = [
        key for key in result["scope_keys"] if not key.startswith(("backend:", "user-backend:"))
    ]
    return result


@transaction.atomic
def initialize_usage(item, *, size=0, version=""):
    """Create the stable charge once; retries must not reset previously saved bytes."""
    if item.type != "docs":
        raise quota.StorageWriteConflict("Expected a native document.")
    item = Item.objects.select_for_update().get(pk=item.pk)
    existing = StorageUsage.objects.filter(item=item).first()
    if existing:
        return existing
    return quota.observe_usage(
        key=quota.resource_key(f"docs:{item.docs_binding.document_id}"),
        item=item,
        size=size,
        version=version,
        **attribution(item),
    )


def _authorize_write(item, user, operation_id, size, digest=None):
    """Only the original creator may finish the exact, still-hidden initial body."""
    binding = DocsBinding.objects.get(item=item)
    if binding.state in {"pending", "preparing"}:
        from suite_identity.access import require_access  # noqa: PLC0415

        initial = binding.creation_context.get("initial_content")
        if (
            not initial
            or not user.is_authenticated
            or not user.is_active
            or item.creator_id != user.pk
            or binding.request_key != operation_id
            or initial["size"] != size
            or (digest is not None and initial["digest"] != digest)
            or item.ancestors_deleted_at
            or item.hard_deleted_at
            or not item.accesses.filter(user=user, role="owner").exists()
        ):
            raise PermissionDenied()
        require_access(user)
        if not placement_capabilities(item, user).get("update"):
            raise PermissionDenied()
    elif not item.get_abilities(user).get("update"):
        raise PermissionDenied()


def reserve(user, *, document_id, operation_id, size):
    """Reserve serialized content plus unique attachments before any durable write."""
    if not enabled():
        raise NotFound()
    binding = DocsBinding.objects.select_related("item").filter(document_id=document_id).first()
    if not binding or not binding.item:
        raise PermissionDenied()
    _authorize_write(binding.item, user, operation_id, size)
    usage = StorageUsage.objects.select_related("owner").filter(item=binding.item).first()
    if usage is None:
        raise quota.StorageWriteConflict("Document accounting must be initialized first.")
    if usage.owner:
        refresh_policy(usage.owner, organization=usage.organization)
    with transaction.atomic():
        item = Item.objects.select_for_update().get(pk=binding.item_id)
        _authorize_write(item, user, operation_id, size)
        previous = StorageReservation.objects.filter(pk=operation_id).first()
        if previous and previous.state == "publishing":
            if (
                previous.actor_id != (user.pk if user.is_authenticated else None)
                or previous.resource_key != usage.key
                or previous.publication.get("kind") != "docs"
                or previous.publication.get("size") != size
            ):
                raise quota.StorageWriteConflict()
            return previous
        operation = quota.admit(
            key=usage.key,
            actor=user if user.is_authenticated else None,
            size=size,
            operation_id=operation_id,
        )
        if operation.state == "reserved" and not operation.publication:
            operation = quota.record_staging(
                operation.pk,
                {"kind": "docs", "document_id": str(document_id)},
            )
        initial = binding.creation_context.get("initial_content")
        if initial and operation_id == binding.request_key and operation.state == "writing":
            # The initial body may be durably staged immediately after this response.
            # Fence it in the same transaction, so expiry cannot release its budget.
            quota.begin_publication(
                operation.pk,
                observed_version=operation.expected_version,
                size=size,
                publication={**operation.publication, "digest": initial["digest"]},
            )
            operation.refresh_from_db()
        return operation


def transition(user, data):  # noqa: PLR0912
    """Fence publication before IO; acknowledge only this document's reservation."""
    if not enabled():
        raise NotFound()
    if data["action"] == "reduce":
        return reduce_usage(user, data)
    if data["action"] == "reserve":
        operation = reserve(
            user,
            document_id=data["document_id"],
            operation_id=data["operation_id"],
            size=data["size"],
        )
    else:
        operation = StorageReservation.objects.filter(pk=data["operation_id"]).first()
        if (
            operation is None
            and data["action"] == "cancel"
            and data.get("unpublished")
            and not user.is_authenticated
            and data.get("version") == ""
            and DocsBinding.objects.filter(
                document_id=data["document_id"],
                request_key=data["operation_id"],
                creation_context__aborting_initial=True,
            ).exists()
        ):
            return {
                "operation_id": str(data["operation_id"]),
                "state": "cancelled",
                "previous_size": 0,
                "reserved_bytes": 0,
                "expected_version": "",
            }
        usage = (
            StorageUsage.objects.select_related("item")
            .filter(
                key=operation.resource_key if operation else None,
                item__docs_binding__document_id=data["document_id"],
            )
            .first()
        )
        if operation is None or usage is None or operation.publication.get("kind") != "docs":
            raise NotFound()
        if user.is_authenticated and operation.actor_id != user.pk:
            raise PermissionDenied()
        if data["action"] == "begin":
            # Without a principal, only an explicit public editing link can authorize IO.
            _authorize_write(usage.item, user, operation.pk, data["size"], data["digest"])
            if operation.state in {"publishing", "committed"}:
                if (
                    operation.expected_version != data["version"]
                    or operation.publication.get("size") != data["size"]
                    or operation.publication.get("digest") != data["digest"]
                ):
                    raise quota.StorageWriteConflict("Document publication does not match.")
            else:
                quota.begin_publication(
                    operation.pk,
                    observed_version=data["version"],
                    size=data["size"],
                    publication={
                        **operation.publication,
                        "digest": data["digest"],
                    },
                )
        elif data["action"] == "commit":
            # The private Docs mutation credential confirms a durable native write.
            # This remains possible after user revocation, without authorizing new IO.
            if operation.publication.get("digest") != data["digest"]:
                raise quota.StorageWriteConflict("Document publication does not match.")
            with transaction.atomic():
                Item.objects.select_for_update().get(pk=usage.item_id)
                operation.refresh_from_db()
                committed = operation.state == "committed"
                quota.commit(operation.pk, size=data["size"], version=data["version"])
                if not committed:
                    Item.objects.filter(pk=usage.item_id).update(
                        size=data["size"],
                        updated_at=timezone.now(),
                    )
                binding = (
                    DocsBinding.objects.select_for_update()
                    .filter(
                        item=usage.item,
                        request_key=operation.pk,
                    )
                    .first()
                )
                if binding and binding.creation_context.get("initial_content"):
                    binding.creation_context["initial_content_committed"] = True
                    if (
                        binding.state == "preparing"
                        and binding.applied_revision == binding.revision
                    ):
                        binding.state = "active"
                    binding.save(update_fields=["creation_context", "state", "updated_at"])
        elif data["action"] == "cancel":
            # A lost response is not evidence that no content was published.
            unpublished = data.get("unpublished", False)
            if unpublished and (
                user.is_authenticated or data.get("version") != operation.expected_version
            ):
                raise PermissionDenied()
            quota.cancel(operation.pk, publication_ruled_out=unpublished)
        else:
            raise quota.StorageWriteConflict("Unknown document accounting operation.")
        operation.refresh_from_db()
    return {
        "operation_id": str(operation.pk),
        "state": operation.state,
        "previous_size": operation.previous_size,
        "reserved_bytes": operation.reserved_bytes,
        "expected_version": operation.expected_version,
    }


@transaction.atomic
def reduce_usage(user, data):
    """The trusted peer may reduce confirmed bytes, never bypass admission for growth."""
    if user.is_authenticated:
        raise PermissionDenied()
    item = (
        Item.objects.select_for_update()
        .filter(docs_binding__document_id=data["document_id"])
        .first()
    )
    if item is None:
        raise NotFound()
    usage = (
        StorageUsage.objects.select_for_update()
        .filter(item__docs_binding__document_id=data["document_id"])
        .first()
    )
    if usage is None:
        raise NotFound()
    if (
        usage.version != data["version"]
        or data["size"] > usage.size
        or StorageReservation.objects.filter(
            resource_key=usage.key, state__in=["reserved", "writing", "publishing"]
        ).exists()
    ):
        raise quota.StorageWriteConflict("Document accounting is awaiting a publication.")
    quota.observe_usage(
        key=usage.key, size=data["size"], scope_keys=usage.scope_keys, version=usage.version
    )
    Item.objects.filter(pk=item.pk).update(size=data["size"])
    return {"document_id": str(data["document_id"]), "size": data["size"], "version": usage.version}
