"""Refresh ST policy without extending the lifetime of the People projection."""

from django.core.management.base import BaseCommand, CommandError

from suite_identity.directory import SnapshotError
from suite_identity.policy import synchronize_policy


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        try:
            count = synchronize_policy()
        except SnapshotError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(f"Application access verified for {count} principals.")
