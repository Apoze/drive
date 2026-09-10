"""Admin classes and registrations for core app."""

from functools import partial

from django.contrib import admin, messages
from django.contrib.auth import admin as auth_admin
from django.db import transaction
from django.db.models import CharField, Exists, OuterRef, Subquery
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _

from lasuite.malware_detection import malware_detection
from lasuite.malware_detection.admin import MalwareDetectionAdmin as BaseMalwareDetectionAdmin
from lasuite.malware_detection.models import MalwareDetection

from core import models
from core.malware_detection import analysis_kwargs
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
        (_("Entitlements"), {"fields": ("storage_limit_override",)}),
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
        "storage_limit_override",
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
                    "size_display",
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
        "size_display",
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

    @admin.display(description=_("size"))
    def size_display(self, obj):
        """Return the human readable size of the item file."""
        if obj.size is None:
            return None
        return filesizeformat(obj.size)

    def trigger_file_analysis(self, request, queryset):
        """Reanalyse the file of the items."""

        for item in queryset:
            if item.type == models.ItemTypeChoices.FILE:
                malware_detection.analyse_file(
                    item.file_key, item_id=item.id, **analysis_kwargs(item)
                )

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


class ItemExistsFilter(admin.SimpleListFilter):
    """Filter malware detection records on the existence of their related item."""

    title = _("item exists")
    parameter_name = "item_exists"

    def lookups(self, request, model_admin):
        """Return the filter options."""
        return [("yes", _("Yes")), ("no", _("No"))]

    def queryset(self, request, queryset):
        """Filter the queryset on the item_exists annotation."""
        if self.value() == "yes":
            return queryset.filter(item_exists=True)
        if self.value() == "no":
            return queryset.filter(item_exists=False)
        return queryset


admin.site.unregister(MalwareDetection)


class StorageGrantInline(admin.TabularInline):
    """Grant access without creating or exposing a NAS credential."""

    model = models.StorageGrant
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(models.StorageBackend)
class StorageBackendAdmin(admin.ModelAdmin):
    """Connection metadata; secret references remain in the deployment registry."""

    list_display = (
        "name",
        "registry_id",
        "organization",
        "enabled",
        "maintenance",
        "attribution_pending",
        "inventory_completed_at",
    )
    search_fields = ("name", "registry_id", "organization")
    readonly_fields = (
        "capacity",
        "inventory_completed_at",
        "inventory_generation",
        "maintenance",
        "attribution_pending",
    )
    actions = ("enter_maintenance", "apply_attribution")

    @admin.action(description="Pause writes to edit storage spaces")
    def enter_maintenance(self, request, queryset):
        """Drain writers before allowing an administrator to change roots."""
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_quota import StorageWriteConflict  # noqa: PLC0415

        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_tree_transfer import enter_maintenance  # noqa: PLC0415

        for backend in queryset:
            try:
                enter_maintenance(backend)
            except StorageWriteConflict as exc:
                self.message_user(request, str(exc.detail), level=messages.ERROR)
                return
        self.message_user(
            request, "Storage remains readable. Edit its spaces, then apply attribution."
        )

    @admin.action(description="Reconcile attribution and resume writes")
    def apply_attribution(self, request, queryset):
        """Schedule accounting before reopening the edited namespace."""
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.tasks.storage import reclassify_storage  # noqa: PLC0415

        for backend in queryset.filter(maintenance=True):
            reclassify_storage.delay(str(backend.pk), str(request.user.pk))
        self.message_user(
            request, "Reconciliation scheduled. Writes resume only after successful accounting."
        )


@admin.register(models.StorageSpace)
class StorageSpaceAdmin(admin.ModelAdmin):
    """Manage virtual roots and their path grants with the existing admin UI."""

    list_display = ("name", "backend", "root_path", "owner", "enabled")
    list_filter = ("backend", "enabled")
    search_fields = ("name", "root_path", "owner__email")
    autocomplete_fields = ("owner", "backend")
    inlines = (StorageGrantInline,)


@admin.register(
    models.StorageQuota, models.StorageUsage, models.StorageReservation, models.StorageMoveJob
)
class StorageAccountingAdmin(admin.ModelAdmin):
    """Audit counters and operations; raw edits would corrupt quota accounting."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_list_display(self, request):
        fields = {
            models.StorageQuota: (
                "key",
                "limit_bytes",
                "used_bytes",
                "reserved_bytes",
                "policy_applied_at",
            ),
            models.StorageUsage: (
                "key",
                "space",
                "owner",
                "size",
                "attribution_conflict",
                "observed_at",
            ),
            models.StorageReservation: ("id", "actor", "state", "reserved_bytes", "expires_at"),
            models.StorageMoveJob: ("id", "actor", "space", "state", "updated_at", "reason"),
        }
        return fields[self.model]


@admin.register(MalwareDetection)
class MalwareDetectionAdmin(BaseMalwareDetectionAdmin):
    """Admin class for the MalwareDetection model with item existence tooling."""

    list_display = BaseMalwareDetectionAdmin.list_display + ("item_exists", "item_size")
    list_filter = BaseMalwareDetectionAdmin.list_filter + (ItemExistsFilter,)

    def get_queryset(self, request):
        """Annotate records with the existence and size of their related item."""
        related_items = models.Item.objects.annotate(
            id_text=Cast("id", output_field=CharField())
        ).filter(
            id_text=KeyTextTransform("item_id", OuterRef("parameters")),
        )
        return (
            super()
            .get_queryset(request)
            .annotate(
                item_exists=Exists(related_items),
                item_size=Subquery(related_items.values("size")[:1]),
            )
        )

    @admin.display(boolean=True, description=_("item exists"))
    def item_exists(self, obj):
        """Return whether the item of the record still exists."""
        return obj.item_exists

    @admin.display(description=_("item size"), ordering="item_size")
    def item_size(self, obj):
        """Return the human readable size of the item file."""
        if obj.item_size is None:
            return None
        return filesizeformat(obj.item_size)
