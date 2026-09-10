from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("suite_identity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="policy_observed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
