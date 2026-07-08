"""Add user column preferences."""

import core.models
import django.core.serializers.json
import django_pydantic_field.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_reconcile_model_state_drift"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="column_preferences",
            field=django_pydantic_field.fields.PydanticSchemaField(
                blank=True,
                config=None,
                default=None,
                encoder=django.core.serializers.json.DjangoJSONEncoder,
                null=True,
                schema=core.models.ColumnPreferences,
            ),
        ),
    ]
