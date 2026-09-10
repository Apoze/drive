"""Keep old URLs valid until explicit transfer revocation."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0048_preserve_transferred_public_links")]
    operations = [
        migrations.AddField(
            model_name="item",
            name="share_link_nonce",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
    ]
