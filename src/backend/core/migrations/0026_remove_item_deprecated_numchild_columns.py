"""Drop deprecated item child-count columns."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0025_alter_item_upload_state"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="item",
            name="_deprecated_numchild",
        ),
        migrations.RemoveField(
            model_name="item",
            name="_deprecated_numchild_folder",
        ),
    ]
