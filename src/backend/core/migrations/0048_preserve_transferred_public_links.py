"""A folder move preserves links created on both its source and staged destination."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0047_resource_favorites_across_views")]

    operations = [
        migrations.RemoveConstraint(
            model_name="mountsharelink",
            name="mount_share_link_resource_creator_unique",
        ),
    ]
