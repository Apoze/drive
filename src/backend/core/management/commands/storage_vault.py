"""Verify or rotate database credentials using deployment-mounted vault keys."""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import StorageBackend
from core.services.storage_connections import decrypt_credentials, encrypt_credentials


class Command(BaseCommand):
    """The first mounted key encrypts; subsequent keys permit a resumable rotation."""

    help = "Verify encrypted storage credentials; --rotate re-encrypts using the first mounted key."

    def add_arguments(self, parser):
        parser.add_argument("--rotate", action="store_true")

    def handle(self, *args, **options):
        count = 0
        try:
            for identity in (
                StorageBackend.objects.exclude(secret_ciphertext="")
                .values_list("pk", flat=True)
                .iterator(chunk_size=200)
            ):
                with transaction.atomic():
                    backend = StorageBackend.objects.select_for_update().get(pk=identity)
                    credentials = decrypt_credentials(backend)
                    if options["rotate"]:
                        backend.secret_ciphertext = encrypt_credentials(backend, credentials)
                        backend.save(update_fields=["secret_ciphertext"])
                    count += 1
        except ValidationError:
            raise CommandError(
                "Vault verification failed. Keep all previous keys "
                "and retry after restoring access."
            ) from None
        self.stdout.write(
            f"Verified {count} encrypted storage credentials."
            + (" Rotation applied." if options["rotate"] else "")
        )
