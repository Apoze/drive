"""Initialize native S3 accounting and reconcile configured NAS connections."""

import json

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from botocore.exceptions import ClientError

from core.models import Item, ItemUploadStateChoices, StorageBackend, StorageReservation
from core.services.storage_inventory import audit_accounting, initialize_items, scan_backend
from core.services.storage_recovery import (
    cleanup_candidates,
    cleanup_operation,
    reconcile_expired_operations,
    reconcile_operation,
    restore_backup,
)
from core.services.storage_s3_write import object_head


class Command(BaseCommand):
    """Inventory is read-only; explicit recovery options operate on journalled files."""

    help = "Initialize S3 accounting, scan NAS metadata, or list unresolved publications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ensure-bucket",
            action="store_true",
            help="Create a missing S3 bucket; preserve existing settings.",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Audit counters and readiness during a write-free activation window.",
        )
        parser.add_argument(
            "--verify-items",
            action="store_true",
            help="Compare historical S3 object sizes with Item metadata, without reading contents.",
        )
        parser.add_argument("--initialize-items", action="store_true")
        parser.add_argument("--backend", help="StorageBackend UUID to scan.")
        parser.add_argument("--all-backends", action="store_true")
        parser.add_argument("--pending", action="store_true")
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Clean expired private copies and abandoned transfers.",
        )
        parser.add_argument(
            "--restore", help="Committed StorageReservation UUID whose backup will be restored."
        )
        parser.add_argument("--space", help="Authorized destination StorageSpace UUID.")
        parser.add_argument(
            "--destination", help="New virtual destination path; existing files are never replaced."
        )
        parser.add_argument(
            "--actor", help="Active superuser UUID, also granted access to the destination space."
        )
        parser.add_argument(
            "--recover",
            action="store_true",
            help="Reconcile expired operations without guessing uncertain outcomes.",
        )

    # Independent explicitly requested command options.
    # pylint: disable-next=too-many-branches
    def handle(self, *args, **options):  # noqa: PLR0912
        if options["ensure_bucket"]:
            client = default_storage.connection.meta.client
            try:
                client.head_bucket(Bucket=default_storage.bucket_name)
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in {"404", "NoSuchBucket"}:
                    raise CommandError(
                        "S3 bucket is not accessible; no configuration changed."
                    ) from None
                client.create_bucket(Bucket=default_storage.bucket_name)
            self.stdout.write("S3 bucket available; existing settings preserved.")
        if options["restore"]:
            if not all(options[key] for key in ("space", "destination", "actor")):
                raise CommandError("Restoration requires --space, --destination and --actor.")
            restore_backup(
                options["restore"],
                space_id=options["space"],
                actor_id=options["actor"],
                destination=options["destination"],
            )
            self.stdout.write("Retained version restored as a new file.")
        if options["cleanup"]:
            for operation_id in cleanup_candidates():
                self.stdout.write(f"{operation_id}: {cleanup_operation(operation_id)}")
        if options["initialize_items"]:
            initialize_items()
            self.stdout.write("S3 accounting initialized.")
        backends = StorageBackend.objects.filter(enabled=True)
        if options["backend"]:
            backends = backends.filter(pk=options["backend"])
        if options["backend"] or options["all_backends"]:
            for backend in backends:
                scan_backend(backend.pk)
                self.stdout.write(f"Inventory completed: {backend.pk}")
        if options["pending"]:
            for operation in StorageReservation.objects.filter(state="publishing").iterator():
                self.stdout.write(f"{operation.pk}: publication outcome requires reconciliation")
        if options["recover"]:
            for operation_id in reconcile_expired_operations():
                self.stdout.write(f"{operation_id}: {reconcile_operation(operation_id)}")
        if options["check"] or options["verify_items"]:
            report = audit_accounting()
            if options["verify_items"]:
                report["s3_size_mismatches"] = self.verify_items()
            self.stdout.write(json.dumps(report, sort_keys=True))
            if any(report.values()):
                raise CommandError("Resolve the reported storage discrepancies before activation.")

    @staticmethod
    def verify_items():
        """Check object metadata only; pending empty uploads need no native object."""
        mismatches = 0
        for item in Item.objects.filter(type="file", hard_deleted_at__isnull=True).iterator(
            chunk_size=500
        ):
            head = object_head(
                default_storage.connection.meta.client, default_storage.bucket_name, item.file_key
            )
            if not head and item.upload_state == ItemUploadStateChoices.PENDING and not item.size:
                continue
            if not head or head.get("ContentLength") != item.size:
                mismatches += 1
        return mismatches
