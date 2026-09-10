"""Inspect projections without allowing an application to replace People authority."""

from datetime import timedelta

from django.conf import settings
from django.contrib import admin
from django.utils import timezone

from .models import Account, DirectoryState, GroupMapping


class ProjectionAdmin(admin.ModelAdmin):
    """Native model permissions and organization scope also apply to diagnostics."""

    actions = None

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        organization = Account.objects.filter(user=request.user).values("organization_id")[:1]
        return queryset.filter(organization_id__in=organization)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DirectoryState)
class DirectoryStateAdmin(ProjectionAdmin):
    """Display the last complete synchronization, including a retryable failure."""

    list_display = ("organization_id", "revision", "checked_at", "fresh", "last_error")

    @admin.display(boolean=True, description="Annuaire à jour")
    def fresh(self, obj):
        return bool(
            obj.checked_at
            and obj.checked_at
            >= timezone.now() - timedelta(seconds=settings.SUITE_IDENTITY_MAX_STALE_SECONDS)
        )


@admin.register(Account)
class AccountAdmin(ProjectionAdmin):
    """Show account association, suspension and independent ST verification."""

    list_display = (
        "principal_id",
        "user",
        "organization_id",
        "active",
        "checked_at",
        "policy_allowed",
        "policy_checked_at",
        "session_version",
    )
    list_filter = ("active", "policy_allowed")
    search_fields = ("=principal_id",)
    list_select_related = ("user",)


@admin.register(GroupMapping)
class GroupMappingAdmin(ProjectionAdmin):
    """The local Django group ID remains inspectable after an IdP migration."""

    list_display = ("display_name", "group_id", "organization_id", "local_group", "active")
    search_fields = ("display_name",)
    list_select_related = ("local_group",)
