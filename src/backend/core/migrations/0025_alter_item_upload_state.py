"""Reconcile item upload state choices."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0024_user_column_preferences"),
    ]

    operations = [
        migrations.AlterField(
            model_name="item",
            name="upload_state",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", "Pending"),
                    ("creating", "Creating"),
                    ("expired", "Expired"),
                    ("duplicating", "Duplicating"),
                    ("analyzing", "Analyzing"),
                    ("suspicious", "Suspicious"),
                    (
                        "file_too_large_to_analyze",
                        "File too large to analyze",
                    ),
                    ("ready", "Ready"),
                ],
                max_length=25,
                null=True,
            ),
        ),
    ]
