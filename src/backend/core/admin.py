"""Admin classes and registrations for core app."""

from functools import partial

from django.contrib import admin, messages
from django.contrib.auth import admin as auth_admin
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from lasuite.malware_detection import malware_detection

from core import models
from core.tasks.user_reconciliation import user_reconciliation_csv_import_job


@admin.register(models.User)
class UserAdmin(auth_admin.UserAdmin):
    """Admin class for the User model"""

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "admin_email",
                    "password",
                )
            },
        ),
        (
            _("Personal info"),
            {
                "fields": (
                    "sub",
                    "email",
                    "full_name",
                    "short_name",
                    "language",
                    "timezone",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_device",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )
    list_display = (
        "id",
        "sub",
        "full_name",
        "admin_email",
        "email",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_device",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_staff", "is_superuser", "is_device", "is_active")
    ordering = (
        "is_active",
        "-is_superuser",
        "-is_staff",
        "-is_device",
        "-updated_at",
        "full_name",
    )
    readonly_fields = (
        "id",
        "sub",
        "email",
        "full_name",
        "short_name",
        "created_at",
        "updated_at",
    )
    search_fields = ("id", "sub", "admin_email", "email", "full_name")


@admin.register(models.UserReconciliationCsvImport)
class UserReconciliationCsvImportAdmin(admin.ModelAdmin):
    """Admin class for UserReconciliationCsvImport model."""

    list_display = ("id", "__str__", "created_at", "status")

    def save_model(self, request, obj, form, change):
        """Override save_model to trigger the import task on creation."""
        super().save_model(request, obj, form, change)

        if not change:
            # Defer to commit so the task does not run before the row is visible.
            transaction.on_commit(partial(user_reconciliation_csv_import_job.delay, obj.pk))
            messages.success(request, _("Import job created and queued."))


@admin.action(description=_("Process selected user reconciliations"))
def process_reconciliation(_modeladmin, _request, queryset):
    """
    Admin action to process selected user reconciliations.
    The action will process only entries that are ready and have both emails checked.
    """
    processable_entries = queryset.filter(
        status="ready", active_email_checked=True, inactive_email_checked=True
    )

    for entry in processable_entries:
        entry.process_reconciliation_request()


@admin.register(models.UserReconciliation)
class UserReconciliationAdmin(admin.ModelAdmin):
    """Admin class for UserReconciliation model."""

    list_display = ["id", "__str__", "created_at", "status"]
    actions = [process_reconciliation]


class ItemAccessInline(admin.TabularInline):
    """Inline admin class for item accesses."""

    autocomplete_fields = ["user"]
    model = models.ItemAccess
    extra = 0


@admin.register(models.Item)
class ItemAdmin(admin.ModelAdmin):
    """item admin interface declaration."""

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "title",
                    "filename",
                    "size",
                    "deleted_at",
                    "ancestors_deleted_at",
                    "malware_detection_info",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "creator",
                    "link_reach",
                    "link_role",
                )
            },
        ),
        (
            _("Malware detection"),
            {"fields": ("upload_state",)},
        ),
        (
            _("Tree structure"),
            {
                "fields": (
                    "path",
                    "depth",
                    "numchild",
                )
            },
        ),
    )
    inlines = (ItemAccessInline,)
    list_display = (
        "id",
        "title",
        "type",
        "link_reach",
        "link_role",
        "upload_state",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "creator",
        "depth",
        "id",
        "numchild",
        "path",
        "filename",
        "size",
        "deleted_at",
        "ancestors_deleted_at",
        "malware_detection_info",
    )
    search_fields = ("id", "title", "creator__email")
    list_filter = ("upload_state", "link_reach", "link_role")
    show_facets = admin.ShowFacets.ALWAYS
    actions = ("trigger_file_analysis",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate_with_numchild()

        return queryset

    def trigger_file_analysis(self, request, queryset):
        """Reanalyse the file of the items."""

        for item in queryset:
            if item.type == models.ItemTypeChoices.FILE:
                malware_detection.analyse_file(item.file_key, item_id=item.id)

        self.message_user(request, "The files have been scheduled for a new analysis.")


@admin.register(models.Invitation)
class InvitationAdmin(admin.ModelAdmin):
    """Admin interface to handle invitations."""

    fields = (
        "email",
        "item",
        "role",
        "created_at",
        "issuer",
    )
    readonly_fields = (
        "created_at",
        "is_expired",
        "issuer",
    )
    list_display = (
        "email",
        "item",
        "created_at",
        "is_expired",
    )

    def save_model(self, request, obj, form, change):
        obj.issuer = request.user
        obj.save()
