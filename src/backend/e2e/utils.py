"""E2E utils."""

from lasuite.drf.models.choices import LinkReachChoices

from core import factories, models


def get_or_create_e2e_user(email):
    """Get or create an E2E user."""
    user = models.User.objects.filter(email=email).first()
    if not user:
        user = factories.UserFactory(email=email, sub=None, language="en-us")
    return user


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

    models.ItemAccess.objects.get_or_create(
        item=workspace,
        user=user,
        defaults={"role": models.RoleChoices.OWNER},
    )
    return workspace
