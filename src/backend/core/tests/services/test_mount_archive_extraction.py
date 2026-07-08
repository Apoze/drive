"""Direct tests for mount archive extraction preflight helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from types import SimpleNamespace
from unittest import mock

import pytest
from lasuite.drf.models.choices import RoleChoices

from core import factories, models
from core.mounts.providers.base import MountEntry, MountProviderError
from core.services.mount_archive_extraction import (
    MountArchiveExtractionPreflightError,
    MountArchiveExtractionStartRequest,
    ResolvedMountArchiveDestination,
    ResolvedMountArchiveExtractionJob,
    ensure_mount_archive_extract_hardening,
    get_mount_archive_source_item_or_error,
    resolve_mount_archive_destination,
    resolve_mount_archive_extraction_job,
    validate_mount_archive_source_item,
)
from core.services.mount_security import MOUNT_ARCHIVE_EXTRACT_UNSAFE_ERROR_CODE

pytestmark = pytest.mark.django_db


def test_ensure_mount_archive_extract_hardening_fails_closed(monkeypatch):
    monkeypatch.delenv("MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT", raising=False)

    with pytest.raises(MountArchiveExtractionPreflightError) as exc_info:
        ensure_mount_archive_extract_hardening()

    assert exc_info.value.error_kind == "permission_denied"
    assert exc_info.value.public_code == MOUNT_ARCHIVE_EXTRACT_UNSAFE_ERROR_CODE


def test_validate_mount_archive_source_item_accepts_ready_zip_with_retrieve_ability():
    user = factories.UserFactory()
    archive_item = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FILE,
        title="archive.zip",
        filename="archive.zip",
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"zip",
        upload_bytes__filename="archive.zip",
        users=[(user, RoleChoices.OWNER)],
    )

    assert validate_mount_archive_source_item(user=user, archive_item=archive_item) == archive_item


def test_validate_mount_archive_source_item_rejects_suspicious_file():
    user = factories.UserFactory()
    archive_item = factories.ItemFactory(
        creator=user,
        type=models.ItemTypeChoices.FILE,
        title="archive.zip",
        filename="archive.zip",
        users=[(user, RoleChoices.OWNER)],
    )
    archive_item.upload_state = models.ItemUploadStateChoices.SUSPICIOUS
    archive_item.effective_upload_state = lambda: models.ItemUploadStateChoices.READY

    with pytest.raises(MountArchiveExtractionPreflightError) as exc_info:
        validate_mount_archive_source_item(user=user, archive_item=archive_item)

    assert exc_info.value.error_kind == "permission_denied"
    assert exc_info.value.public_code == "archive.extract.suspicious"


def test_get_mount_archive_source_item_or_error_returns_item_and_maps_not_found():
    item = factories.ItemFactory(type=models.ItemTypeChoices.FILE, title="a.zip", filename="a.zip")
    assert get_mount_archive_source_item_or_error(archive_item_id=str(item.id)) == item

    with pytest.raises(MountArchiveExtractionPreflightError) as exc_info:
        get_mount_archive_source_item_or_error(
            archive_item_id="00000000-0000-0000-0000-000000000000"
        )

    assert exc_info.value.error_kind == "not_found"
    assert exc_info.value.public_code == "item.not_found"


def test_resolve_mount_archive_destination_validates_capabilities_and_folder(monkeypatch):
    provider = mock.Mock()
    provider.stat.return_value = MountEntry(
        entry_type="folder",
        normalized_path="/dest",
        name="dest",
    )
    io = mock.Mock()
    io.supports.return_value = True

    monkeypatch.setattr(
        "core.services.mount_archive_extraction.get_mount_provider",
        lambda _provider_name: provider,
    )
    monkeypatch.setattr(
        "core.services.mount_archive_extraction.resolve_mount_provider_io_capabilities",
        lambda **_kwargs: io,
    )

    resolved = resolve_mount_archive_destination(
        mount={"provider": "smb"},
        destination_path="dest",
    )

    assert resolved == ResolvedMountArchiveDestination(
        mount={"provider": "smb"},
        provider=provider,
        normalized_destination_path="/dest",
        destination_entry=provider.stat.return_value,
    )
    provider.stat.assert_called_once_with(mount={"provider": "smb"}, normalized_path="/dest")


def test_resolve_mount_archive_destination_maps_invalid_path_and_not_found(monkeypatch):
    provider = mock.Mock()
    io = mock.Mock()
    io.supports.return_value = True

    monkeypatch.setattr(
        "core.services.mount_archive_extraction.get_mount_provider",
        lambda _provider_name: provider,
    )
    monkeypatch.setattr(
        "core.services.mount_archive_extraction.resolve_mount_provider_io_capabilities",
        lambda **_kwargs: io,
    )

    with pytest.raises(MountArchiveExtractionPreflightError) as invalid_exc:
        resolve_mount_archive_destination(mount={"provider": "smb"}, destination_path="/../bad")

    assert invalid_exc.value.public_code == "mount.path.invalid"

    provider.stat.side_effect = MountProviderError(
        failure_class="not_found",
        next_action_hint="retry",
        public_message="missing",
        public_code="mount.path.not_found",
    )

    with pytest.raises(MountArchiveExtractionPreflightError) as missing_exc:
        resolve_mount_archive_destination(mount={"provider": "smb"}, destination_path="/dest")

    assert missing_exc.value.error_kind == "not_found"
    assert missing_exc.value.public_code == "mount.path.not_found"


def test_resolve_mount_archive_extraction_job_returns_stable_task_payload(monkeypatch):
    user = factories.UserFactory()
    start_request = MountArchiveExtractionStartRequest(
        archive_item_id="archive-1",
        destination_path="folder",
        mode="selection",
        selection_paths=["folder/a.txt"],
    )

    monkeypatch.setenv("MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT", "true")
    monkeypatch.setattr(
        "core.services.mount_archive_extraction.get_entitlements_backend",
        lambda: SimpleNamespace(can_upload=lambda _user: {"result": True}),
    )
    monkeypatch.setattr(
        "core.services.mount_archive_extraction.get_mount_archive_source_item_or_error",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        "core.services.mount_archive_extraction.validate_mount_archive_source_item",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        "core.services.mount_archive_extraction.resolve_mount_archive_destination",
        lambda **_kwargs: ResolvedMountArchiveDestination(
            mount={"provider": "smb"},
            provider=object(),
            normalized_destination_path="/folder",
            destination_entry=MountEntry(
                entry_type="folder",
                normalized_path="/folder",
                name="folder",
            ),
        ),
    )

    resolved = resolve_mount_archive_extraction_job(
        user=user,
        mount_id="mount-1",
        mount={"provider": "smb"},
        start_request=start_request,
    )

    assert resolved == ResolvedMountArchiveExtractionJob(
        archive_item_id="archive-1",
        mount_id="mount-1",
        destination_path="/folder",
        user_id=str(user.id),
        mode="selection",
        selection_paths=["folder/a.txt"],
    )
    assert resolved.as_task_kwargs() == {
        "archive_item_id": "archive-1",
        "mount_id": "mount-1",
        "destination_path": "/folder",
        "user_id": str(user.id),
        "mode": "selection",
        "selection_paths": ["folder/a.txt"],
    }
