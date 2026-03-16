"""E2E utils."""

from __future__ import annotations

from collections.abc import Iterable

from django.db.models import Q

from lasuite.drf.models.choices import LinkReachChoices

from core import models

from e2e.services.namespaces import (
    SessionNamespace,
    run_scope_slug,
    worker_scope_slug,
)

DEFAULT_E2E_LANGUAGE = "en-us"


def _default_full_name(email: str) -> str:
    local_part = (email or "").split("@", maxsplit=1)[0].replace(".", " ").strip()
    if not local_part:
        return "E2E User"
    return f"E2E {local_part.title()}"


def _default_short_name(email: str) -> str:
    local_part = (email or "").split("@", maxsplit=1)[0].strip()
    return (local_part or "e2e")[:100]


def get_or_create_e2e_user(
    email: str,
    *,
    full_name: str | None = None,
    short_name: str | None = None,
    language: str | None = DEFAULT_E2E_LANGUAGE,
):
    """Get or create an E2E user and normalize its bootstrap profile."""
    user = models.User.objects.filter(email=email).first()
    created = user is None
    if not user:
        user = models.User(email=email, sub=None)
        user.set_unusable_password()

    desired_full_name = full_name or _default_full_name(email)
    desired_short_name = short_name or _default_short_name(email)

    update_fields: list[str] = []
    if user.full_name != desired_full_name:
        user.full_name = desired_full_name
        update_fields.append("full_name")
    if user.short_name != desired_short_name:
        user.short_name = desired_short_name
        update_fields.append("short_name")
    if user.language != language:
        user.language = language
        update_fields.append("language")

    if created:
        user.save()
    elif update_fields:
        user.save(update_fields=[*update_fields, "updated_at"])

    return user


def ensure_item_owner_access(item, user):
    """Ensure the user keeps owner access on an E2E-created item."""
    models.ItemAccess.objects.get_or_create(
        item=item,
        user=user,
        defaults={"role": models.RoleChoices.OWNER},
    )
    return item


def ensure_main_workspace(user):
    """
    Ensure the user has a main workspace and owner access to it.

    E2E runs reset the DB entirely; the regular OIDC onboarding flow is not
    exercised, so we must create the minimum required data for "My files".
    """
    workspace = (
        models.Item.objects.filter(
            creator=user,
            type=models.ItemTypeChoices.FOLDER,
            main_workspace=True,
            ancestors_deleted_at__isnull=True,
            deleted_at__isnull=True,
        )
        .order_by("created_at")
        .first()
    )
    if not workspace:
        workspace = models.Item.objects.create_child(
            creator=user,
            link_reach=LinkReachChoices.RESTRICTED,
            type=models.ItemTypeChoices.FOLDER,
            title="My files",
            main_workspace=True,
        )

    return ensure_item_owner_access(workspace, user)


def ensure_named_child_folder(parent, *, title, creator):
    """Create or reuse a deterministic child folder for E2E data scopes."""
    folder = (
        parent.children()
        .filter(title=title, type=models.ItemTypeChoices.FOLDER)
        .order_by("created_at")
        .first()
    )
    if folder:
        if folder.deleted_at is not None:
            folder.restore()
        return ensure_item_owner_access(folder, creator)

    folder = models.Item.objects.create_child(
        parent=parent,
        creator=creator,
        link_reach=LinkReachChoices.RESTRICTED,
        type=models.ItemTypeChoices.FOLDER,
        title=title,
        main_workspace=False,
    )
    return ensure_item_owner_access(folder, creator)


def find_main_workspace(user):
    """Return the user's main workspace if it already exists."""
    return (
        models.Item.objects.filter(
            creator=user,
            type=models.ItemTypeChoices.FOLDER,
            main_workspace=True,
            ancestors_deleted_at__isnull=True,
            deleted_at__isnull=True,
            hard_deleted_at__isnull=True,
        )
        .order_by("created_at")
        .first()
    )


def delete_item_subtree(root) -> int:
    """Delete one item subtree in one DB query."""
    items = models.Item.objects.filter(path__descendants=root.path)
    purge_item_relations(items)
    return items.delete()[0]


def clear_workspace_descendants(workspace) -> int:
    """Delete everything below a workspace root while preserving the workspace."""
    items = models.Item.objects.filter(path__descendants=workspace.path).exclude(
        pk=workspace.pk
    )
    purge_item_relations(items)
    return items.delete()[0]


def purge_item_relations(items) -> None:
    """Delete item-bound relations explicitly before subtree cleanup.

    Some E2E flows create side tables such as link traces from share-link previews.
    The subtree cleanup path should remove those relations deterministically instead
    of relying on collector/DB cascade behavior.
    """
    item_ids = list(items.values_list("pk", flat=True))
    if not item_ids:
        return
    models.LinkTrace.objects.filter(item_id__in=item_ids).delete()
    models.ItemFavorite.objects.filter(item_id__in=item_ids).delete()
    models.ItemAccess.objects.filter(item_id__in=item_ids).delete()
    models.Invitation.objects.filter(item_id__in=item_ids).delete()
    models.MirrorItemTask.objects.filter(item_id__in=item_ids).delete()


def get_e2e_users_for_scope(
    *,
    run_id: str,
    worker_id: str | None = None,
    actor_key: str | None = None,
) -> Iterable[models.User]:
    """Return E2E users that belong to one run / worker / actor namespace."""
    if actor_key is not None:
        namespace = SessionNamespace(
            run_id=run_id,
            worker_id=worker_id or "worker",
            actor_key=actor_key,
        )
        return models.User.objects.filter(
            Q(email=namespace.actor_email) | Q(short_name=namespace.actor_short_name)
        ).order_by("email")

    scope_prefix = f"e2e-{run_scope_slug(run_id)}"
    if worker_id is not None:
        scope_prefix = f"{scope_prefix}-{worker_scope_slug(worker_id)}"

    return models.User.objects.filter(short_name__startswith=scope_prefix).order_by(
        "email"
    )
