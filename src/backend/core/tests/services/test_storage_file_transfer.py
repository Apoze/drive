"""Real S3 transfer publication at a full logical quota and crash recovery."""

# Each parameter reuses the real multi-backend setup and its bounded teardown.
# pylint: disable=too-many-lines,too-many-nested-blocks
# ruff: noqa: PLR0911, PLR0912, PLR0915

import socket
import uuid
import zipfile
from io import BytesIO
from unittest.mock import patch
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage

import pytest
from cryptography.fernet import Fernet
from lasuite.malware_detection.enums import ReportStatus
from requests_toolbelt import MultipartEncoder
from rest_framework.test import APIClient

from core import factories, models
from core.malware_detection import analysis_kwargs, malware_detection_callback
from core.mounts.providers import localfs, virtual
from core.services.storage_connections import (
    encrypt_credentials,
    storage_for_backend,
    storage_for_item,
)
from core.services.storage_file_transfer import S3TransferWrite, enqueue_s3_transfer
from core.services.storage_integrity import verify_mount_digest
from core.services.storage_inventory import audit_accounting, initialize_items, scan_backend
from core.services.storage_mount_s3_transfer import MountedS3TransferWrite
from core.services.storage_move_job import enqueue_transfer, execute_move
from core.services.storage_native_transfer import enqueue_native_transfer
from core.services.storage_quota import StorageWriteConflict, resource_key
from core.services.storage_recovery import cleanup_operation, restore_backup
from core.services.storage_s3_write import StorageS3Write
from core.services.storage_spaces import resolve_space_mount
from core.services.storage_transfer_location import TransferLocation, resolve_location
from core.tasks.item import process_item_purge
from core.utils.share_links import compute_item_share_token
from wopi.conversion.backends.onlyoffice import SizedFile
from wopi.services.access import AccessUserItemNotAllowed, AccessUserItemService
from wopi.services.lock import LockService


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "interruption",
    [
        "lost_completion",
        "impact",
        "native_create",
        "cleanup",
        "ordinary_move",
        "space_tree_move",
        "connection_tree_move",
        "scan",
        "copy_source_change",
        "copy_source_changed_after_publish",
        "collision",
        "source_change",
        "copy",
        "s3_mount",
        "mount_s3",
        "move_mount_s3",
        "move_s3_mount",
        "move_s3_mount_delegate",
        "move_mount_mount",
        "mount_mount",
        "folder_s3_mount",
        "folder_move_s3_mount",
        "folder_move_mount_s3",
        "folder_move_mount_mount",
        "folder_s3_s3",
        "folder_mount_s3",
        "folder_mount_mount",
    ],
)
# One end-to-end fixture includes its bounded setup and cleanup.
# pylint: disable-next=too-many-locals,too-many-statements,too-many-branches,too-many-return-statements
def test_move_full_budget_and_lost_completion(settings, tmp_path, interruption, monkeypatch):
    """Verify both buckets and recover a lost reply without a second copy or charge."""
    key_file = tmp_path / "vault.key"
    key_file.write_bytes(Fernet.generate_key())
    settings.STORAGE_SECRET_KEY_FILE = str(key_file)
    settings.STORAGE_ALLOW_INSECURE_ENDPOINTS = True
    settings.STORAGE_ALLOWED_NETWORKS = [
        row[4][0] + ("/128" if ":" in row[4][0] else "/32")
        for row in socket.getaddrinfo(
            urlsplit(default_storage.endpoint_url).hostname, None, type=socket.SOCK_STREAM
        )
    ]
    actor = factories.UserFactory()
    stores, roots = [], []
    try:
        for index in range(2):
            bucket = "drive-transfer-" + uuid.uuid4().hex
            default_storage.connection.meta.client.create_bucket(Bucket=bucket)
            backend = models.StorageBackend(
                registry_id=bucket,
                family="s3",
                name=f"Files {index}",
                organization="local",
                configuration={
                    "endpoint_url": default_storage.endpoint_url,
                    "bucket_name": bucket,
                    "prefix": f"files{index}",
                },
            )
            backend.secret_ciphertext = encrypt_credentials(
                backend,
                {
                    "access_key": default_storage.access_key,
                    "secret_key": default_storage.secret_key,
                },
            )
            backend.save()
            storage = storage_for_backend(backend)
            stores.append(storage)
            root = models.Item.objects.create(
                type="folder", title=f"Space {index}", storage_backend=backend, creator=actor
            )
            space = models.StorageSpace.objects.create(
                backend=backend,
                name=f"Space {index}",
                root_item=root,
                explicit_access=True,
                owner=actor,
            )
            models.Item.objects.filter(pk=root.pk).update(storage_space=space)
            root.refresh_from_db()
            models.StorageGrant.objects.create(
                space=space, user=actor, writable=True, shareable=True
            )
            roots.append(root)
        item = models.Item.objects.create_child(
            parent=roots[0],
            type="file",
            title="Moving",
            filename="file.txt",
            creator=actor,
            upload_state="ready",
            size=7,
        )
        models.Item.objects.filter(pk=item.pk).update(upload_state="ready")
        item.refresh_from_db()
        source_key = item.file_key
        if interruption in {"cleanup", "move_s3_mount", "move_s3_mount_delegate"}:
            stores[0].connection.meta.client.put_bucket_versioning(
                Bucket=stores[0].bucket_name, VersioningConfiguration={"Status": "Enabled"}
            )
        stores[0].save(source_key, BytesIO(b"payload"))
        settings.STORAGE_GOVERNANCE_ENABLED = True
        settings.STORAGE_UNIFIED_ENABLED = True
        initialize_items()
        canonical_key = resource_key(f"previous-native-identity:{item.pk}")
        models.StorageUsage.objects.filter(item=item).update(key=canonical_key)
        models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=7)
        if interruption == "ordinary_move":
            folder = models.Item.objects.create_child(
                parent=roots[0], type="folder", title="Target", creator=actor
            )
            api = APIClient()
            api.force_authenticate(actor)
            with patch("core.services.storage_move_job.dispatch_move"):
                queued = api.post(
                    "/api/v1.0/storage-transfers/",
                    {
                        "source": str(item.pk),
                        "destination": str(folder.pk),
                        "mode": "move",
                    },
                    format="json",
                )
            assert queued.status_code == 202
            # Losing the activity transaction must not leave an unjournaled tree move.
            with patch(
                "core.services.storage_move_job.record_item_activity",
                side_effect=RuntimeError("Interrupted"),
            ):
                with pytest.raises(RuntimeError, match="Interrupted"):
                    execute_move(queued.data["id"])
            item.refresh_from_db()
            assert str(item.path) == f"{roots[0].path}.{item.pk}"
            assert execute_move(queued.data["id"]) == "done"
            assert execute_move(queued.data["id"]) == "done"
            item.refresh_from_db()
            assert str(item.path) == f"{folder.path}.{item.pk}" and item.file_key == source_key
            assert models.ItemActivity.objects.filter(item=item, action="moved").count() == 1
            assert models.StorageQuota.objects.get(key=f"user:{actor.pk}").used_bytes == 7
            with pytest.raises(ValidationError, match="inside itself"):
                folder.move(folder)
            return
        if interruption in {"space_tree_move", "connection_tree_move"}:
            target = models.Item.objects.create(
                type="folder",
                title="Other allocation",
                storage_backend=roots[
                    0 if interruption == "space_tree_move" else 1
                ].storage_backend,
            )
            target_space = models.StorageSpace.objects.create(
                backend=target.storage_backend,
                root_item=target,
                name="Other allocation",
                owner=actor,
            )
            models.Item.objects.filter(pk=target.pk).update(storage_space=target_space)
            models.StorageGrant.objects.create(
                space=target_space, user=actor, writable=True, shareable=True
            )
            target.refresh_from_db()
            folder = models.Item.objects.create_child(
                parent=roots[0], type="folder", title="Folder", creator=actor
            )
            nested = models.Item.objects.create_child(
                parent=folder, type="folder", title="Nested", creator=actor
            )
            favorite = models.ItemFavorite.objects.create(item=folder, user=actor)
            models.Item.objects.filter(pk=folder.pk).update(link_reach="public")
            item.move(nested)
            sibling = models.Item.objects.create_child(
                parent=folder,
                type="file",
                title="Sibling",
                filename="sibling.txt",
                creator=actor,
                size=3,
            )
            models.Item.objects.filter(pk=sibling.pk).update(upload_state="ready")
            stores[0].save(sibling.file_key, BytesIO(b"abc"))
            initialize_items()
            models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=10)
            previous_path = str(item.path)
            models.StorageQuota.objects.create(key=f"space:{target_space.pk}", limit_bytes=9)
            api = APIClient()
            api.force_authenticate(actor)
            with (
                patch("core.services.storage_item_tree_move.dispatch_move"),
                patch("core.services.storage_folder_copy.dispatch_move"),
                patch("core.services.storage_file_transfer.dispatch_move"),
                patch("core.services.storage_inventory.refresh_policy"),
            ):
                queued = api.post(
                    "/api/v1.0/storage-transfers/",
                    {
                        "source": str(folder.pk),
                        "destination": str(target.pk),
                        "mode": "move",
                    },
                    format="json",
                )
                assert queued.status_code == 202, queued.data
                for _ in range(10):
                    if execute_move(queued.data["id"]) == "conflict":
                        break
                else:
                    pytest.fail("Quota must prevent the folder publication")
                item.refresh_from_db()
                if interruption == "space_tree_move":
                    assert str(item.path) == previous_path and item.file_key == source_key
                models.StorageQuota.objects.filter(key=f"space:{target_space.pk}").update(
                    limit_bytes=10
                )
                with patch("core.services.storage_move_job.dispatch_move"):
                    assert (
                        api.post(
                            f"/api/v1.0/storage-transfers/{queued.data['id']}/recover/"
                        ).status_code
                        == 202
                    )
                if interruption == "space_tree_move":
                    with patch(
                        "core.services.storage_quota.commit", side_effect=OSError("lost commit")
                    ):
                        with pytest.raises(OSError):
                            execute_move(queued.data["id"])
                    item.refresh_from_db()
                    assert str(item.path) == previous_path
                    with patch(
                        "core.services.storage_connections.storage_for_backend",
                        side_effect=AssertionError("must not copy bytes"),
                    ):
                        assert execute_move(queued.data["id"]) == "done"
                        assert execute_move(queued.data["id"]) == "done"
                else:
                    parent_job = models.StorageMoveJob.objects.get(pk=queued.data["id"])
                    for child in models.StorageMoveJob.objects.filter(
                        payload__parent_job=str(parent_job.pk), state="conflict"
                    ):
                        with patch("core.services.storage_move_job.dispatch_move"):
                            assert (
                                api.post(
                                    f"/api/v1.0/storage-transfers/{child.pk}/recover/"
                                ).status_code
                                == 202
                            )
                    with patch(
                        "core.services.storage_item_tree_move.record_item_activity",
                        side_effect=OSError("lost folder commit"),
                    ) as publication:
                        for _ in range(20):
                            execute_move(parent_job.pk)
                            if publication.called:
                                break
                        else:
                            pytest.fail("Folder finalization was not reached")
                    folder.refresh_from_db()
                    assert folder.storage_space_id == roots[0].storage_space_id
                    staged = models.Item.objects.get(
                        pk=parent_job.copy_entries.get(parent__isnull=True).target_id
                    )
                    visitor = factories.UserFactory()
                    models.ItemFavorite.objects.create(item=staged, user=visitor)
                    models.ItemAccess.objects.create(item=staged, user=visitor, role="reader")
                    invitation = models.Invitation.objects.create(
                        item=staged, email="pending@example.invalid", role="reader", issuer=actor
                    )
                    grant = models.StorageGrant.objects.create(
                        space=target_space, root_item=staged, user=visitor
                    )
                    models.Item.objects.filter(pk=staged.pk).update(link_reach="public")
                    staged_token = compute_item_share_token(staged.pk)
                    with patch(
                        "core.services.storage_file_transfer.execute_s3_transfer",
                        side_effect=AssertionError("files must not be transferred again"),
                    ):
                        assert execute_move(parent_job.pk) == "done"
                        assert execute_move(parent_job.pk) == "done"

            item.refresh_from_db()
            folder.refresh_from_db()
            nested.refresh_from_db()
            assert str(item.path) == f"{target.path}.{folder.pk}.{nested.pk}.{item.pk}"
            assert {item.storage_space_id, folder.storage_space_id, nested.storage_space_id} == {
                target_space.pk
            }
            if interruption == "space_tree_move":
                assert item.file_key == source_key
            else:
                assert item.storage_backend_id == target.storage_backend_id
                with stores[1].open(item.file_key) as result:
                    assert result.read() == b"payload"
                assert models.ItemFavorite.objects.filter(item=folder, user=visitor).exists()
                assert models.ItemAccess.objects.filter(
                    item=folder, user=visitor, role="reader"
                ).exists()
                invitation.refresh_from_db()
                grant.refresh_from_db()
                assert invitation.item_id == grant.root_item_id == folder.pk
                alias = APIClient().get(f"/api/v1.0/share-links/{staged_token}/browse/")
                assert alias.status_code == 200 and alias.data == {"mount_path": "/"}
                alias_browse = APIClient().get(
                    f"/api/v1.0/mount-share-links/{staged_token}/browse/"
                )
                assert alias_browse.status_code == 200
                assert alias_browse.data["entry"]["name"] == folder.title

            assert models.StorageUsage.objects.get(item=item).key == canonical_key
            assert models.StorageQuota.objects.get(key=f"user:{actor.pk}").used_bytes == 10
            budget = models.StorageQuota.objects.get(key=f"space:{target_space.pk}")
            assert (budget.used_bytes, budget.reserved_bytes) == (10, 0)
            assert models.ItemActivity.objects.filter(item=folder, action="moved").count() == 1
            assert models.ItemFavorite.objects.get(pk=favorite.pk).item_id == folder.pk
            shared = APIClient().get(
                f"/api/v1.0/share-links/{compute_item_share_token(folder.pk)}/browse/"
            )
            assert shared.status_code == 200, shared.data
            assert shared.data["item"]["id"] == str(folder.pk)
            assert audit_accounting()["counter_mismatches"] == 0
            return
        if interruption in {
            "impact",
            "native_create",
            "s3_mount",
            "mount_s3",
            "mount_mount",
            "move_mount_s3",
            "move_s3_mount",
            "move_s3_mount_delegate",
            "move_mount_mount",
        } or interruption.startswith("folder_"):
            nas = tmp_path / "nas"
            nas.mkdir()
            (nas / "source").mkdir()
            (nas / "target").mkdir()
            (nas / "source" / "native.txt").write_bytes(b"payload")
            backend = models.StorageBackend.objects.create(
                registry_id="copy-nas", name="NAS", organization="local"
            )
            space = models.StorageSpace.objects.create(backend=backend, owner=actor, name="NAS")
            settings.MOUNTS_REGISTRY = [
                {
                    "mount_id": "copy-nas",
                    "enabled": True,
                    "provider": "localfs",
                    "params": {"root_dir": str(nas)},
                }
            ]
            moving_actor, target_space = actor, space
            if interruption == "move_s3_mount_delegate":
                moving_actor = factories.UserFactory()
                models.StorageGrant.objects.create(
                    space=roots[0].storage_space,
                    user=moving_actor,
                    writable=True,
                    shareable=True,
                )
                target_space = models.StorageSpace.objects.create(
                    backend=backend,
                    name="Creator owned",
                    root_path="/target",
                    attribute_to_creator=True,
                    explicit_access=True,
                )
                models.StorageGrant.objects.create(
                    space=target_space, user=moving_actor, writable=True
                )
                models.StorageQuota.objects.create(key=f"user:{moving_actor.pk}", limit_bytes=0)
            scan_backend(backend.pk)
            native = models.StorageResource.objects.get(
                namespace=backend.namespace, name="native.txt"
            )
            folder = models.StorageResource.objects.get(namespace=backend.namespace, name="target")
            if interruption == "native_create":
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=None)
                api = APIClient()
                api.force_authenticate(actor)
                endpoint = f"/api/v1.0/resources/{folder.pk}/new-file/?space={space.pk}"
                created = api.post(
                    endpoint, {"filename_stem": "Document", "extension": "docx"}, format="json"
                )
                assert created.status_code == 201, created.data
                assert created.data["adapter"]["kind"] == "mount"
                data = (nas / "target" / "Document.docx").read_bytes()
                assert data.startswith(b"PK") and len(data) > 100
                assert not models.Item.objects.filter(pk=created.data["id"]).exists()
                exported = api.get(f"/api/v1.0/mounts/{space.pk}/export/", {"path": "/target"})
                assert exported.status_code == 200
                with zipfile.ZipFile(BytesIO(b"".join(exported.streaming_content))) as archive:
                    assert archive.namelist() == ["Document.docx"]
                    assert archive.read("Document.docx") == data

                assert (
                    api.post(
                        endpoint, {"filename_stem": "Document", "extension": "docx"}, format="json"
                    ).status_code
                    == 409
                )
                quota = models.StorageQuota.objects.get(key=f"user:{actor.pk}")
                quota.limit_bytes = quota.used_bytes
                quota.save(update_fields=["limit_bytes"])
                assert (
                    api.post(
                        endpoint, {"filename_stem": "Full", "extension": "odt"}, format="json"
                    ).status_code
                    == 413
                )
                assert not (nas / "target" / "Full.odt").exists()
                api.force_authenticate(factories.UserFactory())
                assert (
                    api.post(
                        endpoint, {"filename_stem": "Denied", "extension": "txt"}, format="json"
                    ).status_code
                    == 404
                )
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=None)
                (nas / "target" / "legacy.doc").write_bytes(b"synthetic legacy source")
                scan_backend(backend.pk)
                legacy = models.StorageResource.objects.get(
                    namespace=backend.namespace, name="legacy.doc"
                )
                settings.WOPI_ONLYOFFICE_CONVERT_JWT_SECRET = "synthetic-test-secret"
                settings.WOPI_CLIENTS_CONFIGURATION = {
                    "onlyoffice": {
                        "options": {
                            "ForceConvertExtensions": ["doc"],
                            "ConvertServiceUrl": "http://converter.invalid/converter",
                        }
                    }
                }
                api.force_authenticate(actor)
                with patch("core.services.storage_copy_job.dispatch_move"):
                    queued = api.post(f"/api/v1.0/resources/{legacy.pk}/convert/?space={space.pk}")
                assert queued.status_code == 202, queued.data

                with patch("wopi.conversion.native.resolve_backend") as converter:
                    converter.return_value.convert.return_value = SizedFile(
                        BytesIO(data), name="converted.docx", size=len(data)
                    )
                    assert execute_move(queued.data["id"]) == "done"
                    assert execute_move(queued.data["id"]) == "done"
                    assert converter.return_value.convert.call_count == 1
                assert (nas / "target" / "legacy (converted).docx").read_bytes() == data
                assert (nas / "target" / "legacy.doc").read_bytes() == b"synthetic legacy source"

                for destination_id, destination_space in [
                    (roots[1].pk, roots[1].storage_space_id),
                    (folder.pk, space.pk),
                ]:
                    with patch("core.services.storage_archive.dispatch_move"):
                        zipped = api.post(
                            "/api/v1.0/storage-transfers/archive/",
                            {
                                "sources": [
                                    {"source": str(item.pk)},
                                    {"source": str(folder.pk), "source_space": str(space.pk)},
                                ],
                                "destination": str(destination_id),
                                "destination_space": str(destination_space),
                                "mode": "archive",
                                "name": "mixed.zip",
                            },
                            format="json",
                        )
                    assert zipped.status_code == 202, zipped.data
                    assert execute_move(zipped.data["id"]) == "done"
                    assert execute_move(zipped.data["id"]) == "done"
                    archive_job = models.StorageMoveJob.objects.get(pk=zipped.data["id"])
                    if destination_id == folder.pk:
                        zip_bytes = (nas / "target" / "mixed.zip").read_bytes()
                    else:
                        output = models.Item.objects.get(pk=archive_job.payload["result"])
                        with storage_for_item(output).open(output.file_key, "rb") as stream:
                            zip_bytes = stream.read()
                    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
                        assert archive.read("file.txt") == b"payload"
                        assert archive.read("target/Document.docx") == data
                        assert "target/" in archive.namelist()
                    assert archive_job.copy_entries.filter(done=False).count() == 0
                    if destination_id != folder.pk:
                        models.Item.objects.filter(pk=output.pk).update(upload_state="ready")
                    for target_index, (target_id, target_space) in enumerate(
                        [(roots[1].pk, roots[1].storage_space_id), (folder.pk, space.pk)]
                    ):
                        name = f"extracted-{destination_id}-{target_index}"
                        request = {
                            "sources": [
                                {
                                    "source": archive_job.payload["result"],
                                    "source_space": str(destination_space),
                                }
                            ],
                            "destination": str(target_id),
                            "destination_space": str(target_space),
                            "mode": "extract",
                            "name": name,
                        }
                        if target_id == folder.pk:
                            monkeypatch.setenv("MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT", "false")
                            denied = api.post(
                                "/api/v1.0/storage-transfers/extract/", request, format="json"
                            )
                            assert denied.status_code == 403
                            assert (
                                denied.data["errors"][0]["code"] == "MOUNT_ARCHIVE_EXTRACT_UNSAFE"
                            )
                        monkeypatch.setenv("MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT", "true")
                        with patch("core.services.storage_extract.dispatch_move"):
                            extracted = api.post(
                                "/api/v1.0/storage-transfers/extract/", request, format="json"
                            )
                        assert extracted.status_code == 202, extracted.data
                        if target_index == 0:
                            # A committed member survives a worker loss before parent progress.
                            with patch(
                                "core.services.storage_copy_job._finish",
                                side_effect=OSError("synthetic worker loss"),
                            ):
                                assert execute_move(extracted.data["id"]) == "more"
                        for _ in range(10):
                            outcome = execute_move(extracted.data["id"])
                            if outcome != "more":
                                break
                        extraction = models.StorageMoveJob.objects.get(pk=extracted.data["id"])
                        assert outcome == "done", extraction.reason
                        assert execute_move(extraction.pk) == "done"
                        assert extraction.copy_entries.filter(done=False).count() == 0
                        if target_id == folder.pk:
                            assert (nas / "target" / name / "file.txt").read_bytes() == b"payload"
                            assert (
                                nas / "target" / name / "target" / "Document.docx"
                            ).read_bytes() == data
                        else:
                            extracted_root = models.Item.objects.get(
                                pk=extraction.payload["result"]
                            )
                            extracted_file = extracted_root.children().get(filename="file.txt")
                            with storage_for_item(extracted_file).open(
                                extracted_file.file_key, "rb"
                            ) as stream:
                                assert stream.read() == b"payload"
                assert audit_accounting()["counter_mismatches"] == 0
                return
            if interruption == "impact":
                models.Item.objects.filter(pk=item.pk).update(link_reach="public")
                models.MountShareLink.objects.create(
                    token="synthetic-impact-link",
                    resource=native,
                    created_by=actor,
                    mount_id=str(space.pk),
                    normalized_path="/source/native.txt",
                )
                api = APIClient()
                api.force_authenticate(actor)
                selection = [
                    {"source": str(item.pk)},
                    {"source": str(native.pk), "source_space": str(space.pk)},
                ]
                with patch.object(
                    localfs, "open_read", side_effect=AssertionError("metadata only")
                ):
                    for mode in ("copy", "move"):
                        result = api.post(
                            "/api/v1.0/storage-transfers/impact/",
                            {
                                "sources": selection,
                                "destination": str(roots[1].pk),
                                "mode": mode,
                            },
                            format="json",
                        )
                        assert result.status_code == 200, result.data
                        assert result.data["files"] == 2 and result.data["bytes"] == 14
                        assert result.data["space_additional_bytes"] == 14
                        assert result.data["global_additional_bytes"] == (
                            14 if mode == "copy" else 0
                        )
                        assert result.data["public_links"] == (0 if mode == "copy" else 2)
                duplicate = api.post(
                    "/api/v1.0/storage-transfers/impact/",
                    {
                        "sources": selection * 2,
                        "destination": str(roots[1].pk),
                        "mode": "copy",
                    },
                    format="json",
                )
                assert duplicate.status_code == 409
                assert not models.StorageMoveJob.objects.exists()
                assert not models.StorageReservation.objects.exists()
                api.force_authenticate(factories.UserFactory())
                denied = api.post(
                    "/api/v1.0/storage-transfers/impact/",
                    {
                        "sources": selection,
                        "destination": str(roots[1].pk),
                        "mode": "copy",
                    },
                    format="json",
                )
                assert denied.status_code == 404
                return
            if interruption == "move_mount_mount":
                other_nas = tmp_path / "other-nas"
                other_nas.mkdir()
                (other_nas / "destination").mkdir()
                other_backend = models.StorageBackend.objects.create(
                    registry_id="other-nas", name="Other NAS", organization="local"
                )
                other_space = models.StorageSpace.objects.create(
                    backend=other_backend, owner=actor, name="Other NAS"
                )
                settings.MOUNTS_REGISTRY += [
                    {
                        "mount_id": "other-nas",
                        "enabled": True,
                        "provider": "localfs",
                        "params": {"root_dir": str(other_nas)},
                    }
                ]
                scan_backend(other_backend.pk)
                target = models.StorageResource.objects.get(
                    namespace=other_backend.namespace, path="/destination"
                )
                favorite = models.StorageResourceFavorite.objects.create(
                    resource=native, user=actor, space=space, favorite=True
                )
                api = APIClient()
                api.force_authenticate(actor)
                links_url = f"/api/v1.0/resources/{native.pk}/public-links/"
                assert api.post(links_url, {}, format="json").status_code == 200
                link = models.MountShareLink.objects.get(resource=native)
                usage = models.StorageUsage.objects.get(
                    native_key=resource_key(f"mount:{backend.namespace}:{native.provider_identity}")
                )
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=14)
                with (
                    patch("core.services.storage_native_transfer.dispatch_move"),
                    patch("core.services.storage_inventory.refresh_policy"),
                ):
                    queued = api.post(
                        "/api/v1.0/storage-transfers/",
                        {
                            "source": str(native.pk),
                            "destination": str(target.pk),
                            "mode": "move",
                        },
                        format="json",
                    )
                    assert queued.status_code == 202, queued.data
                    with patch(
                        "core.services.storage_quota.commit", side_effect=OSError("lost reply")
                    ):
                        assert execute_move(queued.data["id"]) == "running"
                    assert not (nas / "source" / "native.txt").exists()
                    assert (other_nas / "destination" / "native.txt").read_bytes() == b"payload"
                    scan_backend(backend.pk)
                    scan_backend(other_backend.pk)
                    assert models.StorageQuota.objects.get(key=f"user:{actor.pk}").used_bytes == 14
                    other_space.enabled = False
                    other_space.save(update_fields=["enabled"])
                    assert execute_move(queued.data["id"]) == "conflict"
                    other_space.enabled = True
                    other_space.save(update_fields=["enabled"])
                    with patch("core.services.storage_move_job.dispatch_move"):
                        assert (
                            api.post(
                                f"/api/v1.0/storage-transfers/{queued.data['id']}/recover/"
                            ).status_code
                            == 202
                        )
                    with patch.object(
                        localfs, "open_write", side_effect=AssertionError("must not recopy")
                    ):
                        assert execute_move(queued.data["id"]) == "cleanup"
                native.refresh_from_db()
                usage.refresh_from_db()
                favorite.refresh_from_db()
                assert native.namespace == other_backend.namespace and not native.missing
                assert usage.backend_id == other_backend.pk
                assert favorite.space_id == other_space.pk and favorite.favorite
                assert models.StorageQuota.objects.get(key=f"user:{actor.pk}").used_bytes == 14
                public = APIClient()
                download = public.get(f"/api/v1.0/mount-share-links/{link.token}/download/")
                assert download.status_code == 200
                assert b"".join(download.streaming_content) == b"payload"
                actor.is_superuser = True
                actor.save(update_fields=["is_superuser"])
                retained = api.get("/api/v1.0/storage-administration-jobs/retained-versions/")
                assert retained.status_code == 200 and retained.data["count"] == 1
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=21)
                with patch("core.services.storage_inventory.refresh_policy"):
                    restore_backup(
                        retained.data["results"][0]["id"],
                        space_id=space.pk,
                        actor_id=actor.pk,
                        destination="/source/restored.txt",
                    )
                assert (nas / "source" / "restored.txt").read_bytes() == b"payload"
                with patch("core.services.storage_inventory.refresh_policy"):
                    virtual.rename(
                        mount=resolve_space_mount(space.pk, actor),
                        src_normalized_path="/source",
                        dst_normalized_path="/renamed-source",
                    )
                settings.STORAGE_BACKUP_RETENTION_DAYS = 0
                space.enabled = False
                space.save(update_fields=["enabled"])
                assert execute_move(queued.data["id"]) == "cleanup"
                space.enabled = True
                space.save(update_fields=["enabled"])
                assert execute_move(queued.data["id"]) == "done"
                assert not list((nas / "renamed-source").glob(".drive-txn-*.moved"))
                assert (nas / "renamed-source/restored.txt").read_bytes() == b"payload"
                assert (other_nas / "destination" / "native.txt").read_bytes() == b"payload"
                scan_backend(backend.pk)
                scan_backend(other_backend.pk)
                assert audit_accounting()["counter_mismatches"] == 0
                return
            if interruption in {"move_s3_mount", "move_s3_mount_delegate"}:
                item.link_reach = "public"
                item.save(update_fields=["link_reach"])
                models.ItemFavorite.objects.create(item=item, user=actor)
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=14)
                with (
                    patch("core.services.storage_native_transfer.dispatch_move"),
                    patch("core.services.storage_inventory.refresh_policy"),
                ):
                    job = enqueue_native_transfer(
                        actor=moving_actor,
                        source=resolve_location(item.pk, moving_actor),
                        destination=resolve_location(
                            folder.pk, moving_actor, space_id=target_space.pk, destination=True
                        ),
                    )
                    with patch(
                        "core.services.storage_quota.commit", side_effect=OSError("lost reply")
                    ):
                        assert execute_move(job.pk) == "running"
                    item.refresh_from_db()
                    assert not item.hard_deleted_at
                    assert (nas / "target" / "file.txt").read_bytes() == b"payload"
                    with patch.object(
                        localfs, "open_write", side_effect=AssertionError("must not recopy")
                    ):
                        assert execute_move(job.pk) == "cleanup"
                    assert execute_move(job.pk) == "cleanup"
                moved = models.StorageResource.objects.get(pk=item.pk)
                assert moved.path == "/target/file.txt" and not moved.missing
                usage = models.StorageUsage.objects.get(key=canonical_key)
                assert usage.item_id is None and usage.backend_id == backend.pk
                assert usage.owner_id == actor.pk
                if moving_actor.pk != actor.pk:
                    assert (
                        models.StorageQuota.objects.get(key=f"user:{moving_actor.pk}").used_bytes
                        == 0
                    )
                assert models.StorageResourceFavorite.objects.get(
                    resource=moved, user=actor
                ).favorite
                process_item_purge(item.pk)
                assert not models.Item.objects.filter(pk=item.pk).exists()
                with stores[0].open(source_key) as stream:
                    assert stream.read() == b"payload"
                public = APIClient()
                link = models.MountShareLink.objects.get(resource=moved)
                authenticated = APIClient()
                authenticated.force_authenticate(actor)
                old_url = f"/api/v1.0/items/{item.pk}/download/"
                moved_download = authenticated.get(old_url)
                assert moved_download.status_code == 302
                assert authenticated.get(moved_download.headers["Location"]).status_code == 200
                anonymous_download = public.get(old_url, {"share_token": link.token})
                assert anonymous_download.status_code == 302
                assert public.get(anonymous_download.headers["Location"]).status_code == 200
                public_browse = public.get(f"/api/v1.0/share-links/{link.token}/browse/")
                assert public_browse.status_code == 200
                assert public_browse.data["item"]["id"] == str(item.pk)
                download = public.get(f"/api/v1.0/mount-share-links/{link.token}/download/")
                assert b"".join(download.streaming_content) == b"payload"
                space.allow_sharing = False
                space.save(update_fields=["allow_sharing"])
                assert public.get(f"/api/v1.0/share-links/{link.token}/browse/").status_code == 410
                settings.STORAGE_BACKUP_RETENTION_DAYS = 0
                grant = roots[0].storage_space.grants.get(user=moving_actor)
                grant.writable = False
                grant.save(update_fields=["writable"])
                assert execute_move(job.pk) == "cleanup"
                grant.writable = True
                grant.save(update_fields=["writable"])

                def revoke_during_verification(*args, **kwargs):
                    verify_mount_digest(*args, **kwargs)
                    models.StorageGrant.objects.filter(pk=grant.pk).update(writable=False)

                with patch(
                    "core.services.storage_transfer_location.verify_mount_digest",
                    side_effect=revoke_during_verification,
                ):
                    assert execute_move(job.pk) == "cleanup"
                grant.save(update_fields=["writable"])
                assert execute_move(job.pk) == "done"
                stores[0].save(source_key, BytesIO(b"outside"))
                with (
                    patch("core.services.storage_mount_s3_transfer.dispatch_move"),
                    patch("core.services.storage_inventory.refresh_policy"),
                ):
                    returned = enqueue_transfer(
                        actor=actor,
                        source=resolve_location(moved.pk, actor),
                        destination=resolve_location(roots[0].pk, actor, destination=True),
                    )
                    assert execute_move(returned.pk) == "cleanup"
                assert not models.StorageResourceFavorite.objects.filter(resource=moved).exists()
                returned_item = models.Item.objects.get(pk=item.pk)
                assert returned_item.file_key != source_key
                with storage_for_item(returned_item).open(returned_item.file_key) as stream:
                    assert stream.read() == b"payload"
                with stores[0].open(source_key) as stream:
                    assert stream.read() == b"outside"
                initialize_items()
                scan_backend(backend.pk)
                assert models.StorageQuota.objects.get(key=f"user:{actor.pk}").used_bytes == 14
                assert audit_accounting()["counter_mismatches"] == 0
                return
            if interruption == "move_mount_s3":
                favorite = models.StorageResourceFavorite.objects.create(
                    resource=native,
                    user=actor,
                    space=space,
                    favorite=True,
                )
                public_link = models.MountShareLink.objects.create(
                    resource=native,
                    created_by=actor,
                    mount_id=str(space.pk),
                    token=uuid.uuid4().hex,
                    normalized_path="/source/native.txt",
                )
                original_usage = models.StorageUsage.objects.get(
                    native_key=resource_key(f"mount:{backend.namespace}:{native.provider_identity}")
                )
                api = APIClient()
                api.force_authenticate(actor)
                links_url = f"/api/v1.0/resources/{native.pk}/public-links/"
                assert api.post(links_url, {}, format="json").status_code == 200
                assert models.MountShareLink.objects.filter(resource=native).count() == 1
                stranger = factories.UserFactory()
                other_api = APIClient()
                other_api.force_authenticate(stranger)
                assert other_api.get(links_url).status_code == 404
                stranger_grant = models.StorageGrant.objects.create(space=space, user=stranger)
                assert other_api.get(links_url).data["count"] == 0
                assert other_api.post(links_url, {}, format="json").status_code == 403
                assert (
                    other_api.delete(
                        links_url, {"link": str(public_link.pk)}, format="json"
                    ).status_code
                    == 404
                )
                stranger_grant.path = "/source/native.txt"
                stranger_grant.shareable = True
                stranger_grant.save(update_fields=["path", "shareable"])
                ancestor = models.StorageResource.objects.get(
                    namespace=backend.namespace, path="/source"
                )
                assert (
                    other_api.post(
                        f"/api/v1.0/resources/{ancestor.pk}/public-links/", {}, format="json"
                    ).status_code
                    == 403
                )
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=14)
                with (
                    patch("core.services.storage_mount_s3_transfer.dispatch_move"),
                    patch("core.services.storage_inventory.refresh_policy"),
                ):
                    queued = api.post(
                        "/api/v1.0/storage-transfers/",
                        {
                            "source": str(native.pk),
                            "source_space": str(space.pk),
                            "destination": str(roots[1].pk),
                            "mode": "move",
                        },
                        format="json",
                    )
                    assert queued.status_code == 202, queued.data
                    original_publish = S3TransferWrite.publish

                    def require_closed_source(writer, size):
                        assert writer.reader.stream.closed
                        return original_publish(writer, size)

                    with (
                        patch.object(S3TransferWrite, "publish", require_closed_source),
                        patch(
                            "core.services.storage_quota.commit", side_effect=OSError("lost reply")
                        ),
                    ):
                        assert execute_move(queued.data["id"]) == "running"
                    assert not models.Item.objects.filter(pk=native.pk).exists()
                    assert not (nas / "source" / "native.txt").exists()
                    assert len(list((nas / "source").glob(".drive-txn-*.moved"))) == 1
                    scan_backend(backend.pk)
                    target_space = roots[1].storage_space
                    target_space.enabled = False
                    target_space.save(update_fields=["enabled"])
                    assert execute_move(queued.data["id"]) == "conflict"
                    target_space.enabled = True
                    target_space.save(update_fields=["enabled"])
                    with patch("core.services.storage_move_job.dispatch_move"):
                        assert (
                            api.post(
                                f"/api/v1.0/storage-transfers/{queued.data['id']}/recover/"
                            ).status_code
                            == 202
                        )
                    with patch.object(
                        MountedS3TransferWrite,
                        "prepare",
                        side_effect=AssertionError("must not recopy"),
                    ):
                        assert execute_move(queued.data["id"]) == "cleanup"
                    assert execute_move(queued.data["id"]) == "cleanup"
                moved = models.Item.objects.get(pk=native.pk)
                assert moved.storage_space_id == roots[1].storage_space_id
                assert moved.upload_state == "ready"
                with storage_for_item(moved).open(moved.file_key) as stream:
                    assert stream.read() == b"payload"
                original_usage.refresh_from_db()
                assert original_usage.item_id == moved.pk and original_usage.native_key is None
                assert models.ItemFavorite.objects.filter(
                    user_id=favorite.user_id, item=moved
                ).exists()
                public = APIClient()
                public_url = f"/api/v1.0/mount-share-links/{public_link.token}/"
                assert public.get(public_url + "browse/").data["entry"]["name"] == "native.txt"
                download = public.get(public_url + "download/", HTTP_RANGE="bytes=0-2")
                assert download.status_code == 206
                assert b"".join(download.streaming_content) == b"pay"
                assert public.get(public_url + "download/?path=/sibling").status_code == 404
                assert api.get(links_url).data["results"][0]["id"] == str(public_link.pk)
                assert api.post(links_url, {}, format="json").status_code == 403
                assert (
                    api.delete(links_url, {"link": str(public_link.pk)}, format="json").status_code
                    == 204
                )
                assert public.get(public_url + "download/").status_code == 404
                public_link.save(force_insert=True)
                target_space = moved.storage_space
                target_space.allow_sharing = False
                target_space.save(update_fields=["allow_sharing"])
                assert public.get(public_url + "download/").status_code == 410
                target_space.allow_sharing = True
                target_space.save(update_fields=["allow_sharing"])
                native.refresh_from_db()
                assert native.missing
                scan_backend(backend.pk)
                assert models.StorageQuota.objects.get(key=f"user:{actor.pk}").used_bytes == 14
                virtual.remove(
                    mount=resolve_space_mount(space.pk, actor), normalized_path="/source"
                )
                parent_deletion = models.StorageReservation.objects.get(
                    publication__kind="delete", publication__source_path="/source"
                )
                # A later cross-family move must not strand the first retained source.
                with (
                    patch("core.services.storage_native_transfer.dispatch_move"),
                    patch("core.services.storage_inventory.refresh_policy"),
                ):
                    returned = enqueue_transfer(
                        actor=actor,
                        source=resolve_location(moved.pk, actor),
                        destination=resolve_location(folder.pk, actor, destination=True),
                    )
                    assert execute_move(returned.pk) == "cleanup"
                settings.STORAGE_BACKUP_RETENTION_DAYS = 0
                with patch("core.services.storage_inventory.refresh_policy"):
                    assert execute_move(queued.data["id"]) == "done"
                assert cleanup_operation(parent_deletion.pk) == "cleaned"
                assert not list(nas.glob(".drive-txn-*.deleted"))
                assert audit_accounting()["counter_mismatches"] == 0
                return
            if interruption in {"folder_move_mount_s3", "folder_move_mount_mount"}:
                (nas / "source/Nested").mkdir()
                (nas / "source/Empty").mkdir()
                (nas / "source/native.txt").rename(nas / "source/Nested/native.txt")
                scan_backend(backend.pk)
                bundle = models.StorageResource.objects.get(
                    namespace=backend.namespace, path="/source"
                )
                nested = models.StorageResource.objects.get(
                    namespace=backend.namespace, path="/source/Nested"
                )
                empty = models.StorageResource.objects.get(
                    namespace=backend.namespace, path="/source/Empty"
                )
                target = roots[1]
                if interruption.endswith("_mount"):
                    other_nas = tmp_path / "other-nas"
                    other_nas.mkdir()
                    (other_nas / "destination").mkdir()
                    other_backend = models.StorageBackend.objects.create(
                        registry_id="other-nas", name="Other NAS", organization="local"
                    )
                    models.StorageSpace.objects.create(
                        backend=other_backend, owner=actor, name="Other NAS"
                    )
                    settings.MOUNTS_REGISTRY += [
                        {
                            "mount_id": "other-nas",
                            "enabled": True,
                            "provider": "localfs",
                            "params": {"root_dir": str(other_nas)},
                        }
                    ]
                    scan_backend(other_backend.pk)
                    target = models.StorageResource.objects.get(
                        namespace=other_backend.namespace, path="/destination"
                    )
                models.StorageResourceFavorite.objects.create(
                    resource=bundle, user=actor, space=space, favorite=True
                )
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=14)
                api = APIClient()
                api.force_authenticate(actor)
                assert (
                    api.post(
                        f"/api/v1.0/resources/{bundle.pk}/public-links/", {}, format="json"
                    ).status_code
                    == 200
                )
                link = models.MountShareLink.objects.get(resource=bundle)
                with (
                    patch("core.services.storage_folder_copy.dispatch_move"),
                    patch("core.services.storage_mount_s3_transfer.dispatch_move"),
                    patch("core.services.storage_native_transfer.dispatch_move"),
                    patch("core.services.storage_inventory.refresh_policy"),
                ):
                    queued = api.post(
                        "/api/v1.0/storage-transfers/",
                        {
                            "source": str(bundle.pk),
                            "destination": str(target.pk),
                            "mode": "move",
                        },
                        format="json",
                    )
                    assert queued.status_code == 202, queued.data
                    with patch(
                        "core.services.storage_native_folder_move._publish",
                        side_effect=OSError("lost native folder metadata"),
                    ) as publication:
                        for _ in range(10):
                            execute_move(queued.data["id"])
                            if publication.called:
                                break
                        else:
                            job = models.StorageMoveJob.objects.get(pk=queued.data["id"])
                            pytest.fail(f"Native finalization missing: {job.state}: {job.reason}")
                    with (
                        patch(
                            "core.services.storage_native_transfer.execute_native_transfer",
                            side_effect=AssertionError("must not move files twice"),
                        ),
                        patch(
                            "core.services.storage_mount_s3_transfer.execute_mount_s3_move",
                            side_effect=AssertionError("must not move files twice"),
                        ),
                    ):
                        for _ in range(10):
                            if execute_move(queued.data["id"]) == "done":
                                break
                        else:
                            job = models.StorageMoveJob.objects.get(pk=queued.data["id"])
                            pytest.fail(f"Native folder not finished: {job.state}: {job.reason}")
                        assert execute_move(queued.data["id"]) == "done"
                assert not (nas / "source").exists()
                if interruption.endswith("_s3"):
                    moved = models.Item.objects.get(pk=native.pk)
                    assert str(moved.path) == f"{target.path}.{bundle.pk}.{nested.pk}.{native.pk}"
                    assert (
                        models.Item.objects.filter(pk__in=[bundle.pk, nested.pk, empty.pk]).count()
                        == 3
                    )
                    assert models.ItemFavorite.objects.filter(
                        item_id=bundle.pk, user=actor
                    ).exists()
                    with storage_for_item(moved).open(moved.file_key) as result:
                        assert result.read() == b"payload"
                else:
                    assert (
                        models.StorageResource.objects.filter(
                            pk__in=[bundle.pk, nested.pk, empty.pk, native.pk],
                            namespace=other_backend.namespace,
                            missing=False,
                        ).count()
                        == 4
                    )
                    assert (
                        other_nas / "destination/source/Nested/native.txt"
                    ).read_bytes() == b"payload"
                public = APIClient()
                browse = public.get(f"/api/v1.0/mount-share-links/{link.token}/browse/")
                assert browse.status_code == 200, browse.data
                assert browse.data["entry"]["entry_type"] == "folder"
                assert browse.data["children"]["count"] == 2
                exported = public.get(f"/api/v1.0/mount-share-links/{link.token}/download/")
                assert exported.status_code == 200
                with zipfile.ZipFile(BytesIO(b"".join(exported.streaming_content))) as archive:
                    assert archive.read("Nested/native.txt") == b"payload"
                    assert "Empty/" in archive.namelist()
                download = public.get(
                    f"/api/v1.0/mount-share-links/{link.token}/download/",
                    {"path": "/Nested/native.txt"},
                )
                assert download.status_code == 200, getattr(download, "data", None)
                assert b"".join(download.streaming_content) == b"payload"
                assert (
                    public.get(
                        f"/api/v1.0/mount-share-links/{link.token}/download/",
                        {"path": f"/{item.pk}"},
                    ).status_code
                    == 404
                )
                settings.STORAGE_BACKUP_RETENTION_DAYS = 0
                job = models.StorageMoveJob.objects.get(pk=queued.data["id"])
                with patch("core.services.storage_inventory.refresh_policy"):
                    for entry in job.copy_entries.filter(kind="file"):
                        assert execute_move(entry.child_job_id) == "done"
                    for operation in models.StorageReservation.objects.filter(
                        publication__folder_job_id=str(job.pk)
                    ).order_by("created_at"):
                        assert cleanup_operation(operation.pk) == "cleaned"
                assert not list(nas.glob(".drive-txn-*.deleted"))
                scan_backend(backend.pk)
                assert models.StorageQuota.objects.get(key=f"user:{actor.pk}").used_bytes == 14
                assert audit_accounting()["counter_mismatches"] == 0
                return
            if interruption == "folder_move_s3_mount":
                bundle = models.Item.objects.create_child(
                    parent=roots[0], type="folder", title="Bundle", creator=actor
                )
                nested = models.Item.objects.create_child(
                    parent=bundle, type="folder", title="Nested", creator=actor
                )
                empty = models.Item.objects.create_child(
                    parent=bundle, type="folder", title="Empty", creator=actor
                )
                item.move(nested)
                models.Item.objects.filter(pk=bundle.pk).update(link_reach="public")
                models.ItemFavorite.objects.create(item=bundle, user=actor)
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=14)
                api = APIClient()
                api.force_authenticate(actor)
                with (
                    patch("core.services.storage_folder_copy.dispatch_move"),
                    patch("core.services.storage_native_transfer.dispatch_move"),
                    patch("core.services.storage_inventory.refresh_policy"),
                ):
                    queued = api.post(
                        "/api/v1.0/storage-transfers/",
                        {"mode": "move", "source": str(bundle.pk), "destination": str(folder.pk)},
                        format="json",
                    )
                    assert queued.status_code == 202, queued.data
                    with patch(
                        "core.services.storage_item_tree_move.transfer_item_links",
                        side_effect=OSError("lost folder finalization"),
                    ) as finalize:
                        for _ in range(10):
                            execute_move(queued.data["id"])
                            if finalize.called:
                                break
                        else:
                            job = models.StorageMoveJob.objects.get(pk=queued.data["id"])
                            pytest.fail(f"Folder finalization missing: {job.state}: {job.reason}")
                    assert models.Item.objects.filter(pk=bundle.pk).exists()
                    staged_root = models.StorageMoveJob.objects.get(
                        pk=queued.data["id"]
                    ).copy_entries.get(parent__isnull=True)
                    staged_link = models.MountShareLink.objects.create(
                        token=uuid.uuid4().hex,
                        resource_id=staged_root.target_id,
                        created_by=actor,
                        mount_id=str(space.pk),
                        normalized_path="/target/Bundle",
                    )
                    with patch(
                        "core.services.storage_native_transfer.execute_native_transfer",
                        side_effect=AssertionError("must not repeat file publication"),
                    ):
                        assert execute_move(queued.data["id"]) == "done"
                        assert execute_move(queued.data["id"]) == "done"
                assert not models.Item.objects.filter(
                    pk__in=[bundle.pk, nested.pk, empty.pk, item.pk]
                ).exists()
                for node, path in (
                    (bundle, "/target/Bundle"),
                    (nested, "/target/Bundle/Nested"),
                    (empty, "/target/Bundle/Empty"),
                    (item, "/target/Bundle/Nested/file.txt"),
                ):
                    resource = models.StorageResource.objects.get(pk=node.pk)
                    assert resource.namespace == backend.namespace and resource.path == path
                assert (nas / "target/Bundle/Nested/file.txt").read_bytes() == b"payload"
                assert models.StorageResourceFavorite.objects.get(
                    resource_id=bundle.pk, user=actor
                ).favorite
                assert models.StorageQuota.objects.get(key=f"user:{actor.pk}").used_bytes == 14
                public = APIClient()
                token = compute_item_share_token(bundle.pk)
                legacy = public.get(f"/api/v1.0/share-links/{token}/browse/")
                assert legacy.status_code == 200 and legacy.data == {"mount_path": "/"}
                nested_link = public.get(
                    f"/api/v1.0/share-links/{token}/browse/", {"item_id": str(nested.pk)}
                )
                assert nested_link.data == {"mount_path": "/Nested"}
                assert (
                    public.get(
                        f"/api/v1.0/share-links/{token}/browse/", {"item_id": str(native.pk)}
                    ).status_code
                    == 404
                )
                public_browse = public.get(f"/api/v1.0/mount-share-links/{token}/browse/")
                assert public_browse.status_code == 200, public_browse.data
                staged_link.refresh_from_db()
                assert staged_link.resource_id == bundle.pk
                assert (
                    public.get(
                        f"/api/v1.0/mount-share-links/{staged_link.token}/browse/"
                    ).status_code
                    == 200
                )
                download = public.get(
                    f"/api/v1.0/mount-share-links/{token}/download/", {"path": "/Nested/file.txt"}
                )
                assert download.status_code == 200
                assert b"".join(download.streaming_content) == b"payload"
                scan_backend(backend.pk)
                assert audit_accounting()["counter_mismatches"] == 0
                return
            if interruption.startswith("folder_"):
                (nas / "source" / "empty").mkdir()
                models.Item.objects.create_child(
                    parent=roots[0], type="folder", title="empty", creator=actor
                )
                source_folder = models.StorageResource.objects.get(
                    namespace=backend.namespace, name="source"
                )
                api = APIClient()
                api.force_authenticate(actor)
                request = {
                    "mode": "copy",
                    "source": str(
                        roots[0].pk if interruption.startswith("folder_s3_") else source_folder.pk
                    ),
                    "destination": str(roots[1].pk if interruption.endswith("_s3") else folder.pk),
                }
                if interruption == "folder_mount_mount":
                    request["name"] = "renamed-copy"
                with (
                    patch("core.services.storage_copy_job.dispatch_move"),
                    patch("core.services.storage_folder_copy.dispatch_move"),
                    patch("core.services.storage_move_job.dispatch_move"),
                    patch("core.services.storage_inventory.refresh_policy"),
                ):
                    models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(
                        limit_bytes=14
                    )
                    queued = api.post("/api/v1.0/storage-transfers/", request, format="json")
                    assert queued.status_code == 202, queued.data
                    assert (
                        api.post(
                            "/api/v1.0/storage-transfers/",
                            {**request, "name": "changed-intent"},
                            format="json",
                        ).status_code
                        == 409
                    )
                    if interruption == "folder_s3_mount":
                        # Lose the response after creating the private folder, before
                        # its identity is persisted. Recovery must retain that folder.
                        native_stat = localfs.stat

                        def lost_staging_identity(**kwargs):
                            path = kwargs["normalized_path"]
                            if ".drive-txn-copy-" in path and (nas / path.lstrip("/")).exists():
                                raise RuntimeError("Lost staging identity")
                            return native_stat(**kwargs)

                        with patch.object(localfs, "stat", side_effect=lost_staging_identity):
                            assert execute_move(queued.data["id"]) == "running"
                        assert execute_move(queued.data["id"]) == "conflict"
                        assert (
                            api.post(
                                f"/api/v1.0/storage-transfers/{queued.data['id']}/recover/"
                            ).status_code
                            == 202
                        )
                    for _ in range(5):
                        outcome = execute_move(queued.data["id"])
                        if outcome not in {"busy", "more"}:
                            break
                    assert outcome == "conflict"
                    manifest_url = f"/api/v1.0/storage-transfers/{queued.data['id']}/entries/"
                    manifest = api.get(manifest_url)
                    assert manifest.status_code == 200 and manifest.data["count"] == 3
                    if interruption == "folder_s3_mount":
                        assert manifest.data["results"][0]["retained_staging"] == 1
                        assert len(list((nas / "target").glob(".drive-txn-copy-*"))) == 1
                    stranger_api = APIClient()
                    stranger_api.force_authenticate(factories.UserFactory())
                    assert stranger_api.get(manifest_url).status_code == 404
                    models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(
                        limit_bytes=21
                    )
                    assert (
                        api.post(
                            f"/api/v1.0/storage-transfers/{queued.data['id']}/recover/"
                        ).status_code
                        == 202
                    )
                    for _ in range(5):
                        outcome = execute_move(queued.data["id"])
                        if outcome not in {"busy", "more"}:
                            break
                    assert outcome == "done"
                    assert execute_move(queued.data["id"]) == "done"
                copied_job = models.StorageMoveJob.objects.get(pk=queued.data["id"])
                entries = copied_job.copy_entries
                assert entries.count() == 3 and entries.filter(done=False).count() == 0
                file_entry = entries.get(kind="file")
                if interruption.endswith("_s3"):
                    copied = models.Item.objects.get(pk=file_entry.target_id)
                    with storage_for_item(copied).open(copied.file_key) as content:
                        assert content.read() == b"payload"
                    assert models.Item.objects.filter(
                        pk=entries.get(name="empty").target_id, type="folder"
                    ).exists()
                else:
                    output = nas / "target" / copied_job.payload["title"]
                    assert (
                        output
                        / ("file.txt" if interruption.startswith("folder_s3_") else "native.txt")
                    ).read_bytes() == b"payload"
                    assert (output / "empty").is_dir()
                account = models.StorageQuota.objects.get(key=f"user:{actor.pk}")
                assert (account.used_bytes, account.reserved_bytes) == (21, 0)
                return
            request = {
                "mode": "copy",
                "source": str(item.pk if interruption == "s3_mount" else native.pk),
                "destination": str(roots[1].pk if interruption == "mount_s3" else folder.pk),
                "name": "copied.txt",
            }
            api = APIClient()
            api.force_authenticate(actor)
            with (
                patch("core.services.storage_copy_job.dispatch_move"),
                patch("core.services.storage_inventory.refresh_policy"),
            ):
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=14)
                queued = api.post("/api/v1.0/storage-transfers/", request, format="json")
                assert queued.status_code == 202, queued.data
                assert execute_move(queued.data["id"]) == "failed"
                assert not (nas / "target" / "copied.txt").exists()
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=21)
                queued = api.post("/api/v1.0/storage-transfers/", request, format="json")
                assert queued.status_code == 202, queued.data
                with patch("core.services.storage_quota.commit", side_effect=OSError("lost reply")):
                    assert execute_move(queued.data["id"]) == "running"
                with patch(
                    "core.services.storage_copy_job._write",
                    side_effect=AssertionError("must not recopy"),
                ):
                    assert execute_move(queued.data["id"]) == "done"
            copied_job = models.StorageMoveJob.objects.get(pk=queued.data["id"])
            if interruption == "mount_s3":
                copied = models.Item.objects.get(pk=copied_job.payload["result"])
                assert copied.upload_state == "ready" and copied.mimetype == "text/plain"
                with storage_for_item(copied).open(copied.file_key) as content:
                    assert content.read() == b"payload"
            else:
                assert (nas / "target" / "copied.txt").read_bytes() == b"payload"
                assert (
                    models.StorageResource.objects.get(pk=copied_job.payload["result"]).name
                    == "copied.txt"
                )
            assert (nas / "source" / "native.txt").read_bytes() == b"payload"
            account = models.StorageQuota.objects.get(key=f"user:{actor.pk}")
            assert (account.used_bytes, account.reserved_bytes) == (21, 0)
            return
        if interruption == "scan":
            with patch("storages.backends.s3.S3File", side_effect=AssertionError("must stream")):
                with default_storage.open(item.file_key) as stream:
                    assert stream.size == 7 and stream.read(7) == b"payload"
            with default_storage.open(item.file_key) as stream:
                encoded = MultipartEncoder(
                    fields={"file": ("fixture.txt", stream)}, boundary="fixture"
                )
                chunks = []
                while part := encoded.read(16):
                    chunks.append(part)
                body = b"".join(chunks)
                assert b"payload" in body and len(body) == encoded.len
            item.upload_state = "analyzing"
            item.save(update_fields=["upload_state"])
            expected = analysis_kwargs(item)
            stores[0].connection.meta.client.put_object(
                Bucket=stores[0].bucket_name, Key=item.file_key, Body=b"changed"
            )
            malware_detection_callback(
                item.file_key, ReportStatus.SAFE, None, item_id=item.pk, **expected
            )
            item.refresh_from_db()
            assert item.upload_state == "analyzing"
            malware_detection_callback(
                item.file_key, ReportStatus.SAFE, None, item_id=item.pk, **analysis_kwargs(item)
            )
            item.refresh_from_db()
            assert item.upload_state == "ready"
            return
        token, _ = AccessUserItemService().insert_new_access(item, actor)
        with (
            patch("core.services.storage_file_transfer.dispatch_move"),
            patch("core.services.storage_copy_job.dispatch_move"),
            patch("core.services.storage_file_transfer.inventory.refresh_policy"),
        ):
            if interruption.startswith("copy_source_change"):
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=14)
                api = APIClient()
                api.force_authenticate(actor)
                queued = api.post(
                    "/api/v1.0/storage-transfers/",
                    {"source": str(item.pk), "destination": str(roots[1].pk), "mode": "copy"},
                    format="json",
                )
                assert queued.status_code == 202
                if interruption == "copy_source_changed_after_publish":
                    complete = StorageS3Write.completed

                    def replace_after_publication(write, size, version):
                        stores[0].connection.meta.client.put_object(
                            Bucket=stores[0].bucket_name, Key=item.file_key, Body=b"changed"
                        )
                        return complete(write, size, version)

                    with patch.object(StorageS3Write, "completed", replace_after_publication):
                        assert execute_move(queued.data["id"]) == "conflict"
                    endpoint = f"/api/v1.0/storage-transfers/{queued.data['id']}/accept/"
                    api.force_authenticate(factories.UserFactory())
                    assert api.post(endpoint).status_code == 404
                    api.force_authenticate(actor)
                    accepted = api.post(endpoint)
                    assert accepted.status_code == 200 and accepted.data["state"] == "done", (
                        accepted.data
                    )
                    copied_job = models.StorageMoveJob.objects.get(pk=queued.data["id"])
                    copied = models.Item.objects.get(pk=copied_job.payload["result"])
                    with storage_for_item(copied).open(copied.file_key) as content:
                        assert content.read() == b"payload"
                    with storage_for_item(item).open(item.file_key) as content:
                        assert content.read() == b"changed"
                    account = models.StorageQuota.objects.get(key=f"user:{actor.pk}")
                    assert (account.used_bytes, account.reserved_bytes) == (14, 0)
                    assert api.post(endpoint).status_code == 409
                    return
                open_source = TransferLocation.open

                def replaced_source(location, observation):
                    stores[0].connection.meta.client.put_object(
                        Bucket=stores[0].bucket_name, Key=item.file_key, Body=b"changed"
                    )
                    return open_source(location, observation)

                with patch.object(TransferLocation, "open", replaced_source):
                    assert execute_move(queued.data["id"]) == "failed"
                assert (
                    models.Item.objects.filter(type="file", hard_deleted_at__isnull=True).count()
                    == 1
                )
                return
            if interruption == "copy":
                api = APIClient()
                api.force_authenticate(actor)
                request = {"source": str(item.pk), "destination": str(roots[1].pk), "mode": "copy"}
                rejected = api.post("/api/v1.0/storage-transfers/", request, format="json")
                assert rejected.status_code == 202
                assert execute_move(rejected.data["id"]) == "failed"
                assert (
                    models.Item.objects.filter(type="file", hard_deleted_at__isnull=True).count()
                    == 1
                )
                models.StorageQuota.objects.filter(key=f"user:{actor.pk}").update(limit_bytes=14)
                queued = api.post("/api/v1.0/storage-transfers/", request, format="json")
                assert queued.status_code == 202 and queued.data["mode"] == "copy"
                with patch("core.services.storage_quota.commit", side_effect=OSError("lost reply")):
                    assert execute_move(queued.data["id"]) == "running"
                with patch(
                    "core.services.storage_copy_job._write",
                    side_effect=AssertionError("must not recopy"),
                ):
                    assert execute_move(queued.data["id"]) == "done"
                copied_job = models.StorageMoveJob.objects.get(pk=queued.data["id"])
                copied = models.Item.objects.get(pk=copied_job.payload["copy_item"])
                item.refresh_from_db()
                assert copied.pk != item.pk
                assert copied.upload_state == "ready" and copied.size == 7
                assert copied.storage_space_id == roots[1].storage_space_id
                assert item.storage_space_id == roots[0].storage_space_id
                with storage_for_item(copied).open(copied.file_key) as content:
                    assert content.read() == b"payload"
                account = models.StorageQuota.objects.get(key=f"user:{actor.pk}")
                assert (account.used_bytes, account.reserved_bytes) == (14, 0)
                return
            LockService(item).lock("editing")
            with pytest.raises(StorageWriteConflict):
                enqueue_s3_transfer(actor=actor, source=item, destination=roots[1])
            LockService(item).unlock()
            api = APIClient()
            api.force_authenticate(actor)
            queued = api.post(
                "/api/v1.0/storage-transfers/",
                {
                    "source": str(item.pk),
                    "destination": str(roots[1].pk),
                },
                format="json",
            )
            assert queued.status_code == 202, queued.data
            job = models.StorageMoveJob.objects.get(pk=queued.data["id"])
            api.force_authenticate(factories.UserFactory())
            assert api.get(f"/api/v1.0/storage-transfers/{job.pk}/").status_code == 404
            if interruption == "source_change":
                publish = S3TransferWrite.publish

                def change_source(write, size):
                    write.source_client.put_object(
                        Bucket=write.source_storage.bucket_name,
                        Key=write.original_key,
                        Body=b"changed",
                    )
                    publish(write, size)

                with patch.object(S3TransferWrite, "publish", change_source):
                    assert execute_move(job.pk) == "failed"
                item.refresh_from_db()
                assert item.storage_space_id == roots[0].storage_space_id
                job.refresh_from_db()
                assert not stores[1].exists(job.operation.publication["key"])
                account = models.StorageQuota.objects.get(key=f"user:{actor.pk}")
                assert (account.used_bytes, account.reserved_bytes) == (7, 0)
                return
            if interruption == "collision":
                publish = S3TransferWrite.publish

                def create_concurrent_destination(write, size):
                    publish(write, size)
                    write.client.put_object(Bucket=write.bucket, Key=write.key, Body=b"outside")

                with patch.object(S3TransferWrite, "publish", create_concurrent_destination):
                    assert execute_move(job.pk) == "running"
                item.refresh_from_db()
                assert item.storage_space_id == roots[0].storage_space_id
                job.refresh_from_db()
                with stores[1].open(job.operation.publication["key"]) as content:
                    assert content.read() == b"outside"
                return
            with patch.object(S3TransferWrite, "finish", side_effect=OSError("lost completion")):
                assert execute_move(job.pk) == "running"
            item.refresh_from_db()
            assert item.storage_space_id == roots[0].storage_space_id
            with patch(
                "core.services.storage_file_transfer.stream_to_s3_object",
                side_effect=AssertionError("must not recopy"),
            ):
                assert execute_move(job.pk) == "cleanup"
        item.refresh_from_db()
        assert item.storage_space_id == roots[1].storage_space_id
        item.save(update_fields=["title"])
        assert models.StorageUsage.objects.get(item=item).key == canonical_key
        assert str(item.path) == f"{roots[1].path}.{item.pk}"
        with storage_for_item(item).open(item.file_key) as content:
            assert content.read() == b"payload"
        with stores[0].open(source_key) as content:
            assert content.read() == b"payload"
        account = models.StorageQuota.objects.get(key=f"user:{actor.pk}")
        assert (account.used_bytes, account.reserved_bytes) == (7, 0)
        assert (
            models.StorageQuota.objects.get(key=f"space:{roots[0].storage_space_id}").used_bytes
            == 0
        )
        assert (
            models.StorageQuota.objects.get(key=f"space:{roots[1].storage_space_id}").used_bytes
            == 7
        )
        with pytest.raises(AccessUserItemNotAllowed):
            AccessUserItemService().get_access_user_item(token)
        if interruption == "lost_completion":
            with (
                patch("core.services.storage_file_transfer.dispatch_move"),
                patch("core.services.storage_file_transfer.inventory.refresh_policy"),
            ):
                returned = enqueue_s3_transfer(actor=actor, source=item, destination=roots[0])
                assert execute_move(returned.pk) == "cleanup"
            item.refresh_from_db()
            assert item.file_key != source_key
            with storage_for_item(item).open(item.file_key) as content:
                assert content.read() == b"payload"
            with stores[0].open(source_key) as content:
                assert content.read() == b"payload"
            account.refresh_from_db()
            assert (account.used_bytes, account.reserved_bytes) == (7, 0)
        if interruption == "cleanup":
            client = stores[0].connection.meta.client
            job.refresh_from_db()
            version = job.operation.publication["source_version"]
            assert version and version != "null"
            assert execute_move(job.pk) == "cleanup"  # Retention still applies.
            settings.STORAGE_BACKUP_RETENTION_DAYS = 0
            grant = models.StorageGrant.objects.get(space=roots[0].storage_space, user=actor)
            grant.writable = False
            grant.save()
            assert execute_move(job.pk) == "cleanup"
            assert client.head_object(
                Bucket=stores[0].bucket_name, Key=source_key, VersionId=version
            )
            grant.writable = True
            grant.save()
            LockService(item).lock("synthetic-cleanup-lock")
            assert execute_move(job.pk) == "cleanup"
            LockService(item).unlock()
            client.put_object(
                Bucket=stores[0].bucket_name, Key=source_key, Body=b"new external object"
            )
            delete = client.delete_object

            def lost_delete_reply(**kwargs):
                assert kwargs["VersionId"] == version
                delete(**kwargs)
                raise OSError("Lost deletion response")

            with patch(
                "core.services.storage_file_transfer.storage_for_backend", return_value=stores[0]
            ):
                with patch.object(client, "delete_object", side_effect=lost_delete_reply):
                    assert execute_move(job.pk) == "cleanup"
                assert execute_move(job.pk) == "done"
            assert execute_move(job.pk) == "done"
            with stores[0].open(source_key) as content:
                assert content.read() == b"new external object"
            versions = client.list_object_versions(Bucket=stores[0].bucket_name, Prefix=source_key)
            assert version not in [row["VersionId"] for row in versions.get("Versions", [])]
    finally:
        for storage in stores:
            client = storage.connection.meta.client
            if interruption == "cleanup" and storage is stores[0]:
                for page in client.get_paginator("list_object_versions").paginate(
                    Bucket=storage.bucket_name
                ):
                    for entry in [*page.get("Versions", []), *page.get("DeleteMarkers", [])]:
                        client.delete_object(
                            Bucket=storage.bucket_name,
                            Key=entry["Key"],
                            VersionId=entry["VersionId"],
                        )
            for page in client.get_paginator("list_objects_v2").paginate(
                Bucket=storage.bucket_name
            ):
                for entry in page.get("Contents", []):
                    client.delete_object(Bucket=storage.bucket_name, Key=entry["Key"])
            client.delete_bucket(Bucket=storage.bucket_name)
