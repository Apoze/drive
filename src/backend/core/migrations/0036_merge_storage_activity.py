"""Join the independently qualified storage and activity schemas."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0031_itemactivity"),
        ("core", "0035_storage_move_jobs"),
    ]

    operations = []
