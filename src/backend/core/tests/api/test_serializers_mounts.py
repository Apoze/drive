"""Direct contract tests for mount serializers."""
# pylint: disable=missing-function-docstring,missing-class-docstring,line-too-long

from __future__ import annotations

from django.utils import timezone

from core.api.serializers_mounts import (
    MountBrowseResponseSerializer,
    MountPreviewInfoSerializer,
    MountShareLinkCreateResponseSerializer,
    MountShareLinkPublicBrowseResponseSerializer,
    MountStreamTicketRequestSerializer,
    MountStreamTicketResponseSerializer,
)


def _abilities_payload() -> dict[str, bool]:
    return {
        "children_list": True,
        "create_folder": True,
        "move": True,
        "rename": True,
        "destroy": False,
        "upload": True,
        "duplicate": False,
        "download": True,
        "preview": True,
        "wopi": False,
        "share_link_create": True,
    }


def test_mount_stream_ticket_request_and_response_serializers_validate_contract():
    request_serializer = MountStreamTicketRequestSerializer(
        data={
            "path": "/folder/report.pdf",
            "disposition": "inline",
            "purpose": "preview",
        }
    )
    response_serializer = MountStreamTicketResponseSerializer(
        data={
            "stream_url": "/api/v1.0/mount-stream/abc123/",
            "expires_at": 1735689600000,
            "etag": '"etag-v1"',
            "content_type": "application/pdf",
            "content_length": 42,
            "supports_range": True,
        }
    )

    assert request_serializer.is_valid(), request_serializer.errors
    assert response_serializer.is_valid(), response_serializer.errors
    assert request_serializer.validated_data["purpose"] == "preview"
    assert response_serializer.validated_data["supports_range"] is True


def test_mount_stream_ticket_request_serializer_rejects_invalid_purpose():
    serializer = MountStreamTicketRequestSerializer(
        data={
            "path": "/folder/report.pdf",
            "disposition": "inline",
            "purpose": "edit",
        }
    )

    assert serializer.is_valid() is False
    assert "purpose" in serializer.errors


def test_mount_preview_info_serializer_validates_stream_contract():
    serializer = MountPreviewInfoSerializer(
        data={
            "mount_id": "alpha-mount",
            "normalized_path": "/folder/report.pdf",
            "name": "report.pdf",
            "size": 42,
            "mimetype": "application/pdf",
            "preview_kind": "pdf",
            "is_wopi_supported": False,
            "can_download": True,
            "can_edit_text": False,
            "stream_url": "/api/v1.0/mount-stream/abc123/",
            "stream_expires_at": 1735689600000,
            "inline_url": "/api/v1.0/mounts/alpha-mount/inline-preview/?path=%2Ffolder%2Freport.pdf",
            "download_url": "/api/v1.0/mounts/alpha-mount/download/?path=%2Ffolder%2Freport.pdf",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["preview_kind"] == "pdf"
    assert serializer.validated_data["can_download"] is True


def test_mount_browse_response_serializer_validates_entry_and_abilities_payload():
    modified_at = timezone.now().isoformat()
    serializer = MountBrowseResponseSerializer(
        data={
            "mount_id": "alpha-mount",
            "normalized_path": "/folder",
            "capabilities": {
                "mount.preview": True,
                "mount.upload": True,
                "mount.share_link": True,
            },
            "entry": {
                "mount_id": "alpha-mount",
                "normalized_path": "/folder",
                "entry_type": "folder",
                "name": "folder",
                "size": None,
                "modified_at": modified_at,
                "abilities": _abilities_payload(),
            },
            "children": {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "mount_id": "alpha-mount",
                        "normalized_path": "/folder/report.pdf",
                        "entry_type": "file",
                        "name": "report.pdf",
                        "size": 42,
                        "modified_at": modified_at,
                        "abilities": _abilities_payload(),
                    }
                ],
            },
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["entry"]["abilities"]["preview"] is True
    assert serializer.validated_data["children"]["results"][0]["entry_type"] == "file"


def test_mount_share_link_serializers_validate_create_and_public_browse_payloads():
    modified_at = timezone.now().isoformat()
    create_serializer = MountShareLinkCreateResponseSerializer(
        data={
            "mount_id": "alpha-mount",
            "normalized_path": "/folder/report.pdf",
            "token": "token-123",
            "share_url": "https://drive.example.com/share/mount/token-123",
        }
    )
    public_browse_serializer = MountShareLinkPublicBrowseResponseSerializer(
        data={
            "normalized_path": "/",
            "entry": {
                "normalized_path": "/",
                "entry_type": "folder",
                "name": "shared-folder",
                "size": None,
                "modified_at": modified_at,
            },
            "children": {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "normalized_path": "/report.pdf",
                        "entry_type": "file",
                        "name": "report.pdf",
                        "size": 42,
                        "modified_at": modified_at,
                    }
                ],
            },
        }
    )

    assert create_serializer.is_valid(), create_serializer.errors
    assert public_browse_serializer.is_valid(), public_browse_serializer.errors
    assert create_serializer.validated_data["token"] == "token-123"
    assert public_browse_serializer.validated_data["children"]["results"][0]["normalized_path"] == (
        "/report.pdf"
    )
