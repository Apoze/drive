"""Exercise real independent S3 locations and the credential trust boundary."""

import socket
import uuid
from io import BytesIO, StringIO
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.management import call_command

import pytest
from cryptography.fernet import Fernet
from rest_framework.test import APIClient

from core import factories, models
from core.api.utils import generate_s3_authorization_headers, get_item_file_head_object
from core.services.s3_streaming import stream_to_s3_object
from core.services.storage_connections import (
    decrypt_credentials,
    storage_for_item,
    storage_for_key,
    validate_destination,
)
from core.services.storage_inventory import initialize_items
from core.tasks.storage_connections import check_storage_connection


# Fixture scenarios keep setup and assertions together.
# pylint: disable=too-many-locals,too-many-statements
@pytest.mark.django_db(transaction=True)
def test_independent_s3_locations_and_bound_credentials(settings, tmp_path):  # noqa: PLR0915
    """Same logical filenames stay isolated and ciphertext cannot change owners."""
    key_file = tmp_path / "vault.key"
    key_file.write_bytes(Fernet.generate_key())
    settings.STORAGE_SECRET_KEY_FILE = str(key_file)
    settings.STORAGE_ALLOW_INSECURE_ENDPOINTS = True
    endpoint = default_storage.endpoint_url
    host = urlsplit(endpoint).hostname
    settings.STORAGE_ALLOWED_NETWORKS = [
        result[4][0] + ("/128" if ":" in result[4][0] else "/32")
        for result in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    ]
    actor = factories.UserFactory()
    api = APIClient()
    api.force_authenticate(actor)
    assert api.get("/api/v1.0/storage-connections/").status_code == 403
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    targets = []
    try:
        for index in range(2):
            bucket = "drive-connections-" + uuid.uuid4().hex
            default_storage.connection.meta.client.create_bucket(Bucket=bucket)
            created = api.post(
                "/api/v1.0/storage-connections/",
                {
                    "name": f"Storage {index}",
                    "organization": "local",
                    "family": "s3",
                    "configuration": {
                        "endpoint_url": endpoint,
                        "bucket_name": bucket,
                        "prefix": "files",
                    },
                    "credentials": {
                        "access_key": default_storage.access_key,
                        "secret_key": default_storage.secret_key,
                    },
                },
                format="json",
            )
            assert created.status_code == 201
            assert "credentials" not in created.data and "secret_ciphertext" not in created.data
            connection = models.StorageBackend.objects.get(pk=created.data["id"])
            assert not connection.enabled
            check_storage_connection(str(connection.pk), connection.configuration_generation)
            activated = api.patch(
                f"/api/v1.0/storage-connections/{connection.pk}/", {"enabled": True}, format="json"
            )
            assert activated.status_code == 200
            connection.refresh_from_db()
            item = factories.ItemFactory(
                creator=actor,
                type="file",
                filename="same.txt",
                storage_backend=connection,
                users=[(actor, "owner")],
                update_upload_state=models.ItemUploadStateChoices.READY,
            )
            storage = storage_for_item(item)
            targets.append((item, storage))
            storage.save(item.file_key, BytesIO(f"content-{index}".encode()))
        for index, (item, _) in enumerate(targets):
            with storage_for_key(item.file_key).open(item.file_key) as content:
                assert content.read() == f"content-{index}".encode()
            assert get_item_file_head_object(item)["ContentLength"] == 9
            media = api.get(f"/api/v1.0/items/{item.pk}/content/", HTTP_RANGE="bytes=1-3")
            assert media.status_code == 206
            assert media["Content-Range"] == "bytes 1-3/9"
            assert b"".join(media.streaming_content) == b"ont"
            assert (
                api.head(f"/api/v1.0/items/{item.pk}/content/").headers.get("Content-Length") == "9"
            )
            assert (
                api.get(f"/api/v1.0/items/{item.pk}/content/", HTTP_RANGE="bytes=90-").status_code
                == 416
            )
            signed = generate_s3_authorization_headers(item.file_key)
            assert item.storage_backend.configuration["bucket_name"] in signed.url
            item.size = 9
            item.save(update_fields=["size"])
        settings.STORAGE_GOVERNANCE_ENABLED = True
        initialize_items()
        item, storage = targets[1]
        stream_to_s3_object(
            s3_client=storage.connection.meta.client,
            bucket=storage.bucket_name,
            key=item.file_key,
            body_stream=BytesIO(b"replacement"),
            content_type="text/plain",
        )
        with storage.open(item.file_key) as content:
            assert content.read() == b"replacement"
        usage = models.StorageQuota.objects.get(key=f"user:{actor.pk}")
        assert (usage.used_bytes, usage.reserved_bytes) == (20, 0)
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.regular_storage_copy import copy_regular_storage_object  # noqa: PLC0415

        source, source_storage = targets[0]
        copied = copy_regular_storage_object(
            s3_client=source_storage.connection.meta.client,
            bucket=source_storage.bucket_name,
            source_key=source.file_key,
            destination_key=item.file_key,
        )
        assert copied.used_streaming_fallback and copied.bytes_written == 9
        with storage.open(item.file_key) as content:
            assert content.read() == b"content-0"
        usage.refresh_from_db()
        assert (usage.used_bytes, usage.reserved_bytes) == (18, 0)
        old_key, new_key = key_file.read_bytes(), Fernet.generate_key()
        key_file.write_bytes(new_key + b"\n" + old_key)
        call_command("storage_vault", rotate=True, stdout=StringIO())
        key_file.write_bytes(new_key)
        call_command("storage_vault", stdout=StringIO())
        first = targets[0][0].storage_backend
        second = targets[1][0].storage_backend
        first.refresh_from_db()
        second.refresh_from_db()
        second.secret_ciphertext = first.secret_ciphertext
        with pytest.raises(ValidationError, match="cannot be resolved"):
            decrypt_credentials(second)
        settings.STORAGE_ALLOWED_NETWORKS = ["0.0.0.0/0"]
        with pytest.raises(ValidationError, match="not allowed"):
            validate_destination("169.254.169.254", 80)
        key_file.unlink()
        with pytest.raises(ValidationError, match="vault is unavailable"):
            decrypt_credentials(first)
    finally:
        for item, storage in targets:
            storage.delete(item.file_key)
            storage.connection.meta.client.delete_bucket(Bucket=storage.bucket_name)
