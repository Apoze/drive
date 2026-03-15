"""E2E fixture search."""

from django.core.management.base import BaseCommand

from e2e.services.bootstrap import seed_search_dataset
from e2e.utils import ensure_main_workspace, get_or_create_e2e_user


class Command(BaseCommand):
    """E2E fixture search."""

    help = "Generates E2E search fixtures."

    def handle(self, *args, **options):
        """E2E fixture search."""
        user = get_or_create_e2e_user("drive@example.com")
        workspace = ensure_main_workspace(user)

        # Create items under the user's main workspace so they are visible in "My files"
        # and discoverable through the default explorer/search scope.
        for item in seed_search_dataset(parent=workspace, creator=user):
            self.stdout.write(f"Item created or reused: {item.title}")
