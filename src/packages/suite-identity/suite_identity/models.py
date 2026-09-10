"""Additive associations: never replace application user IDs or content ownership."""

import uuid

from django.conf import settings
from django.core.validators import URLValidator
from django.db import models


class Account(models.Model):
    """A local user associated with the durable People principal."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="suite_account",
    )
    principal_id = models.UUIDField(unique=True)
    organization_id = models.UUIDField(db_index=True)
    active = models.BooleanField(default=False)
    session_version = models.PositiveBigIntegerField(default=0)
    auth_not_before = models.DateTimeField(null=True, blank=True)
    group_ids = models.JSONField(default=list, blank=True)
    revision = models.PositiveBigIntegerField(default=0)
    checked_at = models.DateTimeField(null=True, blank=True)
    policy_allowed = models.BooleanField(default=False)
    policy_checked_at = models.DateTimeField(null=True, blank=True)
    policy_observed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return str(self.principal_id)


class IdentityBinding(models.Model):
    """A verified external subject belongs to exactly one local account."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="suite_identities",
    )
    issuer = models.CharField(max_length=512, validators=[URLValidator(schemes=["https", "http"])])
    subject = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["issuer", "subject"], name="suite_unique_identity")
        ]

    def __str__(self):
        return str(self.id)


class GroupMapping(models.Model):
    """People group UUID mapped to an existing local Django group ID."""

    group_id = models.UUIDField(primary_key=True)
    organization_id = models.UUIDField(db_index=True)
    local_group = models.OneToOneField("auth.Group", on_delete=models.PROTECT)
    display_name = models.CharField(max_length=150)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.display_name


class DirectoryState(models.Model):
    """Only a complete authoritative read advances the directory checkpoint."""

    organization_id = models.UUIDField(primary_key=True)
    revision = models.PositiveBigIntegerField(default=0)
    checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return str(self.organization_id)
