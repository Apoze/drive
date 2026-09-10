from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("suite_identity", "0002_account_policy_observed_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="auth_not_before",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
