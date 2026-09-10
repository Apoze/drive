"""Reconcile People once; scheduled by the existing application's task runner."""

from django.core.management.base import BaseCommand, CommandError

from suite_identity.directory import SnapshotError, synchronize


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        try:
            revision = synchronize()
        except SnapshotError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(f"Directory revision {revision} applied.")
