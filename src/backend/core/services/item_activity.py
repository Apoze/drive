"""Small, validated writes to the item activity journal."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from core import models

_PAYLOAD_FIELDS = {
    models.ItemActivityActionChoices.CREATED: frozenset(),
    models.ItemActivityActionChoices.RENAMED: frozenset({"old_name", "new_name"}),
    models.ItemActivityActionChoices.DESCRIPTION_UPDATED: frozenset(),
    models.ItemActivityActionChoices.CONTENT_UPDATED: frozenset(),
    models.ItemActivityActionChoices.MOVED: frozenset(
        {
            "old_parent_id",
            "old_parent_name",
            "new_parent_id",
            "new_parent_name",
        }
    ),
    models.ItemActivityActionChoices.TRASHED: frozenset(),
    models.ItemActivityActionChoices.RESTORED: frozenset(),
    models.ItemActivityActionChoices.USER_ACCESS_CREATED: frozenset({"target_name", "role"}),
    models.ItemActivityActionChoices.USER_ACCESS_UPDATED: frozenset(
        {"target_name", "old_role", "new_role"}
    ),
    models.ItemActivityActionChoices.USER_ACCESS_REVOKED: frozenset({"target_name", "role"}),
    models.ItemActivityActionChoices.TEAM_ACCESS_CREATED: frozenset({"target_name", "role"}),
    models.ItemActivityActionChoices.TEAM_ACCESS_UPDATED: frozenset(
        {"target_name", "old_role", "new_role"}
    ),
    models.ItemActivityActionChoices.TEAM_ACCESS_REVOKED: frozenset({"target_name", "role"}),
    models.ItemActivityActionChoices.INVITATION_CREATED: frozenset({"target_name", "role"}),
    models.ItemActivityActionChoices.INVITATION_UPDATED: frozenset(
        {"target_name", "old_role", "new_role"}
    ),
    models.ItemActivityActionChoices.INVITATION_REVOKED: frozenset({"target_name", "role"}),
    models.ItemActivityActionChoices.SHARE_LINK_CREATED: frozenset({"reach", "role"}),
    models.ItemActivityActionChoices.SHARE_LINK_UPDATED: frozenset(
        {"old_reach", "old_role", "new_reach", "new_role"}
    ),
    models.ItemActivityActionChoices.SHARE_LINK_REVOKED: frozenset({"reach", "role"}),
}
_PUBLIC_LINK_ACTOR_NAME = "Visitor via link"
WOPI_CONTENT_UPDATE_WINDOW = timedelta(minutes=5)


def record_item_activity(*, item, action, actor=None, actor_name=None, payload=None):
    """Append one validated product event after its operation succeeds."""
    payload = {} if payload is None else payload
    expected_fields = _PAYLOAD_FIELDS.get(action)
    if not isinstance(payload, dict) or expected_fields is None or set(payload) != expected_fields:
        raise ValidationError(
            "Invalid item activity payload.", code="item_activity_payload_invalid"
        )

    if actor is not None and not actor.is_authenticated:
        actor = None
        actor_name = actor_name or _PUBLIC_LINK_ACTOR_NAME
    elif actor_name is None:
        if actor is None:
            raise ValidationError("An activity actor name is required.")
        actor_name = actor.full_name or actor.email or actor.admin_email or str(actor.id)

    return models.ItemActivity.objects.create(
        item=item,
        actor=actor,
        actor_name=actor_name,
        action=action,
        payload=payload,
    )


def record_wopi_content_update(*, item, actor):
    """Coalesce repeated WOPI saves by the same actor for five minutes."""
    actor_id = actor.id if actor.is_authenticated else None
    if models.ItemActivity.objects.filter(
        item=item,
        actor_id=actor_id,
        action=models.ItemActivityActionChoices.CONTENT_UPDATED,
        created_at__gte=timezone.now() - WOPI_CONTENT_UPDATE_WINDOW,
    ).exists():
        return None
    return record_item_activity(
        item=item,
        actor=actor,
        action=models.ItemActivityActionChoices.CONTENT_UPDATED,
    )
