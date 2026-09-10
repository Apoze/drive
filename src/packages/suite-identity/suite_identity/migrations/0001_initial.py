import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        primary_key=True,
                        related_name="suite_account",
                        serialize=False,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("principal_id", models.UUIDField(unique=True)),
                ("organization_id", models.UUIDField(db_index=True)),
                ("active", models.BooleanField(default=False)),
                ("session_version", models.PositiveBigIntegerField(default=0)),
                ("group_ids", models.JSONField(blank=True, default=list)),
                ("revision", models.PositiveBigIntegerField(default=0)),
                ("checked_at", models.DateTimeField(blank=True, null=True)),
                ("policy_allowed", models.BooleanField(default=False)),
                ("policy_checked_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="DirectoryState",
            fields=[
                (
                    "organization_id",
                    models.UUIDField(primary_key=True, serialize=False),
                ),
                ("revision", models.PositiveBigIntegerField(default=0)),
                ("checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, max_length=80)),
            ],
        ),
        migrations.CreateModel(
            name="GroupMapping",
            fields=[
                ("group_id", models.UUIDField(primary_key=True, serialize=False)),
                ("organization_id", models.UUIDField(db_index=True)),
                ("display_name", models.CharField(max_length=150)),
                ("active", models.BooleanField(default=True)),
                (
                    "local_group",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT, to="auth.group"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="IdentityBinding",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "issuer",
                    models.CharField(
                        max_length=512,
                        validators=[
                            django.core.validators.URLValidator(
                                schemes=["https", "http"]
                            )
                        ],
                    ),
                ),
                ("subject", models.CharField(max_length=255)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="suite_identities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("issuer", "subject"), name="suite_unique_identity"
                    )
                ],
            },
        ),
    ]
