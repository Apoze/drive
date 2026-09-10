"""Inspect or migrate storage metadata without copying file contents."""

import json

from django.core.management.base import BaseCommand, CommandError

from core.services.storage_migration import migrate_storage, migration_report
from core.services.storage_namespace import advisory_guard
from core.services.storage_quota import StorageWriteConflict


class Command(BaseCommand):
    """Default to a no-write dry run; application requires drained, fenced writers."""

    help = "Report unified-storage migration or apply its repeatable metadata backfill."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            with advisory_guard("storage-unified-migration"):
                report = migrate_storage() if options["apply"] else migration_report()
        except StorageWriteConflict as exc:
            raise CommandError(str(exc.detail)) from None
        self.stdout.write(json.dumps(report, sort_keys=True))
