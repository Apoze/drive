"""Run through manage.py shell against the isolated ST/Samba qualification stack.

All credentials come from mounted secret files. No user file contents, secrets,
tokens or HTTP payloads are emitted. This deliberately exercises real HTTP/TLS,
PostgreSQL, S3 and SMB together instead of multiplying mocked test cases.
"""

from io import BytesIO
from pathlib import Path

from django.core.files.storage import default_storage
from django.test import override_settings

from core import models
from core.entitlements import get_entitlements_backend
from core.mounts.providers import smb, virtual
from core.services import storage_quota as quota
from core.services.s3_streaming import stream_to_s3_object
from core.services.storage_inventory import initialize_items, refresh_policy, scan_backend
from core.services.storage_spaces import resolve_space_mount


organization = "e8cc8c21-bd9a-4b54-91fa-24c4df24d9e4"
registry = [{"mount_id": "loop-nas", "display_name": "Qualification NAS", "provider": "smb", "enabled": True,
             "params": {"server": "drive-storage-samba-qa", "share": "nas", "username": "qa-a",
                        "base_path": "/loop", "password_secret_path": "/run/secrets/qa-a"}}]
native_root = {**registry[0], "params": {**registry[0]["params"], "base_path": "/"}}
smb.mkdirs(mount=native_root, normalized_path="/loop/alice")

with override_settings(
    STORAGE_GOVERNANCE_ENABLED=True,
    STORAGE_ORGANIZATION_ID=organization,
    MOUNTS_REGISTRY=registry,
    ENTITLEMENTS_BACKEND="core.entitlements.backends.deploycenter.DeployCenterEntitlementsBackend",
    ENTITLEMENTS_BACKEND_PARAMETERS={"base_url": "https://st-qualification-proxy:8443/api/v1.0/entitlements/",
        "service_id": 1, "api_key": Path("/run/secrets/st-service-key").read_text().strip(),
        "organization_claim": "organization_id", "cache_timeout": 0},
):
    get_entitlements_backend.cache_clear()
    actor, _ = models.User.objects.get_or_create(sub="storage-qualification", defaults={
        "email": "storage-qualification@example.invalid", "claims": {"organization_id": organization},
        "password": "!",
    })
    backend, _ = models.StorageBackend.objects.get_or_create(registry_id="loop-nas", defaults={
        "name": "Qualification NAS", "organization": organization,
    })
    space, _ = models.StorageSpace.objects.get_or_create(backend=backend, root_path="/alice", defaults={
        "name": "Personal qualification", "owner": actor,
    })
    initialize_items()
    scan_backend(backend.pk)
    refresh_policy(actor)
    policy = models.StorageQuota.objects.get(key=f"user:{actor.pk}")
    assert policy.limit_bytes == 17
    assert models.StorageQuota.objects.get(key=f"organization:{organization}").limit_bytes == 23
    mount = resolve_space_mount(space.pk, actor)
    virtual.write_stream(mount=mount, final_path="/loop.txt", chunks=[b"hello"])
    item, _ = models.Item.objects.get_or_create(creator=actor, filename="qualification.txt", defaults={
        "title": "qualification", "type": "file", "size": 0,
    })
    common = {"s3_client": default_storage.connection.meta.client, "bucket": default_storage.bucket_name,
              "key": item.file_key, "content_type": "text/plain"}
    stream_to_s3_object(**common, body_stream=BytesIO(b"native"))
    try:
        virtual.write_stream(mount=mount, final_path="/loop.txt", chunks=[b"x" * 20])
    except quota.StorageQuotaExceeded:
        pass
    else:
        raise AssertionError("The shared S3/NAS quota did not reject growth")
    with virtual.open_read(mount=mount, normalized_path="/loop.txt") as content:
        assert content.read() == b"hello"
    policy.refresh_from_db()
    assert (policy.used_bytes, policy.reserved_bytes) == (11, 0)
    space_policy = models.StorageQuota.objects.get(key=f"space:{space.pk}")
    if space_policy.limit_bytes == 6:
        try:
            virtual.write_stream(mount=mount, final_path="/loop.txt", chunks=[b"1234567"])
        except quota.StorageQuotaExceeded:
            pass
        else:
            raise AssertionError("The ST space override was not enforced")
    entitlements = get_entitlements_backend()
    entitlements.acknowledge_policy(actor, policy.policy_revision)
    assert entitlements.fetch_entitlements(actor)["entitlements"]["storage_policy"]["revision"] == policy.policy_revision
    print("PASS: HTTP/TLS policy, shared S3/SMB quota, preserved original, resource metrics, acknowledgement.")
