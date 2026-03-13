"""Reconcile Django migration state with current core models."""

from __future__ import annotations

import uuid

from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_item_path_nlevel_idx"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name="item",
                    name="numchild",
                ),
                migrations.RemoveField(
                    model_name="item",
                    name="numchild_folder",
                ),
                migrations.AddField(
                    model_name="item",
                    name="_deprecated_numchild",
                    field=models.PositiveIntegerField(
                        db_column="numchild",
                        default=0,
                    ),
                ),
                migrations.AddField(
                    model_name="item",
                    name="_deprecated_numchild_folder",
                    field=models.PositiveIntegerField(
                        db_column="numchild_folder",
                        default=0,
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="item",
            name="upload_state",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", _("Pending")),
                    ("creating", _("Creating")),
                    ("expired", _("Expired")),
                    ("analyzing", _("Analyzing")),
                    ("suspicious", _("Suspicious")),
                    (
                        "file_too_large_to_analyze",
                        _("File too large to analyze"),
                    ),
                    ("ready", _("Ready")),
                ],
                max_length=25,
                null=True,
            ),
        ),
        migrations.AlterModelOptions(
            name="mountsharelink",
            options={
                "verbose_name": "Mount share link",
                "verbose_name_plural": "Mount share links",
            },
        ),
        migrations.AlterField(
            model_name="mountsharelink",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                help_text="primary key for the record as UUID",
                primary_key=True,
                serialize=False,
                verbose_name="id",
            ),
        ),
        migrations.AlterField(
            model_name="mountsharelink",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                editable=False,
                help_text="date and time at which a record was created",
                verbose_name="created on",
            ),
        ),
        migrations.AlterField(
            model_name="mountsharelink",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                editable=False,
                help_text="date and time at which a record was last updated",
                verbose_name="updated on",
            ),
        ),
    ]
