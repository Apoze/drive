"""Small, validated writes to the item activity journal."""

from django.core.exceptions import ValidationError

from core import models

_PAYLOAD_FIELDS = {
    models.ItemActivityActionChoices.CREATED: frozenset(),
    models.ItemActivityActionChoices.RENAMED: frozenset({"old_name", "new_name"}),
    models.ItemActivityActionChoices.DESCRIPTION_UPDATED: frozenset(),
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
}
_PUBLIC_LINK_ACTOR_NAME = "Visitor via link"


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
