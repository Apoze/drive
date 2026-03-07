from django.db import migrations
from django.db.models import F
from django.db.models.indexes import Index
from django_ltree.functions import NLevel


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0021_mount_share_link"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="item",
            index=Index(
                NLevel(F("path")),
                name="drive_item_path_nlevel_idx",
            ),
        ),
    ]
