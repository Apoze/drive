"""Document grants use Drive access rows and stable suite directory identities."""

from django.conf import settings
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db.models import CharField, Q, Value
from django.db.models.functions import Cast, Concat

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from suite_identity.access import require_access
from suite_identity.models import Account, GroupMapping

from core.models import DocsBinding, ItemAccess, User
from core.services.docs_resources import enabled
from core.services.item_activity import record_item_activity


def change_access(item, actor, data):
    """Called under the document lock; inherited grants are changed at their source."""
    if not item.get_abilities(actor).get("accesses_manage"):
        raise PermissionDenied()
    action = data["action"]
    if action == "grant_access":
        target = _target(data)
        role = data["role"]
        if role == "owner" and item.get_role(actor) != "owner":
            raise PermissionDenied("Only an owner can assign another owner.")
        inherited = ItemAccess.objects.filter(
            item__path__ancestors=item.path, **target
        ).values_list("role", flat=True)
        if item.access_role_choices.get_priority(
            item.access_role_choices.max(*inherited)
        ) >= item.access_role_choices.get_priority(role):
            # An access request may be approved after another manager already
            # granted access. Acknowledge it without lowering or duplicating rights.
            return None
        old_role = (
            ItemAccess.objects.filter(item=item, **target).values_list("role", flat=True).first()
        )
        access, created = ItemAccess.objects.update_or_create(
            item=item, **target, defaults={"role": role}
        )
        _record(access, actor, "created" if created else "updated", old_role=old_role)
        return access
    access = ItemAccess.objects.select_for_update().filter(pk=data["access_id"], item=item).first()
    if access is None:
        raise NotFound()
    caps = access.get_abilities(actor)
    if action == "revoke_access":
        if not caps["destroy"]:
            raise PermissionDenied()
        access.delete()
        _record(access, actor, "revoked")
        return None
    if action != "update_access" or data["role"] not in caps["set_role_to"]:
        raise PermissionDenied()
    old_role = access.role
    access.role = data["role"]
    access.save(update_fields=["role"])
    if old_role != access.role:
        _record(access, actor, "updated", old_role=old_role)
    return access


def _record(access, actor, event, *, old_role=None):
    target = (
        (access.user.full_name or access.user.email or str(access.user_id))
        if access.user_id
        else access.team
    )
    record_item_activity(
        item=access.item,
        actor=actor,
        action=f"{'user' if access.user_id else 'team'}_access_{event}",
        payload={
            "target_name": target,
            **(
                {"old_role": old_role, "new_role": access.role}
                if event == "updated"
                else {"role": access.role}
            ),
        },
    )


def _target(data):
    if data.get("principal_id"):
        account = Account.objects.filter(
            principal_id=data["principal_id"],
            organization_id=settings.SUITE_ORGANIZATION_ID,
            active=True,
            user__is_active=True,
        ).first()
        if account is None:
            raise ValidationError("The person is not associated with this organization.")
        return {"user_id": account.user_id, "team": ""}
    group = GroupMapping.objects.filter(
        pk=data["group_id"],
        organization_id=settings.SUITE_ORGANIZATION_ID,
        active=True,
    ).first()
    if group is None:
        raise ValidationError("The group is unavailable for sharing.")
    return {"user_id": None, "team": f"group:{group.local_group_id}"}


def access_queryset(item, actor):
    """Filter before pagination, preserving the existing restricted sharing view."""
    if not item.get_abilities(actor).get("accesses_view"):
        raise PermissionDenied()
    queryset = ItemAccess.objects.filter(
        item__path__ancestors=item.path,
        item__ancestors_deleted_at__isnull=True,
    )
    if item.get_role(actor) not in {"owner", "administrator"}:
        queryset = queryset.filter(Q(role__in=["owner", "administrator"]) | Q(user=actor))
    return queryset.select_related("item__docs_binding", "user__suite_account")


def access_page(item, actor, *, offset, limit, access_id=None, principal_id=None, group_id=None):  # noqa: PLR0913
    """A bounded identity-aware page; inherited file-folder grants stay read-only."""
    queryset = access_queryset(item, actor)
    if access_id:
        queryset = queryset.filter(pk=access_id)
    if principal_id or group_id:
        queryset = queryset.filter(**_target({"principal_id": principal_id, "group_id": group_id}))
    count = queryset.count()
    accesses = list(queryset.order_by("item__path", "created_at", "pk")[offset : offset + limit])
    group_refs = {
        access.team.removeprefix("group:")
        for access in accesses
        if access.team.startswith("group:")
    }
    groups = {
        str(group.local_group_id): group
        for group in GroupMapping.objects.filter(
            local_group_id__in=[value for value in group_refs if value.isdigit()],
            organization_id=settings.SUITE_ORGANIZATION_ID,
        )
    }
    privileged = item.get_role(actor) in {"owner", "administrator"}
    results = []
    for access in accesses:
        inherited = access.item_id != item.pk
        source_visible = not inherited or access.item.get_abilities(actor).get("retrieve")
        caps = access.get_abilities(actor)
        if inherited:
            caps.update(update=False, partial_update=False, destroy=False, set_role_to=[])
        try:
            document_id = str(access.item.docs_binding.document_id)
        except DocsBinding.DoesNotExist:
            document_id = None
        user = None
        if access.user_id:
            try:
                principal_id = str(access.user.suite_account.principal_id)
            except Account.DoesNotExist:
                principal_id = None
            user = {
                "principal_id": principal_id,
                "full_name": access.user.full_name,
                "short_name": access.user.short_name,
            }
            if privileged:
                user["email"] = access.user.email
        group = groups.get(access.team.removeprefix("group:"))
        results.append(
            {
                "id": str(access.pk),
                "role": access.role,
                "inherited": inherited,
                "resource": {
                    "item_id": str(access.item_id) if source_visible else None,
                    "document_id": document_id if source_visible else None,
                    "title": access.item.title if source_visible else None,
                },
                "user": user,
                "group_id": str(group.pk) if group else None,
                "group_name": group.display_name if group else access.team or None,
                "abilities": caps,
            }
        )
    return {"count": count, "results": results}


def notification_recipients(document_id, requester_principal, *, offset=0, limit=50):
    """Private worker read: current managers only, including inherited group grants."""
    if not enabled():
        raise NotFound()
    binding = (
        DocsBinding.objects.select_related("item")
        .filter(
            document_id=document_id,
            state="active",
            item__ancestors_deleted_at__isnull=True,
            item__hard_deleted_at__isnull=True,
        )
        .first()
    )
    if binding is None or binding.item is None:
        return {"results": [], "next_offset": None}
    requester = (
        Account.objects.select_related("user")
        .filter(
            principal_id=requester_principal,
            organization_id=settings.SUITE_ORGANIZATION_ID,
            active=True,
            user__is_active=True,
        )
        .first()
    )
    if requester is None:
        return {"results": [], "next_offset": None}
    require_access(requester.user)
    item = binding.item
    grants = ItemAccess.objects.filter(
        item__path__ancestors=item.path, role__in=["owner", "administrator"]
    )
    groups = (
        GroupMapping.objects.filter(
            active=True,
            organization_id=settings.SUITE_ORGANIZATION_ID,
        )
        .annotate(reference=Concat(Value("group:"), Cast("local_group_id", CharField())))
        .filter(
            reference__in=grants.values("team"),
        )
        .values("local_group_id")
    )
    candidates = (
        User.objects.filter(
            Q(pk__in=grants.values("user_id")) | Q(groups__in=groups),
            is_active=True,
            suite_account__active=True,
            suite_account__organization_id=settings.SUITE_ORGANIZATION_ID,
        )
        .exclude(Q(email="") | Q(email__isnull=True))
        .distinct()
        .order_by("pk")
    )
    users = list(candidates[offset : offset + limit + 1])
    results = []
    for user in users[:limit]:
        try:
            require_access(user)
            if item.get_abilities(user).get("accesses_manage"):
                results.append({"email": user.email, "language": user.language})
        except (PermissionDenied, DjangoPermissionDenied) as error:
            if getattr(error, "status_code", None) == 503:
                raise
    return {
        "results": results,
        "title": item.title,
        "next_offset": offset + limit if len(users) > limit else None,
    }
