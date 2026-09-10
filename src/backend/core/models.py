"""
Declare and configure the models for the drive core application
"""

# pylint: disable=too-many-lines
import smtplib
import uuid
from datetime import timedelta
from enum import StrEnum
from logging import getLogger
from os.path import splitext

from django.conf import settings
from django.contrib.auth import models as auth_models
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GistIndex
from django.contrib.sites.models import Site
from django.core import mail, validators
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import models, transaction
from django.db.models.expressions import RawSQL
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import get_language, override
from django.utils.translation import gettext_lazy as _

from django_ltree.functions import NLevel
from django_ltree.managers import TreeManager, TreeQuerySet
from django_ltree.models import TreeModel
from django_pydantic_field import SchemaField
from lasuite.drf.models.choices import (
    PRIVILEGED_ROLES,
    LinkReachChoices,
    LinkRoleChoices,
    PriorityTextChoices,
    RoleChoices,
    get_equivalent_link_definition,
)
from pydantic import BaseModel as PydanticBaseModel
from suite_identity.access import request_accounts, require_access
from timezone_field import TimeZoneField

from core.mounts.paths import MountPathNormalizationError, normalize_mount_path
from core.storage.cache import invalidate_storage_used_cache
from core.utils.item_title import manage_unique_title as manage_unique_title_utils
from wopi.conversion.policy import is_forced_conversion, target_extension_for

logger = getLogger(__name__)

# Item fields whose update can change the storage used by a user.
STORAGE_USED_FIELDS = {"size", "creator", "creator_id", "hard_deleted_at"}


def get_trashbin_cutoff():
    """
    Calculate the cutoff datetime for soft-deleted items based on the retention policy.

    The function returns the current datetime minus the number of days specified in
    the TRASHBIN_CUTOFF_DAYS setting, indicating the oldest date for items that can
    remain in the trash bin.

    Returns:
        datetime: The cutoff datetime for soft-deleted items.
    """
    return timezone.now() - timedelta(days=settings.TRASHBIN_CUTOFF_DAYS)


class DocumentRoleChoices(PriorityTextChoices):
    """Docs preserves comment-only access; ordinary files retain their own roles."""

    READER = "reader", _("Reader")
    COMMENTER = "commenter", _("Commenter")
    EDITOR = "editor", _("Editor")
    ADMIN = "administrator", _("Administrator")
    OWNER = "owner", _("Owner")


class ItemTypeChoices(models.TextChoices):
    """Defines the types of items that can be created."""

    FOLDER = "folder", _("Folder")
    FILE = "file", _("File")
    DOCS = "docs", _("Docs document")


class ItemUploadStateChoices(models.TextChoices):
    """Defines the possible states of an item."""

    PENDING = "pending", _("Pending")
    CREATING = "creating", _("Creating")
    EXPIRED = "expired", _("Expired")
    DUPLICATING = "duplicating", _("Duplicating")
    CONVERTING = "converting", _("Converting")
    ANALYZING = "analyzing", _("Analyzing")
    SUSPICIOUS = "suspicious", _("Suspicious")
    FILE_TOO_LARGE_TO_ANALYZE = (
        "file_too_large_to_analyze",
        _("File too large to analyze"),
    )
    READY = "ready", _("Ready")


class ItemActivityActionChoices(models.TextChoices):
    """Stable product activity codes exposed by the item activity API."""

    CREATED = "created", _("Created")
    RENAMED = "renamed", _("Renamed")
    DESCRIPTION_UPDATED = "description_updated", _("Description updated")
    CONTENT_UPDATED = "content_updated", _("Content updated")
    MOVED = "moved", _("Moved")
    TRASHED = "trashed", _("Moved to trash")
    RESTORED = "restored", _("Restored")
    DOWNLOAD_STARTED = "download_started", _("Download started")
    USER_ACCESS_CREATED = "user_access_created", _("User access created")
    USER_ACCESS_UPDATED = "user_access_updated", _("User access updated")
    USER_ACCESS_REVOKED = "user_access_revoked", _("User access revoked")
    TEAM_ACCESS_CREATED = "team_access_created", _("Team access created")
    TEAM_ACCESS_UPDATED = "team_access_updated", _("Team access updated")
    TEAM_ACCESS_REVOKED = "team_access_revoked", _("Team access revoked")
    INVITATION_CREATED = "invitation_created", _("Invitation created")
    INVITATION_UPDATED = "invitation_updated", _("Invitation updated")
    INVITATION_REVOKED = "invitation_revoked", _("Invitation revoked")
    SHARE_LINK_CREATED = "share_link_created", _("Share link created")
    SHARE_LINK_UPDATED = "share_link_updated", _("Share link updated")
    SHARE_LINK_REVOKED = "share_link_revoked", _("Share link revoked")


class MirrorItemTaskStatusChoices(models.TextChoices):
    """Defines the possible statuses for a mirroring task."""

    PENDING = "pending", _("Pending")
    PROCESSING = "processing", _("Processing")
    COMPLETED = "completed", _("Completed")
    FAILED = "failed", _("Failed")


class DuplicateEmailError(Exception):
    """Raised when an email is already associated with a pre-existing user."""

    def __init__(self, message=None, email=None):
        """Set message and email to describe the exception."""
        self.message = message
        self.email = email
        super().__init__(self.message)


class BaseModel(models.Model):
    """
    Serves as an abstract base model for other models, ensuring that records are validated
    before saving as Django doesn't do it by default.

    Includes fields common to all models: a UUID primary key and creation/update timestamps.
    """

    id = models.UUIDField(
        verbose_name=_("id"),
        help_text=_("primary key for the record as UUID"),
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_at = models.DateTimeField(
        verbose_name=_("created on"),
        help_text=_("date and time at which a record was created"),
        auto_now_add=True,
        editable=False,
    )
    updated_at = models.DateTimeField(
        verbose_name=_("updated on"),
        help_text=_("date and time at which a record was last updated"),
        auto_now=True,
        editable=False,
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Call `full_clean` before saving."""
        self.full_clean()
        super().save(*args, **kwargs)


class UserManager(auth_models.UserManager):
    """Custom manager for User model with additional methods."""

    def get_user_by_sub_or_email(self, sub, email):
        """Fetch existing user by sub or email."""
        try:
            return self.get(sub=sub)
        except self.model.DoesNotExist as err:
            if not email:
                return None

            if settings.OIDC_FALLBACK_TO_EMAIL_FOR_IDENTIFICATION:
                try:
                    return self.get(email__iexact=email)
                except self.model.DoesNotExist:
                    pass
            elif (
                self.filter(email__iexact=email).exists()
                and not settings.OIDC_ALLOW_DUPLICATE_EMAILS
            ):
                raise DuplicateEmailError(
                    _(
                        "We couldn't find a user with this sub but the email is already "
                        "associated with a registered user."
                    )
                ) from err
        return None


class ColumnType(StrEnum):
    """Type of column allowed."""

    LAST_MODIFIED = "last_modified"
    CREATED = "created"
    CREATED_BY = "created_by"
    FILE_TYPE = "file_type"
    FILE_SIZE = "file_size"


class ColumnPreferences(PydanticBaseModel):
    """Pydantic model to validate the custom columns a user can have."""

    column1: ColumnType
    column2: ColumnType

    model_config = {"extra": "forbid"}


class User(AbstractBaseUser, BaseModel, auth_models.PermissionsMixin):
    """User model to work with OIDC only authentication."""

    sub_validator = validators.RegexValidator(
        regex=r"^[\w.@+-:]+\Z",
        message=_(
            "Enter a valid sub. This value may contain only letters, "
            "numbers, and @/./+/-/_/: characters."
        ),
    )

    sub = models.CharField(
        _("sub"),
        help_text=_(
            "Required. 255 characters or fewer. Letters, numbers, and @/./+/-/_/: characters only."
        ),
        max_length=255,
        unique=True,
        validators=[sub_validator],
        blank=True,
        null=True,
    )

    full_name = models.CharField(_("full name"), max_length=100, null=True, blank=True)
    short_name = models.CharField(_("short name"), max_length=100, null=True, blank=True)

    email = models.EmailField(_("identity email address"), blank=True, null=True)
    column_preferences = SchemaField(ColumnPreferences, blank=True, null=True, default=None)

    # Unlike the "email" field which stores the email coming from the OIDC token, this field
    # stores the email used by staff users to login to the admin site
    admin_email = models.EmailField(_("admin email address"), unique=True, blank=True, null=True)

    language = models.CharField(
        max_length=10,
        choices=settings.LANGUAGES,
        default=None,
        verbose_name=_("language"),
        help_text=_("The language in which the user wants to see the interface."),
        null=True,
        blank=True,
    )
    timezone = TimeZoneField(
        choices_display="WITH_GMT_OFFSET",
        use_pytz=False,
        default=settings.TIME_ZONE,
        help_text=_("The timezone in which the user wants to see times."),
    )
    is_device = models.BooleanField(
        _("device"),
        default=False,
        help_text=_("Whether the user is a device or a real user."),
    )
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )

    storage_limit_override = models.BigIntegerField(
        _("storage limit override"),
        help_text=_(
            "Storage limit in bytes for this user, used by the local entitlements "
            "backend. Leave empty to use the configured default limit. "
            "Set to 0 for unlimited storage."
        ),
        null=True,
        blank=True,
        default=None,
        validators=[validators.MinValueValidator(0)],
    )

    claims = models.JSONField(
        blank=True,
        default=dict,
        help_text=_("Claims from the OIDC token."),
    )

    last_release_note_seen = models.CharField(
        _("last release note seen"),
        max_length=85,
        blank=True,
        null=True,
    )

    objects = UserManager()

    USERNAME_FIELD = "admin_email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "drive_user"
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return self.email or self.admin_email or str(self.id)

    def save(self, *args, **kwargs):
        """
        If it's a new user, give its user access to the items to which s.he was invited.
        """
        is_adding = self._state.adding

        super().save(*args, **kwargs)

        if is_adding:
            self._convert_valid_invitations()

    def _convert_valid_invitations(self):
        """
        Convert valid invitations to item accesses.
        Expired invitations are ignored.
        """
        valid_invitations = Invitation.objects.filter(
            email__iexact=self.email,
            # Native Docs invitations are accepted explicitly by a suite principal.
            item__type__in=[ItemTypeChoices.FILE, ItemTypeChoices.FOLDER],
            created_at__gte=(
                timezone.now() - timedelta(seconds=settings.INVITATION_VALIDITY_DURATION)
            ),
        ).select_related("item")

        if not valid_invitations.exists():
            return

        ItemAccess.objects.bulk_create(
            [
                ItemAccess(user=self, item=invitation.item, role=invitation.role)
                for invitation in valid_invitations
            ]
        )

        # Set creator of items if not yet set (e.g. items created via server-to-server API)
        item_ids = [invitation.item_id for invitation in valid_invitations]
        Item.objects.filter(id__in=item_ids, creator__isnull=True).update(creator=self)
        # The bulk update bypasses Item.save() invalidating the
        # storage used cache.
        transaction.on_commit(lambda: invalidate_storage_used_cache([self.id]))

        valid_invitations.delete()

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Email this user."""
        if not self.email:
            raise ValueError("User has no email address.")
        mail.send_mail(subject, message, from_email, [self.email], **kwargs)

    def send_email(self, subject, context=None, language=None):
        """Generate and send email to the user from a template."""

        if not settings.EMAIL_HOST:
            logger.info("EMAIL_HOST host is not set, skipping email sending")
            return

        context = context or {}
        domain = settings.EMAIL_URL_APP or Site.objects.get_current().domain
        language = language or get_language()
        context.update(
            {
                "brandname": settings.EMAIL_BRAND_NAME,
                "domain": domain,
                "logo_img": settings.EMAIL_LOGO_IMG,
            }
        )

        with override(language):
            msg_html = render_to_string("mail/html/reconciliation.html", context)
            msg_plain = render_to_string("mail/text/reconciliation.txt", context)
            subject = str(subject)  # Force translation

            try:
                send_mail(
                    subject.capitalize(),
                    msg_plain,
                    settings.EMAIL_FROM,
                    [self.email],
                    html_message=msg_html,
                    fail_silently=False,
                )
            except smtplib.SMTPException as exception:
                logger.error("reconciliation email was not sent: %s", exception)

    @cached_property
    def teams(self):
        """Stable local group references; renaming a group never changes its grants."""
        if not self.pk or self._state.adding or not self.is_active:
            return []
        return [f"group:{pk}" for pk in self.groups.order_by("pk").values_list("pk", flat=True)]

    def refresh_from_db(self, *args, **kwargs):
        """Revalidation of a long operation must also observe revoked group membership."""
        super().refresh_from_db(*args, **kwargs)
        self.__dict__.pop("teams", None)


class UserReconciliation(BaseModel):
    """Model to run batch jobs to replace an active user by another one."""

    active_email = models.EmailField(_("Active email address"))
    inactive_email = models.EmailField(_("Email address to deactivate"))
    active_email_checked = models.BooleanField(default=False)
    inactive_email_checked = models.BooleanField(default=False)
    active_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="active_user",
    )
    inactive_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inactive_user",
    )
    active_email_confirmation_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, null=True
    )
    inactive_email_confirmation_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, null=True
    )
    source_unique_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Unique ID in the source file"),
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", _("Pending")),
            ("ready", _("Ready")),
            ("done", _("Done")),
            ("error", _("Error")),
        ],
        default="pending",
    )
    logs = models.TextField(blank=True)

    class Meta:
        db_table = "drive_user_reconciliation"
        verbose_name = _("user reconciliation")
        verbose_name_plural = _("user reconciliations")
        ordering = ["-created_at"]

    def __str__(self):
        return f"User reconciliation {self.id}"

    def save(self, *args, **kwargs):
        """
        For pending queries, identify the actual users and send validation emails.
        """
        if self.status == "pending":
            self.active_user = User.objects.filter(email=self.active_email).first()
            self.inactive_user = User.objects.filter(email=self.inactive_email).first()

            if self.active_user and self.inactive_user:
                if not self.active_email_checked:
                    self.send_reconciliation_confirm_email(
                        self.active_user, "active", self.active_email_confirmation_id
                    )
                if not self.inactive_email_checked:
                    self.send_reconciliation_confirm_email(
                        self.inactive_user,
                        "inactive",
                        self.inactive_email_confirmation_id,
                    )
                self.status = "ready"
            else:
                self.status = "error"
                self.logs = "Error: Both active and inactive users need to exist."

        super().save(*args, **kwargs)

    @transaction.atomic
    def process_reconciliation_request(self):
        """
        Process the reconciliation request as a transaction.

        - Transfer item accesses from inactive to active user, updating roles as needed.
        - Transfer item favorites from inactive to active user.
        - Transfer link traces from inactive to active user.
        - Reassign items created by the inactive user to the active user.
        - Reassign invitations issued by the inactive user to the active user.
        - Activate the active user and deactivate the inactive user.
        - Update the reconciliation entry itself.
        """

        if settings.STORAGE_GOVERNANCE_ENABLED:
            raise ValidationError(
                "Reconcile user identities before activating storage governance; "
                "a live merge would invalidate storage ownership and quotas."
            )

        # Prepare the data to perform the reconciliation on
        updated_accesses, removed_accesses = self.prepare_itemaccess_reconciliation()
        updated_linktraces, removed_linktraces = self.prepare_linktrace_reconciliation()
        updated_favorites, removed_favorites = self.prepare_itemfavorite_reconciliation()
        updated_items = self.prepare_item_creator_reconciliation()
        updated_invitations = self.prepare_invitation_issuer_reconciliation()

        self.active_user.is_active = True
        self.inactive_user.is_active = False

        # Actually perform the bulk operations
        ItemAccess.objects.bulk_update(updated_accesses, ["user", "role"])
        if removed_accesses:
            ids_to_delete = [entry.id for entry in removed_accesses]
            ItemAccess.objects.filter(id__in=ids_to_delete).delete()
            # Bulk delete bypasses ItemAccess.delete(), so the nb_accesses cache
            # of the affected items must be invalidated explicitly.
            items_to_invalidate = {entry.item_id: entry.item for entry in removed_accesses}
            for item in items_to_invalidate.values():
                item.invalidate_nb_accesses_cache()

        ItemFavorite.objects.bulk_update(updated_favorites, ["user"])
        if removed_favorites:
            ids_to_delete = [entry.id for entry in removed_favorites]
            ItemFavorite.objects.filter(id__in=ids_to_delete).delete()

        LinkTrace.objects.bulk_update(updated_linktraces, ["user"])
        if removed_linktraces:
            ids_to_delete = [entry.id for entry in removed_linktraces]
            LinkTrace.objects.filter(id__in=ids_to_delete).delete()

        Item.objects.bulk_update(updated_items, ["creator"])
        # The bulk update bypasses Item.save() invalidating the
        # storage used cache, and both users' usage change.
        transaction.on_commit(
            lambda: invalidate_storage_used_cache([self.active_user_id, self.inactive_user_id])
        )
        Invitation.objects.bulk_update(updated_invitations, ["issuer"])

        User.objects.bulk_update([self.active_user, self.inactive_user], ["is_active"])

        # Wrap up the reconciliation entry
        self.logs += (
            f"Requested update for {len(updated_accesses)} ItemAccess items "
            f"and deletion for {len(removed_accesses)} ItemAccess items.\n"
        )
        self.status = "done"
        self.save()

        self.send_reconciliation_done_email()

    def prepare_itemaccess_reconciliation(self):
        """
        Prepare the reconciliation by transferring item accesses from the inactive user
        to the active user.
        """
        updated_accesses = []
        removed_accesses = []
        inactive_accesses = ItemAccess.objects.filter(user=self.inactive_user)

        # Check items where the active user already has access
        inactive_accesses_items = inactive_accesses.values_list("item", flat=True)
        existing_accesses = ItemAccess.objects.filter(user=self.active_user).filter(
            item__in=inactive_accesses_items
        )
        existing_roles_per_item = dict(existing_accesses.values_list("item", "role"))

        for entry in inactive_accesses:
            if entry.item_id in existing_roles_per_item:
                # Update role if needed
                existing_role = existing_roles_per_item[entry.item_id]
                max_role = RoleChoices.max(entry.role, existing_role)
                if existing_role != max_role:
                    existing_access = existing_accesses.get(item=entry.item)
                    existing_access.role = max_role
                    updated_accesses.append(existing_access)
                removed_accesses.append(entry)
            else:
                entry.user = self.active_user
                updated_accesses.append(entry)

        return updated_accesses, removed_accesses

    def prepare_itemfavorite_reconciliation(self):
        """
        Prepare the reconciliation by transferring item favorites from the inactive user
        to the active user.
        """
        updated_favorites = []
        removed_favorites = []

        existing_favorites = ItemFavorite.objects.filter(user=self.active_user)
        existing_favorite_item_ids = set(existing_favorites.values_list("item_id", flat=True))

        inactive_favorites = ItemFavorite.objects.filter(user=self.inactive_user)

        for entry in inactive_favorites:
            if entry.item_id in existing_favorite_item_ids:
                removed_favorites.append(entry)
            else:
                entry.user = self.active_user
                updated_favorites.append(entry)

        return updated_favorites, removed_favorites

    def prepare_linktrace_reconciliation(self):
        """
        Prepare the reconciliation by transferring link traces from the inactive user
        to the active user.
        """
        updated_linktraces = []
        removed_linktraces = []

        existing_linktraces = LinkTrace.objects.filter(user=self.active_user)
        inactive_linktraces = LinkTrace.objects.filter(user=self.inactive_user)

        for entry in inactive_linktraces:
            if existing_linktraces.filter(item=entry.item).exists():
                removed_linktraces.append(entry)
            else:
                entry.user = self.active_user
                updated_linktraces.append(entry)

        return updated_linktraces, removed_linktraces

    def prepare_item_creator_reconciliation(self):
        """
        Prepare the reconciliation by reassigning items created by the inactive user
        to the active user.
        """
        updated_items = []

        inactive_items = Item.objects.filter(creator=self.inactive_user)

        for entry in inactive_items:
            entry.creator = self.active_user
            updated_items.append(entry)

        return updated_items

    def prepare_invitation_issuer_reconciliation(self):
        """
        Prepare the reconciliation by reassigning invitations issued by the inactive user
        to the active user.
        """
        updated_invitations = []

        inactive_invitations = Invitation.objects.filter(issuer=self.inactive_user)

        for entry in inactive_invitations:
            entry.issuer = self.active_user
            updated_invitations.append(entry)

        return updated_invitations

    def send_reconciliation_confirm_email(self, user, user_type, confirmation_id, language=None):
        """Method allowing to send confirmation email for reconciliation requests."""
        language = language or get_language()
        domain = settings.EMAIL_URL_APP or Site.objects.get_current().domain

        message = _(
            """You have requested a reconciliation of your user accounts on Drive.
            To confirm that you are the one who initiated the request
            and that this email belongs to you:"""
        )

        with override(language):
            subject = _("Confirm by clicking the link to start the reconciliation")
            context = {
                "title": subject,
                "message": message,
                "link": f"{domain}/user-reconciliations/{user_type}/{confirmation_id}/",
                "link_label": str(_("Click here")),
                "button_label": str(_("Confirm")),
            }

        user.send_email(subject, context, language)

    def send_reconciliation_done_email(self, language=None):
        """Method allowing to send done email for reconciliation requests."""
        language = language or get_language()
        domain = settings.EMAIL_URL_APP or Site.objects.get_current().domain

        message = _(
            """Your reconciliation request has been processed.
            New documents are likely associated with your account:"""
        )

        with override(language):
            subject = _("Your accounts have been merged")
            context = {
                "title": subject,
                "message": message,
                "link": f"{domain}/",
                "link_label": str(_("Click here to see")),
                "button_label": str(_("See my documents")),
            }

        self.active_user.send_email(subject, context, language)


class UserReconciliationCsvImport(BaseModel):
    """Model to import reconciliation requests from an external source."""

    file = models.FileField(upload_to="imports/", verbose_name=_("CSV file"))
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", _("Pending")),
            ("running", _("Running")),
            ("done", _("Done")),
            ("error", _("Error")),
        ],
        default="pending",
    )
    logs = models.TextField(blank=True)

    class Meta:
        db_table = "drive_user_reconciliation_csv_import"
        verbose_name = _("user reconciliation CSV import")
        verbose_name_plural = _("user reconciliation CSV imports")

    def __str__(self):
        return f"User reconciliation CSV import {self.id}"

    def send_email(self, subject, emails, context=None, language=None):
        """Generate and send email to the user from a template."""

        if not settings.EMAIL_HOST:
            logger.debug("EMAIL_HOST host is not set, skipping email sending")
            return

        context = context or {}
        domain = settings.EMAIL_URL_APP or Site.objects.get_current().domain
        language = language or get_language()
        context.update(
            {
                "brandname": settings.EMAIL_BRAND_NAME,
                "domain": domain,
                "logo_img": settings.EMAIL_LOGO_IMG,
            }
        )

        with override(language):
            msg_html = render_to_string("mail/html/reconciliation.html", context)
            msg_plain = render_to_string("mail/text/reconciliation.txt", context)
            subject = str(subject)  # Force translation

            try:
                send_mail(
                    subject.capitalize(),
                    msg_plain,
                    settings.EMAIL_FROM,
                    emails,
                    html_message=msg_html,
                    fail_silently=False,
                )
            except smtplib.SMTPException as exception:
                logger.error("reconciliation import email was not sent: %s", exception)

    def send_reconciliation_error_email(self, recipient_email, other_email, language=None):
        """Method allowing to send email for reconciliation requests with errors."""
        language = language or get_language()

        emails = [recipient_email]

        message = _(
            """Your request for reconciliation was unsuccessful.
            Reconciliation failed for the following email addresses:
            {recipient_email}, {other_email}.
            Please check for typos.
            You can submit another request with the valid email addresses."""
        ).format(recipient_email=recipient_email, other_email=other_email)

        with override(language):
            subject = _("Reconciliation of your Drive accounts not completed")
            context = {
                "title": subject,
                "message": message,
                "link": settings.USER_RECONCILIATION_FORM_URL,
                "link_label": str(_("Click here")),
                "button_label": str(_("Make a new request")),
            }

        self.send_email(subject, emails, context, language)


class AnnotateUserRoleQuerySetMixin:
    """Mixin to use in a QuerySet to add user_roles annotation."""

    def annotate_user_roles(self, user):
        """
        Annotate queryset with the roles of the current user
        on the item or its ancestors.
        """
        output_field = ArrayField(base_field=models.CharField())

        if user.is_authenticated:
            user_roles_subquery = ItemAccess.objects.filter(
                models.Q(user=user) | models.Q(team__in=user.teams),
                item__path__ancestors=models.OuterRef(self.path_property),
            ).values_list("role", flat=True)

            return self.annotate(
                user_roles=models.Func(
                    user_roles_subquery, function="ARRAY", output_field=output_field
                )
            )

        return self.annotate(
            user_roles=models.Value([], output_field=output_field),
        )


class ItemQuerySet(AnnotateUserRoleQuerySetMixin, TreeQuerySet):
    """Custom queryset for Item model with additional methods."""

    path_property = "path"

    def readable_per_se(self, user):
        """
        Filters the queryset to return documents that the given user has
        permission to read.
        :param user: The user for whom readable documents are to be fetched.
        :return: A queryset of documents readable by the user.
        """
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_access import bound_queryset  # noqa: PLC0415

        queryset = bound_queryset(self, user)
        if user.is_authenticated:
            return queryset.filter(
                models.Q(accesses__user=user)
                | models.Q(accesses__team__in=user.teams)
                | models.Q(_matching_grant=True)
                | ~models.Q(link_reach=LinkReachChoices.RESTRICTED)
            )

        return queryset.filter(models.Q(link_reach=LinkReachChoices.PUBLIC))

    def filter_non_deleted(self, **kwargs):
        """Filter the non deleted items"""
        return self.filter(
            models.Q(
                models.Q(deleted_at__isnull=True) | models.Q(ancestors_deleted_at__isnull=True),
            ),
            **kwargs,
        )

    def created_by(self, user):
        """Filter items created by the given user."""
        return self.filter(creator=user)

    def not_created_by(self, user):
        """Filter items created by someone other than the given user."""
        return self.exclude(creator=user)

    def favorited_by(self, user):
        """Filter items the given user marked as favorite."""
        favorite = ItemFavorite.objects.filter(item_id=models.OuterRef("pk"), user=user)
        return self.filter(models.Exists(favorite))

    def not_favorited_by(self, user):
        """Filter items the given user did not mark as favorite."""
        favorite = ItemFavorite.objects.filter(item_id=models.OuterRef("pk"), user=user)
        return self.exclude(models.Exists(favorite))

    def owned_by(self, user):
        """Filter items the given user owns directly or through an ancestor access."""
        owner_access = ItemAccess.objects.filter(
            models.Q(user=user) | models.Q(team__in=user.teams),
            role=RoleChoices.OWNER,
            item__path__ancestors=models.OuterRef("path"),
        )
        return self.filter(models.Exists(owner_access))

    def annotate_is_favorite(self, user):
        """
        Annotate item queryset with the favorite status for the current user.
        """
        if user.is_authenticated:
            favorite_exists_subquery = ItemFavorite.objects.filter(
                item_id=models.OuterRef("pk"), user=user
            )
            return self.annotate(is_favorite=models.Exists(favorite_exists_subquery))

        return self.annotate(is_favorite=models.Value(False))

    def annotate_user_roles(self, user):
        """
        Annotate item queryset with the roles of the current user
        on the item or its ancestors.
        """
        output_field = ArrayField(base_field=models.CharField())

        if user.is_authenticated:
            user_roles_subquery = ItemAccess.objects.filter(
                models.Q(user=user) | models.Q(team__in=user.teams),
                item__path__ancestors=models.OuterRef("path"),
            ).values_list("role", flat=True)

            return self.annotate(
                user_roles=models.Func(
                    user_roles_subquery, function="ARRAY", output_field=output_field
                )
            )

        return self.annotate(
            user_roles=models.Value([], output_field=output_field),
        )

    def annotate_with_numchild(self):
        """
        Annotate queryset with the count of direct non-deleted children (_numchild)
        and folder children (_numchild_folder).
        Uses two correlated subqueries; the Item.numchild property reads these annotations.
        """
        direct_children_qs = (
            Item.objects.filter(
                path__descendants=models.OuterRef("path"),
                deleted_at__isnull=True,
                ancestors_deleted_at__isnull=True,
            )
            .annotate(_depth_diff=NLevel("path") - NLevel(models.OuterRef("path")))
            .filter(_depth_diff=1)
            .order_by()
        )

        numchild_sq = models.Subquery(
            # .values(group_key=...) introduces a GROUP BY on a constant, collapsing
            # all rows into a single aggregate row so that the subsequent .annotate()
            # produces exactly one COUNT value — the scalar the Subquery expects.
            # Without it, Django would emit no GROUP BY and the ORM would raise an
            # error because COUNT appears without a matching group expression.
            direct_children_qs.values(group_key=models.Value(1))
            .annotate(count=models.Count("pk"))
            .values("count"),
            output_field=models.IntegerField(),
        )

        numchild_folder_sq = models.Subquery(
            direct_children_qs.filter(type=ItemTypeChoices.FOLDER)
            .values(group_key=models.Value(1))
            .annotate(count=models.Count("pk"))
            .values("count"),
            output_field=models.IntegerField(),
        )

        return self.annotate(
            _numchild=numchild_sq,
            _numchild_folder=numchild_folder_sq,
        )


class ItemManager(TreeManager.from_queryset(ItemQuerySet)):
    """Custom manager for Item model overriding create_child method."""

    def get_queryset(self):
        """Get the queryset for the Item model."""
        return ItemQuerySet(model=self.model, using=self._db)

    def readable_per_se(self, user):
        """
        Filters documents based on user permissions using the custom queryset.
        :param user: The user for whom readable documents are to be fetched.
        :return: A queryset of documents readable by the user.
        """
        return self.get_queryset().readable_per_se(user)

    def create_child(self, parent=None, **kwargs):
        """
        Check if the item can have children before adding one and if the title is
        unique in the same path.
        """
        if parent:
            if parent.type != ItemTypeChoices.FOLDER and not (
                parent.type == ItemTypeChoices.DOCS and kwargs.get("type") == ItemTypeChoices.DOCS
            ):
                raise ValidationError(
                    {
                        "type": ValidationError(
                            _("Only folders can have children."),
                            code="item_create_child_type_folder_only",
                        )
                    }
                )
            kwargs["title"] = manage_unique_title_utils(
                self.children(parent.path), kwargs.get("title")
            )

        if not kwargs.get("id"):
            kwargs["id"] = str(uuid.uuid4())

        kwargs["path"] = str(kwargs["id"])

        if parent:
            kwargs["path"] = f"{parent.path!s}.{kwargs['id']!s}"
            if kwargs.get("type") != ItemTypeChoices.DOCS:
                kwargs.setdefault("storage_backend_id", parent.storage_backend_id)
                kwargs.setdefault("storage_space_id", parent.storage_space_id)

        item = self.create(**kwargs)

        return item


# pylint: disable=too-many-public-methods,too-many-instance-attributes
class Item(TreeModel, BaseModel):
    """Item in the tree."""

    storage_backend = models.ForeignKey(
        "StorageBackend",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="items",
    )
    storage_space = models.ForeignKey(
        "StorageSpace",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="items",
    )
    storage_key_prefix = models.CharField(max_length=512, blank=True, default="")
    share_link_nonce = models.UUIDField(null=True, blank=True, editable=False)

    title = models.CharField(_("title"), max_length=255)
    link_reach = models.CharField(
        max_length=20,
        choices=LinkReachChoices.choices,
        null=True,
        blank=True,
    )
    link_role = models.CharField(
        max_length=20,
        choices=[*LinkRoleChoices.choices, ("commenter", _("Commenter"))],
        default=LinkRoleChoices.READER,
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        related_name="items_created",
        blank=True,
        null=True,
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    ancestors_deleted_at = models.DateTimeField(null=True, blank=True)
    hard_deleted_at = models.DateTimeField(null=True, blank=True)

    filename = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(
        max_length=30,
        choices=ItemTypeChoices.choices,
        default=ItemTypeChoices.FOLDER,
    )
    upload_state = models.CharField(
        max_length=25,
        choices=ItemUploadStateChoices.choices,
        null=True,
        blank=True,
    )
    upload_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_(
            "Timestamp used to compute pending upload TTL. Set when a file enters "
            "PENDING state and refreshed when a pending upload is re-initiated."
        ),
    )
    mimetype = models.CharField(max_length=255, null=True, blank=True)
    main_workspace = models.BooleanField(default=False)
    size = models.BigIntegerField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    malware_detection_info = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text=_("Malware detection info when the analysis status is unsafe."),
    )

    label_size = 7

    objects = ItemManager()

    class Meta:
        db_table = "drive_item"
        verbose_name = _("Item")
        verbose_name_plural = _("Items")
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(deleted_at__isnull=True)
                    | models.Q(deleted_at=models.F("ancestors_deleted_at"))
                ),
                name="check_deleted_at_matches_ancestors_deleted_at_when_set",
            )
        ]
        indexes = [
            GistIndex(fields=["path"]),
            models.Index(NLevel(models.F("path")), name="drive_item_path_nlevel_idx"),
            # Covers the storage used computation by creator.
            models.Index(
                fields=["creator"],
                include=["size"],
                condition=models.Q(hard_deleted_at__isnull=True),
                name="item_creator_size_not_hdel_idx",
            ),
        ]

    def __str__(self):
        return str(self.title)

    def __init__(self, *args, **kwargs):
        """Initialize cache property."""
        super().__init__(*args, **kwargs)
        self._ancestors_link_definition = None
        self._computed_link_definition = None
        self._storage_used_creator_id = self.__dict__.get("creator_id")

    @transaction.atomic
    def save(self, *args, **kwargs):
        """Set the upload state to pending if it's the first save and it's a file"""
        self._validate_storage_location()
        if self.type == ItemTypeChoices.DOCS and kwargs.get("update_fields"):
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"updated_at"}
        if settings.STORAGE_GOVERNANCE_ENABLED and not self._state.adding:
            fields = kwargs.get("update_fields")
            if fields is None or set(fields) & {
                "filename",
                "creator",
                "creator_id",
                "size",
                "deleted_at",
                "ancestors_deleted_at",
                "hard_deleted_at",
                "storage_backend",
                "storage_backend_id",
                "storage_space",
                "storage_space_id",
            }:
                # pylint: disable-next=import-outside-toplevel,cyclic-import
                from core.services.storage_quota import guard_metadata_change  # noqa: PLC0415

                guard_metadata_change(StorageUsage.objects.filter(item=self))
        # Validate filename requirements based on item type
        if self.type == ItemTypeChoices.FILE:
            if self.filename is None:
                raise ValidationError(
                    {
                        "filename": ValidationError(
                            _("Filename is required for files."),
                            code="item_filename_required_for_files",
                        )
                    }
                )
        elif self.filename is not None:
            raise ValidationError(
                {
                    "filename": ValidationError(
                        _("Filename is only allowed for files."),
                        code="item_filename_only_allowed_for_files",
                    )
                }
            )

        if (
            self.created_at is None
            and self.type == ItemTypeChoices.FILE
            and self.upload_state
            not in {
                ItemUploadStateChoices.CREATING,
                ItemUploadStateChoices.DUPLICATING,
                ItemUploadStateChoices.CONVERTING,
            }
        ):
            self.upload_state = ItemUploadStateChoices.PENDING
            self.upload_started_at = timezone.now()

        if (
            self.type == ItemTypeChoices.FILE
            and self.upload_state == ItemUploadStateChoices.PENDING
            and self.upload_started_at is None
        ):
            self.upload_started_at = timezone.now()

        if not self.path:
            self.path = str(self.id)

        update_fields = kwargs.get("update_fields")
        creator_is_saved = update_fields is None or {
            "creator",
            "creator_id",
        }.intersection(update_fields)
        previous_creator_id = self._storage_used_creator_id
        if (
            previous_creator_id is None
            and not self._state.adding
            and creator_is_saved
            and "creator_id" in self.__dict__
        ):
            previous_creator_id = (
                type(self).objects.filter(pk=self.pk).values_list("creator_id", flat=True).first()
            )
        super().save(*args, **kwargs)

        if self.type == ItemTypeChoices.DOCS:
            from core.services.docs_lifecycle import queue_change  # noqa: PLC0415

            queue_change(self, update_fields=update_fields)
        self._invalidate_storage_used_cache(update_fields, previous_creator_id)
        if creator_is_saved:
            self._storage_used_creator_id = self.creator_id

    def _validate_storage_location(self):
        """Changes of destination use the durable transfer workflow."""
        if self.link_role == "commenter" and self.type != ItemTypeChoices.DOCS:
            raise ValidationError("Comment-only links require a Docs document.")
        if self.type == ItemTypeChoices.DOCS:
            if not getattr(settings, "DOCS_DRIVE_ENABLED", False):
                raise ValidationError("Docs integration is not enabled.")
            if self.storage_backend_id or self.storage_space_id or self.storage_key_prefix:
                raise ValidationError("Docs content is stored by Docs, not by a file backend.")
            if self.filename is not None or self.upload_state is not None:
                raise ValidationError("Docs documents cannot carry an upload or filename.")
            return
        if (
            not self._state.adding
            and self.pk
            and Item.objects.filter(pk=self.pk)
            .exclude(
                storage_backend_id=self.storage_backend_id,
                storage_space_id=self.storage_space_id,
                storage_key_prefix=self.storage_key_prefix,
            )
            .exists()
        ):
            raise ValidationError("Use a storage transfer to change an existing item location.")
        if self.storage_backend_id and self.storage_backend.family != "s3":
            raise ValidationError("Regular Drive items require an S3 connection.")
        if self._state.adding and self.storage_backend_id:
            self.storage_key_prefix = self.storage_backend.configuration.get("prefix", "").strip(
                "/"
            )
        if self.storage_space_id and self.storage_space.backend_id != self.storage_backend_id:
            raise ValidationError("The item and its space must use the same connection.")

    def _invalidate_storage_used_cache(self, update_fields, previous_creator_id):
        """
        Invalidate the creator's cached storage usage when a save may have
        changed it. Bulk queryset updates bypass save() and must invalidate
        the cache explicitly.
        """
        if update_fields and STORAGE_USED_FIELDS.isdisjoint(update_fields):
            return
        creator_ids = list(
            dict.fromkeys(user_id for user_id in (previous_creator_id, self.creator_id) if user_id)
        )
        if not creator_ids:
            return
        transaction.on_commit(lambda: invalidate_storage_used_cache(creator_ids))

    def effective_upload_state(self) -> str | None:
        """
        Return the effective upload state, applying the pending TTL deterministically.

        The database value may remain `pending` until an explicit transition occurs,
        but user-facing surfaces should treat an over-TTL pending item as `expired`.
        """
        if self.upload_state != ItemUploadStateChoices.PENDING:
            return self.upload_state

        if not self.upload_started_at:
            return self.upload_state

        ttl_seconds = getattr(settings, "ITEM_UPLOAD_PENDING_TTL_SECONDS", None)
        if not ttl_seconds:
            return self.upload_state

        expires_at = self.upload_started_at + timedelta(seconds=int(ttl_seconds))
        return (
            ItemUploadStateChoices.EXPIRED
            if timezone.now() > expires_at
            else ItemUploadStateChoices.PENDING
        )

    def restart_pending_upload(self) -> None:
        """Restart a pending upload session for this item (idempotent retry target)."""
        if self.type != ItemTypeChoices.FILE:
            raise ValidationError(
                {
                    "type": ValidationError(
                        _("This action is only available for items of type FILE."),
                        code="item_upload_type_unavailable",
                    )
                }
            )

        self.upload_state = ItemUploadStateChoices.PENDING
        self.upload_started_at = timezone.now()
        self.save(update_fields=["upload_state", "upload_started_at", "updated_at"])

    def delete(self, using=None, keep_parents=False):
        if self.deleted_at is None and self.ancestors_deleted_at is None:
            raise RuntimeError("The item must be soft deleted before being deleted.")

        return super().delete(using, keep_parents)

    def ancestors(self):
        """Return the ancestors of the item excluding the item itself."""
        return super().ancestors().exclude(id=self.id)

    def descendants(self):
        """Return the descendants of the item excluding the item itself."""
        return super().descendants().exclude(id=self.id)

    def parent(self):
        """Resolve the immediate ancestor independently of creation-date ordering."""
        if self.depth > 1:
            return (
                type(self)
                .objects.filter(path__ancestors=self.path, path__depth=self.depth - 1)
                .first()
            )
        return None

    @property
    def extension(self):
        """Return the extension related to the filename."""
        if self.filename is None:
            raise RuntimeError("The item must have a filename to compute its extension.")

        _, extension = splitext(self.filename)

        if extension:
            return extension.lstrip(".")

        return None

    @property
    def key_base(self):
        """Key base of the location where the item is stored in object storage."""
        if self.type == ItemTypeChoices.DOCS:
            raise ValidationError("Docs documents do not have a Drive storage key.")
        if not self.pk:
            raise RuntimeError("The item instance must be saved before requesting a storage key.")

        if self.type != ItemTypeChoices.FILE:
            raise RuntimeError("Only files have a storage key.")

        prefix = self.storage_key_prefix
        return f"{prefix + '/' if prefix else ''}item/{self.pk!s}"

    @property
    def file_key(self):
        """Key used to store the file in object storage."""
        if self.type == ItemTypeChoices.DOCS:
            raise ValidationError("Docs documents do not have a Drive storage key.")
        if self.filename is None:
            raise RuntimeError("The item must have a filename to generate a file key.")

        return f"{self.key_base}/{self.filename}"

    @property
    def depth(self):
        """Return the depth of the item in the tree."""
        return len(self.path)

    def get_nb_accesses_cache_key(self):
        """Generate a unique cache key for each item."""
        return f"item_{self.id!s}_nb_accesses"

    def manage_unique_title(self, title):
        """Manage the unique title in the same path."""
        return manage_unique_title_utils(
            self.siblings(),
            title,
        )

    @property
    def nb_accesses(self):
        """Calculate the number of accesses."""
        try:
            return self._nb_accesses
        except AttributeError:
            cache_key = self.get_nb_accesses_cache_key()
            nb_accesses = cache.get(cache_key)

            if nb_accesses is None:
                nb_accesses = ItemAccess.objects.filter(
                    item__path__ancestors=self.path,
                ).count()
                cache.set(cache_key, nb_accesses)

            return nb_accesses

    @property
    def numchild(self):
        """Return the number of non-deleted children from annotation."""
        return self._numchild  # pylint: disable=no-member

    @property
    def numchild_folder(self):
        """Calculate the number of non-deleted folder children from annotation."""
        return self._numchild_folder  # pylint: disable=no-member

    @property
    def is_root(self):
        """Return True if the item is the root of the tree."""
        return len(self.path) == 1

    def get_root(self):
        """Return the root of the tree."""
        return self.ancestors().filter(path__depth=1).first()

    def invalidate_nb_accesses_cache(self):
        """
        Invalidate the cache for number of accesses, including on affected descendants.
        """
        for item in self._meta.model.objects.filter(path__descendants=self.path).only("id"):
            cache_key = item.get_nb_accesses_cache_key()
            cache.delete(cache_key)

    def get_role(self, user):
        """Return the role a user has on an item."""
        if self.type == ItemTypeChoices.DOCS:
            from core.services.docs_resources import role_for_document  # noqa: PLC0415

            return role_for_document(self, user)
        if not user.is_authenticated or not user.is_active:
            return None

        account = require_access(user)
        if account is not None and request_accounts.get() is None:
            self.__dict__.pop("user_roles", None)

        try:
            roles = self.user_roles or []
        except AttributeError:
            roles = ItemAccess.objects.filter(
                models.Q(user=user) | models.Q(team__in=user.teams),
                item__path__ancestors=self.path,
            ).values_list("role", flat=True)

        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_access import effective_role  # noqa: PLC0415

        return effective_role(self, user, RoleChoices.max(*roles))

    @property
    def access_role_choices(self):
        """The role vocabulary belongs to the resource, not its storage provider."""
        return DocumentRoleChoices if self.type == ItemTypeChoices.DOCS else RoleChoices

    def compute_ancestors_links_paths_mapping(self):
        """
        Compute the ancestors links for the current item up to the highest readable ancestor.
        """
        ancestors = (
            (self.ancestors() | self._meta.model.objects.filter(pk=self.pk))
            .filter(ancestors_deleted_at__isnull=True)
            .order_by("path")
        )
        ancestors_links = []
        paths_links_mapping = {}

        for ancestor in ancestors:
            ancestors_links.append(
                {"link_reach": ancestor.link_reach, "link_role": ancestor.link_role}
            )
            paths_links_mapping[str(ancestor.path)] = ancestors_links.copy()

        return paths_links_mapping

    @property
    def link_definition(self):
        """Returns link reach/role as a definition in dictionary format."""
        return {"link_reach": self.link_reach, "link_role": self.link_role}

    @property
    def ancestors_link_definition(self):
        """Link definition equivalent to all document's ancestors."""
        if getattr(self, "_ancestors_link_definition", None) is None:
            if self.depth <= 1:
                ancestors_links = []
            else:
                mapping = self.compute_ancestors_links_paths_mapping()
                ancestors_links = mapping.get(str(self.path[:-1]), [])
            self._ancestors_link_definition = get_equivalent_link_definition(ancestors_links)

        return self._ancestors_link_definition

    @ancestors_link_definition.setter
    def ancestors_link_definition(self, definition):
        """Cache the ancestors_link_definition."""
        self._ancestors_link_definition = definition

    @property
    def ancestors_link_reach(self):
        """Link reach equivalent to all document's ancestors."""
        return self.ancestors_link_definition["link_reach"]

    @property
    def ancestors_link_role(self):
        """Link role equivalent to all document's ancestors."""
        return self.ancestors_link_definition["link_role"]

    @property
    def computed_link_definition(self):
        """
        Link reach/role on the document, combining inherited ancestors' link
        definitions and the document's own link definition.
        """
        if getattr(self, "_computed_link_definition", None) is None:
            self._computed_link_definition = get_equivalent_link_definition(
                [self.ancestors_link_definition, self.link_definition]
            )
        return self._computed_link_definition

    @property
    def computed_link_reach(self):
        """Actual link reach on the document."""
        return self.computed_link_definition["link_reach"]

    @property
    def computed_link_role(self):
        """Actual link role on the document."""
        return self.computed_link_definition["link_role"]

    def _can_convert_legacy_file(self, can_update):
        """Return whether the user can explicitly convert this legacy WOPI file."""
        if not (
            can_update
            and self.type == ItemTypeChoices.FILE
            and self.upload_state
            in (
                ItemUploadStateChoices.READY,
                ItemUploadStateChoices.ANALYZING,
            )
            and target_extension_for(self.extension)
            and settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET
        ):
            return False

        onlyoffice_config = settings.WOPI_CLIENTS_CONFIGURATION.get("onlyoffice") or {}
        onlyoffice_options = onlyoffice_config.get("options") or {}
        return bool(
            onlyoffice_options.get("ConvertServiceUrl")
            and is_forced_conversion(self, onlyoffice_options)
        )

    # Existing permission matrix plus the storage-space boundary.
    # pylint: disable-next=too-many-locals
    def get_abilities(self, user):
        """
        Compute and return abilities for a given user on the item.
        """
        if self.type == ItemTypeChoices.DOCS:
            from core.services.docs_resources import document_abilities  # noqa: PLC0415

            return document_abilities(self, user)

        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_access import bound_abilities  # noqa: PLC0415

        # First get the role based on specific access
        role = self.get_role(user)
        # Characteristics that are based only on specific access
        is_owner = role == RoleChoices.OWNER
        is_deleted = self.ancestors_deleted_at
        is_owner_or_admin = is_owner or role == RoleChoices.ADMIN

        # Compute access roles before adding link roles because we don't
        # want anonymous users to access versions (we wouldn't know from
        # which date to allow them anyway)
        # Anonymous users should also not see item accesses
        has_access_role = bool(role) and not is_deleted
        link_select_options = (
            LinkReachChoices.get_select_options(**self.ancestors_link_definition)
            if has_access_role
            else {}
        )

        link_definition = self.computed_link_definition

        link_reach = link_definition["link_reach"]
        if link_reach == LinkReachChoices.PUBLIC or (
            link_reach == LinkReachChoices.AUTHENTICATED and user.is_authenticated
        ):
            # Set the user role to the highest role between the item role and the link role
            # Needed for a user with an access lower than link_role
            # Needed for a user without access to determine the role he has.
            role = RoleChoices.max(role, link_definition["link_role"])
        can_get = bool(role) and not is_deleted
        can_manage = is_owner_or_admin and not is_deleted
        can_update = (is_owner_or_admin or role == RoleChoices.EDITOR) and not is_deleted
        can_create_children = can_update and user.is_authenticated
        can_hard_delete = (
            is_owner
            if self.is_root
            else (is_owner_or_admin or (user.is_authenticated and self.creator == user))
        )
        can_destroy = can_hard_delete and not is_deleted
        can_duplicate = (
            can_get
            and user.is_authenticated
            and self.type == ItemTypeChoices.FILE
            and self.upload_state == ItemUploadStateChoices.READY
        )
        can_export = can_get and self.type == ItemTypeChoices.FOLDER
        can_convert = self._can_convert_legacy_file(can_update)

        abilities = {
            "activity_view": is_owner_or_admin,
            "accesses_manage": can_manage,
            "accesses_view": has_access_role,
            "breadcrumb": can_get,
            "children_list": can_get,
            "children_create": can_create_children,
            "destroy": can_destroy,
            "download": can_get,
            "duplicate": can_duplicate,
            "export": can_export,
            "convert": can_convert,
            "hard_delete": can_hard_delete,
            "favorite": can_get and user.is_authenticated,
            "link_configuration": can_manage,
            "invite_owner": is_owner and not is_deleted,
            "link_select_options": link_select_options,
            "move": can_manage,
            "restore": is_owner,
            "retrieve": can_get or is_owner,
            "tree": can_get,
            "media_auth": can_get,
            "partial_update": can_update,
            "update": can_update,
            "upload_ended": can_update and user.is_authenticated,
            "upload_policy": can_update and user.is_authenticated,
            "wopi": can_get,
        }

        if self.type == ItemTypeChoices.FILE:
            abilities["text"] = can_get

        return bound_abilities(self, user, abilities)

    def send_email(self, subject, emails, context=None, language=None):
        """Generate and send email from a template."""

        if not settings.EMAIL_HOST:
            logger.debug("EMAIL_HOST host is not set, skipping email sending")
            return

        context = context or {}
        base_url = settings.EMAIL_URL_APP or Site.objects.get_current().domain
        language = language or get_language()
        context.update(
            {
                "brandname": settings.EMAIL_BRAND_NAME,
                "item": self,
                "domain": base_url,
                "link": f"{base_url}/explorer/items/{self.id}/",
                "logo_img": settings.EMAIL_LOGO_IMG,
            }
        )

        with override(language):
            msg_html = render_to_string("mail/html/invitation.html", context)
            msg_plain = render_to_string("mail/text/invitation.txt", context)
            subject = str(subject)  # Force translation

            try:
                send_mail(
                    subject.capitalize(),
                    msg_plain,
                    settings.EMAIL_FROM,
                    emails,
                    html_message=msg_html,
                    fail_silently=False,
                )
            except smtplib.SMTPException as exception:
                logger.error("invitation to %s was not sent: %s", emails, exception)

    def send_invitation_email(self, email, role, sender, language=None):
        """Method allowing a user to send an email invitation to another user for a item."""
        language = language or get_language()
        role = self.access_role_choices(role).label
        sender_name = sender.full_name or sender.email
        sender_name_email = (
            f"{sender.full_name:s} ({sender.email})" if sender.full_name else sender.email
        )

        with override(language):
            context = {
                "title": _("{name} shared an item with you!").format(name=sender_name),
                "message": _(
                    '{name} invited you with the role "{role}" on the following item:'
                ).format(name=sender_name_email, role=role.lower()),
            }
            subject = _("{name} shared an item with you: {title}").format(
                name=sender_name, title=self.title
            )

        self.send_email(subject, [email], context, language)

    @transaction.atomic
    def soft_delete(self):
        """
        Soft delete the item, marking the deletion on descendants.
        We still keep the .delete() method untouched for programmatic purposes.
        """
        if settings.STORAGE_GOVERNANCE_ENABLED:
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_quota import guard_metadata_change  # noqa: PLC0415

            guard_metadata_change(StorageUsage.objects.filter(item__in=self.descendants()))
        if self.deleted_at or self.ancestors_deleted_at:
            raise RuntimeError("This item is already deleted or has deleted ancestors.")

        # Check if any ancestors are deleted
        if self.ancestors().filter(deleted_at__isnull=False).exists():
            raise RuntimeError(
                "Cannot delete this item because one or more ancestors are already deleted."
            )

        self.ancestors_deleted_at = self.deleted_at = timezone.now()

        self.save(update_fields=["deleted_at", "ancestors_deleted_at"])

        # Mark all descendants as soft deleted
        if self.type in {ItemTypeChoices.FOLDER, ItemTypeChoices.DOCS}:
            self.descendants().filter(ancestors_deleted_at__isnull=True).update(
                ancestors_deleted_at=self.ancestors_deleted_at,
            )
            from core.services.docs_lifecycle import queue_tree_changes  # noqa: PLC0415

            queue_tree_changes(self)

    @transaction.atomic
    def hard_delete(self):
        """
        Hard delete the item, marking the deletion on descendants.
        We still keep the .delete() method untouched for programmatic purposes.
        """
        if settings.STORAGE_GOVERNANCE_ENABLED:
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_quota import guard_metadata_change  # noqa: PLC0415

            guard_metadata_change(StorageUsage.objects.filter(item__in=self.descendants()))
        if self.hard_deleted_at:
            raise ValidationError(
                {
                    "hard_deleted_at": ValidationError(
                        _("This item is already hard deleted."),
                        code="item_hard_delete_already_effective",
                    )
                }
            )

        if self.deleted_at is None:
            raise ValidationError(
                {
                    "hard_deleted_at": ValidationError(
                        _("To hard delete an item, it must first be soft deleted."),
                        code="item_hard_delete_should_soft_delete_first",
                    )
                }
            )

        # Collect the creators impacted before marking the tree as hard deleted:
        # descendants can have different creators and their bulk update below
        # bypasses Item.save() invalidating the storage used cache.
        creator_ids = set(
            self.descendants()
            .filter(hard_deleted_at__isnull=True)
            .values_list("creator_id", flat=True)
        )
        self.hard_deleted_at = timezone.now()
        self.save(update_fields=["hard_deleted_at"])

        # Mark all descendants as hard deleted
        self.descendants().update(hard_deleted_at=self.hard_deleted_at)
        from core.services.docs_lifecycle import queue_tree_changes  # noqa: PLC0415

        queue_tree_changes(self)
        if getattr(settings, "STORAGE_GOVERNANCE_ENABLED", False):
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_quota import (  # noqa: PLC0415
                retire_usage,  # pylint: disable=import-outside-toplevel
            )

            retire_usage(
                StorageUsage.objects.filter(item__in=self.descendants()).exclude(
                    item__type=ItemTypeChoices.DOCS
                )
            )

        creator_ids.discard(self.creator_id)
        if creator_ids:
            transaction.on_commit(lambda: invalidate_storage_used_cache(creator_ids))

    @transaction.atomic
    def restore(self):
        """Cancelling a soft delete with checks."""
        # This should not happen
        if self.deleted_at is None:
            raise ValidationError(
                {
                    "deleted_at": ValidationError(
                        _("This item is not deleted."),
                        code="item_restore_not_deleted",
                    )
                }
            )

        if (
            self.deleted_at < get_trashbin_cutoff()
            or Item.objects.filter(
                path__ancestors=self.path,
                hard_deleted_at__isnull=False,
            ).exists()
        ):
            raise ValidationError(
                {
                    "deleted_at": ValidationError(
                        _("This item was permanently deleted and cannot be restored."),
                        code="item_restore_hard_deleted",
                    )
                }
            )

        # save the current deleted_at value to exclude it from the descendants update
        current_deleted_at = self.deleted_at
        has_ancestors_deleted = False

        if self.depth > 1:
            has_ancestors_deleted = self.ancestors().filter(deleted_at__isnull=False).exists()

            if has_ancestors_deleted:
                # if it has ancestors deleted, try to move it to the top level ancestor
                highest_ancestor = self.ancestors().filter(path__depth=1).get()
                self.move(highest_ancestor)

        # Restore the current item
        self.deleted_at = None
        self.ancestors_deleted_at = None

        self.save(update_fields=["deleted_at", "ancestors_deleted_at"])

        self.descendants().exclude(
            models.Q(deleted_at__isnull=False)
            | models.Q(ancestors_deleted_at__lt=current_deleted_at)
        ).update(ancestors_deleted_at=None)
        from core.services.docs_lifecycle import queue_tree_changes  # noqa: PLC0415

        queue_tree_changes(self)

    @transaction.atomic
    def move(self, target):
        """
        Move an item to a new position in the tree.
        """
        if self.storage_space_id and (
            not target or target.storage_space_id != self.storage_space_id
        ):
            raise ValidationError("Use a storage transfer to move between spaces.")
        if (
            target
            and target.type != ItemTypeChoices.FOLDER
            and not (self.type == ItemTypeChoices.DOCS and target.type == ItemTypeChoices.DOCS)
        ):
            raise ValidationError(
                {
                    "target": ValidationError(
                        _("Only folders can be targeted when moving an item"),
                        code="item_move_target_not_a_folder",
                    )
                }
            )

        if target and list(target.path[: self.depth]) == list(self.path):
            raise ValidationError("An item cannot be moved inside itself.")
        if settings.STORAGE_GOVERNANCE_ENABLED:
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_quota import guard_metadata_change  # noqa: PLC0415

            guard_metadata_change(StorageUsage.objects.filter(item__path__descendants=self.path))

        old_path = self.path
        if target:
            self.path = f"{target.path!s}.{self.id!s}"
        else:
            self.path = str(self.id)

        self.save(update_fields=["path"])

        if self.type in {ItemTypeChoices.FOLDER, ItemTypeChoices.DOCS}:
            # https://patshaughnessy.net/2017/12/14/manipulating-trees-using-sql-and-the-postgres-ltree-extension
            self._meta.model.objects.filter(path__descendants=old_path).update(
                path=RawSQL("%s || subpath(path, nlevel(%s))", (str(self.path), str(old_path)))
            )
            from core.services.docs_lifecycle import queue_tree_changes  # noqa: PLC0415

            queue_tree_changes(self)


class ItemActivity(BaseModel):
    """Append-only product activity attached to one regular Drive item."""

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="activity_entries",
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="item_activity_entries",
        null=True,
        blank=True,
    )
    actor_name = models.CharField(max_length=255)
    action = models.CharField(max_length=32, choices=ItemActivityActionChoices.choices)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "drive_item_activity"
        verbose_name = _("Item activity")
        verbose_name_plural = _("Item activities")
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=["item", "-created_at", "-id"],
                name="activity_item_created_id_idx",
            )
        ]

    def __str__(self):
        return f"{self.action} on {self.item_id!s}"

    def clean(self):
        """Keep the structured event payload predictable."""
        super().clean()
        if not isinstance(self.payload, dict):
            raise ValidationError(
                {
                    "payload": ValidationError(
                        _("Activity payload must be an object."),
                        code="item_activity_payload_not_object",
                    )
                }
            )


class MirrorItemTask(BaseModel):
    """Model managing a status for a mirroring task."""

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="mirror_tasks",
    )
    status = models.CharField(
        max_length=25,
        choices=MirrorItemTaskStatusChoices.choices,
        default=MirrorItemTaskStatusChoices.PENDING,
    )
    error_details = models.TextField(null=True, blank=True)
    retries = models.IntegerField(default=0)

    class Meta:
        db_table = "drive_mirror_item_task"
        verbose_name = _("Mirror item task")
        verbose_name_plural = _("Mirror item tasks")

    def __str__(self):
        return f"Mirror task for item {self.item!s} with status {self.status!s}"


class LinkTrace(BaseModel):
    """
    Relation model to trace accesses to an item via a link by a logged-in user.
    This is necessary to show the item in the user's list of items even
    though the user does not have a role on the item.
    """

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="link_traces",
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="link_traces")

    class Meta:
        db_table = "drive_link_trace"
        verbose_name = _("Item/user link trace")
        verbose_name_plural = _("Item/user link traces")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "item"],
                name="unique_link_trace_item_user",
                violation_error_message=_("A link trace already exists for this item/user."),
            ),
        ]

    def __str__(self):
        return f"{self.user!s} trace on item {self.item!s}"


class ItemFavorite(BaseModel):
    """Relation model to store a user's favorite items."""

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="favorited_by_users",
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorite_items")

    class Meta:
        db_table = "drive_item_favorite"
        verbose_name = _("Item favorite")
        verbose_name_plural = _("Item favorites")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "item"],
                name="unique_item_favorite_user",
                violation_error_message=_(
                    "This item is already targeted by a favorite relation instance "
                    "for the same user."
                ),
            ),
        ]

    def __str__(self):
        return f"{self.user!s} favorite on item {self.item!s}"


class ItemAccessQuerySet(AnnotateUserRoleQuerySetMixin, models.QuerySet):
    """Custom queryset for ItemAccess model with additional methods."""

    path_property = "item__path"


class ItemAccessManager(models.Manager.from_queryset(ItemAccessQuerySet)):
    """Manager for ItemAccess model."""


class ItemAccess(BaseModel):
    """Relation model to give access to an item for a user or a team with a role."""

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="accesses",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    team = models.CharField(max_length=100, blank=True)
    role = models.CharField(
        max_length=20, choices=DocumentRoleChoices.choices, default=RoleChoices.READER
    )

    objects = ItemAccessManager()

    class Meta:
        db_table = "drive_item_access"
        ordering = ("-created_at",)
        verbose_name = _("Item/user relation")
        verbose_name_plural = _("Item/user relations")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "item"],
                condition=models.Q(user__isnull=False),  # Exclude null users
                name="unique_item_user",
                violation_error_message=_("This user is already in this item."),
            ),
            models.UniqueConstraint(
                fields=["team", "item"],
                condition=models.Q(team__gt=""),  # Exclude empty string teams
                name="unique_item_team",
                violation_error_message=_("This team is already in this item."),
            ),
            models.CheckConstraint(
                condition=models.Q(user__isnull=False, team="")
                | models.Q(user__isnull=True, team__gt=""),
                name="check_item_access_either_user_or_team",
                violation_error_message=_("Either user or team must be set, not both."),
            ),
        ]

    def __str__(self):
        return f"{self.user!s} is {self.role:s} in item {self.item!s}"

    @transaction.atomic
    def save(self, *args, **kwargs):
        """Override save to clear the item's cache for number of accesses."""
        if self.role not in self.item.access_role_choices.values:
            raise ValidationError({"role": "This role is not supported by this resource."})
        if self.item.type == ItemTypeChoices.DOCS:
            Item.objects.select_for_update().get(pk=self.item_id)
        if self.role != RoleChoices.OWNER:
            self._guard_document_owner()
        super().save(*args, **kwargs)
        self.item.invalidate_nb_accesses_cache()

    @transaction.atomic
    def delete(self, *args, **kwargs):
        """Override delete to clear the item's cache for number of accesses."""
        self._guard_document_owner()
        super().delete(*args, **kwargs)
        self.item.invalidate_nb_accesses_cache()

    def _guard_document_owner(self):
        """Serialize owner removal on the document, including concurrent share edits."""
        if self.item.type != ItemTypeChoices.DOCS or self._state.adding:
            return
        Item.objects.select_for_update().get(pk=self.item_id)
        previous = ItemAccess.objects.filter(pk=self.pk).first()
        if previous and previous.role == RoleChoices.OWNER:
            others = ItemAccess.objects.filter(
                item__path__ancestors=self.item.path, role=RoleChoices.OWNER
            ).exclude(pk=self.pk)
            if not others.exists():
                raise ValidationError("A document must retain an owner.")

    @property
    def target_key(self):
        """Get a unique key for the actor targeted by the access, without possible conflict."""
        return f"user:{self.user_id!s}" if self.user_id else f"team:{self.team:s}"

    def _compute_max_ancestors_role(self):
        """
        Compute the max ancestors role for this instance.
        and return a tuple of (max_ancestors_role, item_id)
        """
        ancestors = self.item.ancestors().filter(ancestors_deleted_at__isnull=True)
        filter_condition = models.Q()
        if self.user:
            filter_condition |= models.Q(user=self.user)
        if self.team:
            filter_condition |= models.Q(team=self.team)
        ancestors_roles = ItemAccess.objects.filter(
            filter_condition, item__in=ancestors
        ).values_list("role", "item_id")

        roles = dict(ancestors_roles)

        max_role = self.item.access_role_choices.max(*roles.keys())

        self._max_ancestors_role = max_role
        self._max_ancestors_role_item_id = roles.get(max_role)

    @property
    def max_ancestors_role(self):
        """Link definition equivalent to all document's ancestors."""
        try:
            return self._max_ancestors_role
        except AttributeError:
            pass

        self._compute_max_ancestors_role()

        return self._max_ancestors_role

    @property
    def max_ancestors_role_item_id(self):
        """Get the item_id of the item with the max ancestors role."""
        try:
            return self._max_ancestors_role_item_id
        except AttributeError:
            pass

        self._compute_max_ancestors_role()

        return self._max_ancestors_role_item_id

    @max_ancestors_role.setter
    def max_ancestors_role(self, max_ancestors_role):
        """Cache the max_ancestors_role."""
        self._max_ancestors_role = max_ancestors_role

    @max_ancestors_role_item_id.setter
    def max_ancestors_role_item_id(self, max_ancestors_role_item_id):
        """Cache the max_ancestors_role_item_id."""
        self._max_ancestors_role_item_id = max_ancestors_role_item_id

    def get_role(self, user):
        """Return the role a user has on an item related to this access.."""
        if not user.is_authenticated or not user.is_active:
            return None

        if self.item.type == ItemTypeChoices.DOCS:
            return self.item.get_role(user)
        account = require_access(user)
        if account is not None and request_accounts.get() is None:
            self.__dict__.pop("user_roles", None)
        try:
            roles = self.user_roles or []
        except AttributeError:
            roles = ItemAccess.objects.filter(
                models.Q(user=user) | models.Q(team__in=user.teams),
                item__path__ancestors=self.item.path,
            ).values_list("role", flat=True)

        return self.item.access_role_choices.max(*roles)

    def get_abilities(self, user, is_explicit=True):
        """
        Compute and return abilities for a given user on the item access.
        """
        user_role = (
            self.item.get_role(user)
            if self.item.storage_backend_id or self.item.type == ItemTypeChoices.DOCS
            else self.get_role(user)
        )
        item_abilities = (
            self.item.get_abilities(user)
            if self.item.storage_backend_id or self.item.type == ItemTypeChoices.DOCS
            else None
        )
        is_owner_or_admin = user_role in PRIVILEGED_ROLES and (
            not item_abilities or item_abilities["accesses_manage"]
        )

        if self.role == RoleChoices.OWNER:
            can_delete = user_role == RoleChoices.OWNER and (
                # check if item is not root trying to avoid an extra query
                self.item.depth > 1
                or ItemAccess.objects.filter(item_id=self.item_id, role=RoleChoices.OWNER).count()
                > 1
            )
            set_role_to = self.item.access_role_choices.values if can_delete else []
        else:
            can_delete = is_owner_or_admin
            set_role_to = []
            if is_owner_or_admin:
                set_role_to.extend(
                    role
                    for role in self.item.access_role_choices.values
                    if role != RoleChoices.OWNER
                )
            if user_role == RoleChoices.OWNER:
                set_role_to.append(RoleChoices.OWNER)

        ancestors_role_priority = self.item.access_role_choices.get_priority(
            self.max_ancestors_role
        )
        if is_explicit:
            # Filter out roles that would be lower than the one the user already has
            set_role_to = [
                candidate_role
                for candidate_role in set_role_to
                if self.item.access_role_choices.get_priority(candidate_role)
                >= ancestors_role_priority
            ]
        else:
            set_role_to = [
                candidate_role
                for candidate_role in set_role_to
                if self.item.access_role_choices.get_priority(candidate_role)
                > ancestors_role_priority
            ]

        if item_abilities and not item_abilities["update"]:
            set_role_to = [role for role in set_role_to if role == RoleChoices.READER]

        if self.item.type == ItemTypeChoices.DOCS and not is_owner_or_admin:
            can_delete = False
            set_role_to = []

        return {
            "destroy": can_delete,
            "update": bool(set_role_to) and is_owner_or_admin,
            "partial_update": bool(set_role_to) and is_owner_or_admin,
            "retrieve": (self.user and self.user.id == user.id) or is_owner_or_admin,
            "set_role_to": set_role_to,
        }


class ItemInvitationQuerySet(AnnotateUserRoleQuerySetMixin, models.QuerySet):
    """Custom queryset for ItemInvitation model with additional methods."""

    path_property = "item__path"


class ItemInvitationManager(models.Manager.from_queryset(ItemInvitationQuerySet)):
    """Manager for ItemAccess model."""


class Invitation(BaseModel):
    """User invitation to an item."""

    email = models.EmailField(_("email address"), null=False, blank=False)
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    role = models.CharField(
        max_length=20, choices=DocumentRoleChoices.choices, default=RoleChoices.READER
    )
    issuer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="invitations",
        blank=True,
        null=True,
    )

    objects = ItemInvitationManager()

    class Meta:
        db_table = "drive_invitation"
        verbose_name = _("Item invitation")
        verbose_name_plural = _("Item invitations")
        constraints = [
            models.UniqueConstraint(
                fields=["email", "item"],
                name="email_and_item_unique_together",
            )
        ]

    def __str__(self):
        return f"{self.email} invited to {self.item}"

    def save(self, *args, **kwargs):
        """Keep comment-only invitations confined to native documents."""
        if self.role not in self.item.access_role_choices.values:
            raise ValidationError({"role": "This role is not supported by this resource."})
        return super().save(*args, **kwargs)

    def clean(self):
        """Validate fields."""
        super().clean()

        # Check if an identity already exists for the provided email
        if (
            self.item.type != ItemTypeChoices.DOCS
            and User.objects.filter(email__iexact=self.email).exists()
            and not settings.OIDC_ALLOW_DUPLICATE_EMAILS
        ):
            raise ValidationError(
                {
                    "email": ValidationError(
                        "This email is already associated to a registered user.",
                        code="invitation_email_already_registered",
                    )
                }
            )

    @property
    def is_expired(self):
        """Calculate if invitation is still valid or has expired."""
        if not self.created_at:
            return None

        if self.item.type == ItemTypeChoices.DOCS and hasattr(self, "docs_state"):
            expires = self.docs_state.context.get("expires")
            if not isinstance(expires, (int, float)):
                return True
            return timezone.now().timestamp() >= expires

        validity_duration = timedelta(seconds=settings.INVITATION_VALIDITY_DURATION)
        return timezone.now() > (self.created_at + validity_duration)

    def get_role(self, user):
        """Return the role a user has on an item related to this access.."""
        if not user.is_authenticated or not user.is_active:
            return None

        if self.item.type == ItemTypeChoices.DOCS:
            return self.item.get_role(user)
        account = require_access(user)
        if account is not None and request_accounts.get() is None:
            self.__dict__.pop("user_roles", None)
        try:
            roles = self.user_roles or []
        except AttributeError:
            roles = ItemAccess.objects.filter(
                models.Q(user=user) | models.Q(team__in=user.teams),
                item__path__ancestors=self.item.path,
            ).values_list("role", flat=True)

        return self.item.access_role_choices.max(*roles)

    def get_abilities(self, user):
        """Compute and return abilities for a given user."""
        user_role = (
            self.item.get_role(user)
            if self.item.storage_backend_id or self.item.type == ItemTypeChoices.DOCS
            else self.get_role(user)
        )
        is_owner_or_admin = user_role in PRIVILEGED_ROLES and (
            not (self.item.storage_backend_id or self.item.type == ItemTypeChoices.DOCS)
            or self.item.get_abilities(user)["accesses_manage"]
        )

        return {
            "destroy": is_owner_or_admin,
            "update": is_owner_or_admin,
            "partial_update": is_owner_or_admin,
            "retrieve": is_owner_or_admin,
        }


class DocsInvitation(BaseModel):
    """Explicit acceptance and delivery state, without changing legacy invitations."""

    invitation = models.OneToOneField(
        Invitation, on_delete=models.CASCADE, related_name="docs_state"
    )
    context = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(
                fields=["updated_at"],
                name="docs_invite_delivery",
                condition=models.Q(context__delivery="queued"),
            ),
        ]

    def __str__(self):
        return f"Docs invitation {self.invitation_id}"


class MountShareLink(BaseModel):
    """Share link mapping for MountProvider virtual entries."""

    token = models.CharField(max_length=128, unique=True)
    mount_id = models.CharField(max_length=64, db_index=True)
    normalized_path = models.TextField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mount_share_links",
    )

    resource = models.ForeignKey(
        "StorageResource",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="share_links",
    )

    class Meta:
        db_table = "drive_mount_share_link"
        verbose_name = _("Mount share link")
        verbose_name_plural = _("Mount share links")
        constraints = [
            models.UniqueConstraint(
                fields=["mount_id", "normalized_path"],
                condition=models.Q(resource__isnull=True),
                name="mount_share_link_mount_id_path_unique",
            ),
        ]

    def __str__(self):
        return f"MountShareLink(mount_id={self.mount_id}, id={self.id})"


def _storage_root(value):
    """Validate configuration paths before they can define an authorization root."""
    try:
        path = normalize_mount_path(value)
    except MountPathNormalizationError as exc:
        raise ValidationError(str(exc)) from exc
    if any(
        ":" in part or part.endswith((".", " ")) or part.startswith(".drive-txn-")
        for part in path.split("/")
        if part
    ):
        raise ValidationError("Storage paths cannot contain aliases or reserved transaction names.")
    return path


class StorageBackend(BaseModel):
    """Stable storage connection; secrets are encrypted outside public configuration."""

    registry_id = models.CharField(max_length=64, unique=True)
    family = models.CharField(
        max_length=8, choices=[("mount", "MountProvider"), ("s3", "S3")], default="mount"
    )
    configuration = models.JSONField(default=dict, blank=True)
    secret_ciphertext = models.TextField(blank=True, default="", editable=False)
    configuration_generation = models.PositiveBigIntegerField(default=1)
    managed = models.BooleanField(default=False)
    legacy_s3 = models.BooleanField(default=False)
    connection_checked_at = models.DateTimeField(null=True, blank=True)
    connection_status = models.CharField(max_length=32, default="unchecked")
    name = models.CharField(max_length=255)
    organization = models.CharField(max_length=255)
    # Connections exposing the same files must explicitly share this identity.
    namespace = models.UUIDField(default=uuid.uuid4, db_index=True)
    namespace_root = models.TextField(default="/")
    enabled = models.BooleanField(default=True)
    capacity = models.JSONField(default=dict, blank=True)
    inventory_completed_at = models.DateTimeField(null=True, blank=True)
    inventory_generation = models.UUIDField(null=True, blank=True)
    maintenance = models.BooleanField(default=False)
    attribution_pending = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def clean(self):
        self.namespace_root = _storage_root(self.namespace_root)
        if self.managed:
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.services.storage_connections import validate_configuration  # noqa: PLC0415

            validate_configuration(self)
        if (
            StorageBackend.objects.filter(namespace=self.namespace)
            .exclude(pk=self.pk)
            .exclude(organization=self.organization)
            .exists()
        ):
            raise ValidationError("Connections to one namespace must use the same organization.")
        if (
            StorageBackend.objects.filter(namespace=self.namespace)
            .exclude(pk=self.pk)
            .exclude(family=self.family)
            .exists()
        ):
            raise ValidationError("Connections to one namespace must use the same storage family.")
        previous = StorageBackend.objects.filter(pk=self.pk).first()
        if (
            previous
            and (
                previous.configuration != self.configuration
                or previous.secret_ciphertext != self.secret_ciphertext
            )
            and StorageReservation.objects.filter(
                models.Q(publication__connection_id=str(self.pk))
                | models.Q(publication__source_connection_id=str(self.pk))
                | models.Q(publication__backend_id=str(self.pk)),
                state__in=["reserved", "writing", "publishing"],
            ).exists()
        ):
            raise ValidationError("Reconcile active operations before changing this connection.")
        if (
            previous
            and any(
                getattr(previous, field) != getattr(self, field)
                for field in (
                    "configuration",
                    "secret_ciphertext",
                    "enabled",
                    "namespace",
                    "namespace_root",
                    "organization",
                    "family",
                    "registry_id",
                    "managed",
                    "legacy_s3",
                )
            )
            and StorageAdminJob.objects.filter(
                backend__namespace=previous.namespace, state="running"
            ).exists()
        ):
            raise ValidationError(
                "Wait for storage administration to finish before changing this connection."
            )
        identity_fields = (
            "registry_id",
            "organization",
            "namespace",
            "namespace_root",
            "family",
            "legacy_s3",
        )
        if (
            previous
            and (StorageUsage.objects.filter(backend=self).exists() or self.items.exists())
            and any(getattr(previous, field) != getattr(self, field) for field in identity_fields)
        ):
            raise ValidationError(
                "An inventoried connection's identity is immutable; "
                "register and qualify a new connection for migration."
            )
        if self.attribution_pending and not self.maintenance:
            raise ValidationError("Reconcile storage attribution before leaving maintenance.")
        if self.legacy_s3 and self.family != "s3":
            raise ValidationError("Only an S3 connection can represent historical objects.")
        if (
            previous
            and previous.configuration != self.configuration
            and (
                self.items.exists()
                or StorageUsage.objects.filter(backend__namespace=self.namespace).exists()
                or StorageResource.objects.filter(namespace=self.namespace).exists()
            )
        ):
            if self.family == "s3":
                changed = any(
                    previous.configuration.get(key) != self.configuration.get(key)
                    for key in ("endpoint_url", "bucket_name", "prefix")
                )
            else:
                # Credentials and declared capabilities can change without moving the namespace.
                editable = {"username", "domain", "capabilities", "read_only"}
                before = {
                    key: value
                    for key, value in previous.configuration.get("params", {}).items()
                    if key not in editable
                }
                after = {
                    key: value
                    for key, value in self.configuration.get("params", {}).items()
                    if key not in editable
                }
                changed = before != after or previous.configuration.get(
                    "provider"
                ) != self.configuration.get("provider")
            if changed:
                raise ValidationError(
                    "Transfer existing resources before changing their physical destination."
                )


class StorageSpace(BaseModel):
    """A logical root on S3 or MountProvider, independent of technical credentials."""

    backend = models.ForeignKey(StorageBackend, on_delete=models.PROTECT, related_name="spaces")
    name = models.CharField(max_length=255)
    root_path = models.TextField(default="/")
    root_item = models.OneToOneField(
        Item, on_delete=models.PROTECT, null=True, blank=True, related_name="root_storage_space"
    )
    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="storage_spaces"
    )
    enabled = models.BooleanField(default=True)
    attribute_to_creator = models.BooleanField(default=False)
    explicit_access = models.BooleanField(default=False)
    allow_sharing = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Fence ownership/root changes until their byte attribution is reconciled."""
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_namespace import namespace_guard  # noqa: PLC0415

        previous = StorageSpace.objects.filter(pk=self.pk).first()
        changed = previous is None or any(
            getattr(previous, field) != getattr(self, field)
            for field in ("backend_id", "root_path", "owner_id", "attribute_to_creator")
        )
        if not changed:
            super().save(*args, **kwargs)
            return
        if previous and previous.backend_id != self.backend_id:
            raise ValidationError("Create a new space when changing its connection.")
        with (
            namespace_guard(self.backend, exclusive=True, allow_maintenance=True),
            transaction.atomic(),
        ):
            populated = (
                StorageUsage.objects.filter(backend__namespace=self.backend.namespace).exists()
                if self.backend.family == "mount"
                else bool(
                    self.root_item_id
                    and (
                        self.root_item.storage_space_id
                        or Item.objects.filter(path__descendants=self.root_item.path)
                        .exclude(pk=self.root_item_id)
                        .exists()
                    )
                )
            )
            if (
                populated
                and not StorageBackend.objects.filter(pk=self.backend_id, maintenance=True).exists()
            ):
                raise ValidationError(
                    "Put this storage namespace in maintenance before changing its spaces."
                )
            super().save(*args, **kwargs)
            if populated:
                StorageBackend.objects.filter(namespace=self.backend.namespace).update(
                    attribution_pending=True, maintenance=True
                )

    def clean(self):
        self.root_path = _storage_root(self.root_path)
        if self.root_item_id and (
            self.backend.family != "s3"
            or (self.root_item.type != ItemTypeChoices.FOLDER and not self.backend.legacy_s3)
            or self.root_item.storage_backend_id != self.backend_id
        ):
            raise ValidationError("The logical root must be a folder on this connection.")
        if self.owner_id and self.attribute_to_creator:
            raise ValidationError("Choose a fixed owner or creator attribution.")
        if not self.backend_id:
            return
        previous = StorageSpace.objects.filter(pk=self.pk).first()
        if previous and previous.backend_id != self.backend_id:
            raise ValidationError("Create a new space when changing its connection.")
        if previous and previous.root_item_id != self.root_item_id:
            raise ValidationError("A space's logical root is immutable.")
        changed = previous is None or any(
            getattr(previous, field) != getattr(self, field)
            for field in ("root_path", "owner_id", "attribute_to_creator")
        )
        if (
            changed
            and StorageAdminJob.objects.filter(
                backend__namespace=self.backend.namespace, state="running"
            ).exists()
        ):
            raise ValidationError(
                "Wait for storage administration to finish before changing its roots."
            )
        if (
            changed
            and not StorageBackend.objects.filter(pk=self.backend_id, maintenance=True).exists()
            and (
                StorageUsage.objects.filter(backend__namespace=self.backend.namespace).exists()
                if self.backend.family == "mount"
                else bool(
                    self.root_item_id
                    and (
                        self.root_item.storage_space_id
                        or Item.objects.filter(path__descendants=self.root_item.path)
                        .exclude(pk=self.root_item_id)
                        .exists()
                    )
                )
            )
        ):
            raise ValidationError(
                "Put this storage namespace in maintenance before changing its spaces."
            )


class StorageInventoryEntry(models.Model):
    """Bounded metadata staging; resolve native identities after a complete scan."""

    namespace = models.UUIDField(db_index=True)
    native_key = models.CharField(max_length=64, db_index=True)
    record = models.JSONField()

    def __str__(self):
        return self.native_key


class StorageResource(BaseModel):
    """Mounted metadata and retained link identities; regular contents always use Item/S3."""

    namespace = models.UUIDField(db_index=True)
    identity_key = models.CharField(max_length=64, unique=True)
    provider_identity = models.CharField(max_length=255, blank=True)
    path = models.TextField()
    parent_path = models.TextField(db_index=True)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=8, choices=[("file", "File"), ("folder", "Folder")])
    size = models.PositiveBigIntegerField(default=0)
    modified_at = models.DateTimeField(null=True, blank=True)
    version = models.CharField(max_length=255, blank=True)
    generation = models.UUIDField(null=True, blank=True)
    missing = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["namespace", "parent_path", "name"])]

    def __str__(self):
        return str(self.pk)


class DocsBinding(BaseModel):
    """A live Docs document, its placement and its durable synchronization state."""

    item = models.OneToOneField(
        Item, on_delete=models.SET_NULL, null=True, blank=True, related_name="docs_binding"
    )
    document_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    request_key = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    request_hash = models.CharField(max_length=64, blank=True)
    sort_order = models.BigIntegerField(default=0)
    mounted_parent = models.ForeignKey(
        StorageResource,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="docs_documents",
    )
    anchor_space = models.ForeignKey(
        StorageSpace,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="docs_documents",
    )
    revision = models.PositiveBigIntegerField(default=1)
    applied_revision = models.PositiveBigIntegerField(default=0)
    state = models.CharField(
        max_length=12,
        choices=[
            ("pending", "Pending"),
            ("preparing", "Preparing content"),
            ("active", "Active"),
            ("trash", "Trash"),
            ("purging", "Purging"),
            ("purged", "Purged"),
        ],
        default="pending",
    )
    retry_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=100, blank=True)
    creation_context = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(mounted_parent__isnull=True, anchor_space__isnull=True)
                    | models.Q(mounted_parent__isnull=False, anchor_space__isnull=False)
                ),
                name="docs_mount_anchor_pair",
            ),
            models.CheckConstraint(
                condition=models.Q(item__isnull=False) | models.Q(state="purged"),
                name="docs_binding_retained_until_purged",
            ),
        ]
        indexes = [
            models.Index(fields=["state", "retry_at"]),
            models.Index(
                fields=["created_at", "id"],
                condition=models.Q(applied_revision__lt=models.F("revision")),
                name="docs_pending_metadata",
            ),
        ]

    def __str__(self):
        return str(self.document_id)

    def clean(self):
        """A delayed exchange cannot rebind an identity or resurrect a tombstone."""
        super().clean()
        if self.applied_revision > self.revision:
            raise ValidationError("Applied revision cannot exceed the desired revision.")
        if not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if (previous.document_id, previous.request_key) != (self.document_id, self.request_key):
                raise ValidationError("Document identities are immutable.")
            if self.revision < previous.revision or (
                previous.state == "purged" and self.state != "purged"
            ):
                raise ValidationError("An obsolete document state cannot be restored.")
        if self.item_id and self.item.type != ItemTypeChoices.DOCS:
            raise ValidationError("A Docs binding requires a Docs item.")
        if self.mounted_parent_id:
            if not self.anchor_space_id or self.anchor_space.backend.family != "mount":
                raise ValidationError("Choose a mounted space for this document anchor.")
            if self.mounted_parent.kind != "folder":
                raise ValidationError("A document anchor must be a folder.")
            if self.mounted_parent.namespace != self.anchor_space.backend.namespace:
                raise ValidationError("The folder does not belong to this storage connection.")
            if self.item_id and not self.item.is_root:
                raise ValidationError("Only a document root can have a mounted anchor.")


class DocsCommand(BaseModel):
    """A committed user command can be acknowledged again after a lost response."""

    binding = models.ForeignKey(DocsBinding, on_delete=models.PROTECT, related_name="commands")
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    request_hash = models.CharField(max_length=64)
    revision = models.PositiveBigIntegerField()

    def __str__(self):
        return str(self.pk)


class StorageResourceFavorite(BaseModel):
    """Mounted favorites retain their identity across native renames."""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    resource = models.ForeignKey(StorageResource, on_delete=models.CASCADE)
    space = models.ForeignKey(StorageSpace, on_delete=models.SET_NULL, null=True, blank=True)
    last_opened_at = models.DateTimeField(null=True, blank=True)
    favorite = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "resource"], name="storage_resource_user")
        ]

    def __str__(self):
        return str(self.pk)


class StorageGrant(BaseModel):
    """An additive permission on a virtual root or one of its subdirectories."""

    space = models.ForeignKey(StorageSpace, on_delete=models.CASCADE, related_name="grants")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    team = models.CharField(max_length=255, blank=True, default="")
    path = models.TextField(default="/")
    writable = models.BooleanField(default=False)
    shareable = models.BooleanField(default=False)
    manageable = models.BooleanField(default=False)
    root_item = models.ForeignKey(Item, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, team="")
                    | (models.Q(user__isnull=True) & ~models.Q(team=""))
                ),
                name="storage_grant_one_principal",
            ),
        ]

    def __str__(self):
        return f"{self.space_id}: {self.user_id or self.team}"

    def clean(self):
        self.path = _storage_root(self.path)
        if self.manageable and (
            self.path != "/" or self.root_item_id not in (None, self.space.root_item_id)
        ):
            raise ValidationError("Space management requires a grant on the entire space.")
        if self.space.backend.family == "s3":
            if self.path != "/":
                raise ValidationError("Choose a logical folder for an S3 subtree grant.")
            if self.root_item_id and (
                self.root_item.storage_backend_id != self.space.backend_id
                or not self.space.root_item_id
                or list(self.root_item.path[: self.space.root_item.depth])
                != list(self.space.root_item.path)
            ):
                raise ValidationError("Choose a folder belonging to this space.")
        elif self.root_item_id:
            raise ValidationError("Mounted grants use a relative path.")


class StorageQuota(BaseModel):
    """A logical-byte budget. NULL is unlimited; zero permits no positive growth."""

    key = models.CharField(max_length=255, unique=True)
    limit_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    growth_blocked = models.BooleanField(default=False)
    used_bytes = models.PositiveBigIntegerField(default=0)
    reserved_bytes = models.PositiveBigIntegerField(default=0)
    policy_revision = models.CharField(max_length=64, blank=True, default="")
    policy_origin = models.CharField(max_length=255, blank=True, default="")
    policy_version = models.PositiveBigIntegerField(default=0)
    policy_applied_at = models.DateTimeField(null=True, blank=True)
    accounting_ready_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.key


class StorageUsage(BaseModel):
    """One canonical logical object, with stable attribution and quota scopes."""

    key = models.CharField(max_length=64, unique=True)
    native_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    item = models.OneToOneField(Item, on_delete=models.SET_NULL, null=True, blank=True)
    backend = models.ForeignKey(StorageBackend, on_delete=models.PROTECT, null=True, blank=True)
    space = models.ForeignKey(StorageSpace, on_delete=models.PROTECT, null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    organization = models.CharField(max_length=255)
    path = models.TextField(blank=True, default="")
    provider_identity = models.CharField(max_length=255, blank=True, default="")
    size = models.PositiveBigIntegerField(default=0)
    version = models.CharField(max_length=255, blank=True, default="")
    scope_keys = models.JSONField(default=list)
    observed_at = models.DateTimeField(auto_now=True)
    scan_generation = models.UUIDField(null=True, blank=True, db_index=True)
    attribution_conflict = models.BooleanField(default=False)

    def __str__(self):
        return self.key


class StorageReservation(BaseModel):
    """Durable admission and publication state for one storage mutation."""

    class State(models.TextChoices):
        """Durable stages of admission and publication."""

        RESERVED = "reserved", "Reserved"
        WRITING = "writing", "Writing"
        PUBLISHING = "publishing", "Publishing"
        COMMITTED = "committed", "Committed"
        CANCELLED = "cancelled", "Cancelled"

    resource_key = models.CharField(max_length=64, db_index=True)
    publication_key = models.CharField(max_length=64, blank=True, default="")
    actor = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    state = models.CharField(max_length=16, choices=State, default=State.RESERVED)
    scope_keys = models.JSONField(default=list)
    target_scope_keys = models.JSONField(default=list, blank=True)
    scope_reservations = models.JSONField(default=dict, blank=True)
    policy_revisions = models.JSONField(default=dict, blank=True)
    previous_size = models.PositiveBigIntegerField(default=0)
    reserved_bytes = models.PositiveBigIntegerField(default=0)
    expected_version = models.CharField(max_length=255, blank=True, default="")
    expires_at = models.DateTimeField()
    publication = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["resource_key"],
                condition=models.Q(state__in=["reserved", "writing", "publishing"]),
                name="storage_one_active_publication",
            ),
            models.UniqueConstraint(
                fields=["publication_key"],
                condition=models.Q(state__in=["reserved", "writing", "publishing"])
                & ~models.Q(publication_key=""),
                name="storage_one_active_path_publication",
            ),
        ]

    def __str__(self):
        return f"{self.pk}: {self.state}"


class StorageTransferEntry(BaseModel):
    """Bounded, resumable metadata transfer for a folder or ownership change."""

    operation = models.ForeignKey(
        StorageReservation, on_delete=models.CASCADE, related_name="transfer_entries"
    )
    usage = models.ForeignKey(StorageUsage, on_delete=models.PROTECT)
    size = models.PositiveBigIntegerField()
    source_scopes = models.JSONField(default=list)
    target_scopes = models.JSONField(default=list)
    target_attribution = models.JSONField(default=dict)
    applied = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["operation", "usage"], name="storage_transfer_unique_usage"
            )
        ]

    def __str__(self):
        return f"{self.operation_id}: {self.usage_id}"


class StorageMoveJob(BaseModel):
    """Durable folder moves, retried by workers without extending HTTP requests."""

    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    kind = models.CharField(max_length=32, default="native_move")
    payload = models.JSONField(default=dict, blank=True)
    space = models.ForeignKey(StorageSpace, on_delete=models.PROTECT)
    source_path = models.TextField()
    destination_path = models.TextField()
    source_identity = models.CharField(max_length=255)
    operation = models.OneToOneField(
        StorageReservation, on_delete=models.SET_NULL, null=True, blank=True
    )
    state = models.CharField(
        max_length=16,
        default="queued",
        db_index=True,
        choices=[
            (state, state)
            for state in ("queued", "running", "cleanup", "conflict", "done", "failed")
        ],
    )
    reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "space", "source_path", "destination_path", "kind"],
                condition=models.Q(state__in=["queued", "running", "cleanup", "conflict"]),
                name="storage_one_active_move_request",
            )
        ]

    def __str__(self):
        return f"{self.pk}: {self.state}"


class StorageCopyEntry(BaseModel):
    """Bounded folder manifests retain each source and its latest publication job."""

    job = models.ForeignKey(StorageMoveJob, on_delete=models.PROTECT, related_name="copy_entries")
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True)
    source = models.JSONField()
    source_id = models.UUIDField()
    kind = models.CharField(max_length=16)
    name = models.CharField(max_length=255)
    target_id = models.UUIDField(null=True, blank=True)
    publication = models.JSONField(default=dict, blank=True)
    child_job = models.ForeignKey(
        StorageMoveJob,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="folder_entries",
    )
    enumerated = models.BooleanField(default=False)
    done = models.BooleanField(default=False, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "source_id"], name="storage_copy_source_once")
        ]

    def __str__(self):
        return f"{self.job_id}: {self.source_id}"


class StorageAdminJob(BaseModel):
    """Durable administrative work whose retries do not depend on broker delivery."""

    backend = models.ForeignKey(StorageBackend, on_delete=models.PROTECT)
    space = models.ForeignKey(StorageSpace, on_delete=models.PROTECT, null=True, blank=True)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    kind = models.CharField(
        max_length=32,
        choices=[(name, name) for name in ("inventory", "reclassify", "root", "restore")],
    )
    source_operation = models.ForeignKey(
        StorageReservation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="restore_jobs",
    )
    operation = models.OneToOneField(
        StorageReservation, on_delete=models.PROTECT, null=True, blank=True
    )
    request_key = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    state = models.CharField(
        max_length=16,
        default="queued",
        db_index=True,
        choices=[(name, name) for name in ("queued", "running", "done", "failed")],
    )
    reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["request_key"],
                condition=models.Q(state__in=["queued", "running"]),
                name="storage_one_active_admin_request",
            )
        ]

    def __str__(self):
        return f"{self.kind}: {self.state}"
