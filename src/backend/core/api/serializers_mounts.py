"""Serializers for mount browse endpoints (contract-level)."""

from __future__ import annotations

from rest_framework import serializers

# pylint: disable=abstract-method


class MountEntryAbilitiesSerializer(serializers.Serializer):
    """Per-entry abilities used by the Explorer to avoid dead actions."""

    children_list = serializers.BooleanField()
    upload = serializers.BooleanField()
    duplicate = serializers.BooleanField()
    download = serializers.BooleanField()
    preview = serializers.BooleanField()
    wopi = serializers.BooleanField()
    share_link_create = serializers.BooleanField()


class MountEntrySerializer(serializers.Serializer):
    """Serialize a virtual mount entry identified by (mount_id, normalized_path)."""

    mount_id = serializers.CharField()
    normalized_path = serializers.CharField()
    entry_type = serializers.ChoiceField(choices=["file", "folder"])
    name = serializers.CharField()
    size = serializers.IntegerField(required=False, allow_null=True)
    modified_at = serializers.DateTimeField(required=False, allow_null=True)
    abilities = MountEntryAbilitiesSerializer()


class MountBrowseChildrenSerializer(serializers.Serializer):
    """Limit/offset paginated children payload (DRF-compatible)."""

    count = serializers.IntegerField()
    next = serializers.CharField(required=False, allow_null=True)
    previous = serializers.CharField(required=False, allow_null=True)
    results = MountEntrySerializer(many=True)


class MountBrowseResponseSerializer(serializers.Serializer):
    """Browse response: current entry + children if folder."""

    mount_id = serializers.CharField()
    normalized_path = serializers.CharField()
    capabilities = serializers.DictField(child=serializers.BooleanField())
    entry = MountEntrySerializer()
    children = MountBrowseChildrenSerializer(allow_null=True)


class MountPreviewInfoSerializer(serializers.Serializer):
    """Resolved preview contract for one mount file."""

    mount_id = serializers.CharField()
    normalized_path = serializers.CharField()
    name = serializers.CharField()
    size = serializers.IntegerField(required=False, allow_null=True)
    mimetype = serializers.CharField()
    preview_kind = serializers.ChoiceField(
        choices=[
            "image",
            "video",
            "audio",
            "pdf",
            "text",
            "archive",
            "wopi",
            "unsupported",
        ]
    )
    is_wopi_supported = serializers.BooleanField()
    can_download = serializers.BooleanField()
    can_edit_text = serializers.BooleanField()
    stream_url = serializers.CharField(required=False, allow_null=True)
    stream_expires_at = serializers.IntegerField(required=False, allow_null=True)
    inline_url = serializers.CharField(required=False, allow_null=True)
    download_url = serializers.CharField(required=False, allow_null=True)


class MountStreamTicketRequestSerializer(serializers.Serializer):
    """Request payload for mount browser-stream ticket creation."""

    path = serializers.CharField()
    disposition = serializers.ChoiceField(choices=["inline", "attachment"])
    purpose = serializers.ChoiceField(choices=["preview", "download", "archive"])


class MountStreamTicketResponseSerializer(serializers.Serializer):
    """Response payload for mount browser-stream ticket creation."""

    stream_url = serializers.CharField()
    expires_at = serializers.IntegerField()
    etag = serializers.CharField()
    content_type = serializers.CharField()
    content_length = serializers.IntegerField(required=False, allow_null=True)
    supports_range = serializers.BooleanField()


class MountShareLinkCreateRequestSerializer(serializers.Serializer):
    """Request body for mount share link creation."""

    path = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class MountShareLinkCreateResponseSerializer(serializers.Serializer):
    """Response payload for mount share link creation."""

    mount_id = serializers.CharField()
    normalized_path = serializers.CharField()
    token = serializers.CharField()
    share_url = serializers.CharField()


class MountShareLinkPublicEntrySerializer(serializers.Serializer):
    """Public mount share link entry (no mount_id; relative paths only)."""

    normalized_path = serializers.CharField()
    entry_type = serializers.ChoiceField(choices=["file", "folder"])
    name = serializers.CharField()
    size = serializers.IntegerField(required=False, allow_null=True)
    modified_at = serializers.DateTimeField(required=False, allow_null=True)


class MountShareLinkPublicBrowseChildrenSerializer(serializers.Serializer):
    """Limit/offset paginated public children payload (DRF-compatible)."""

    count = serializers.IntegerField()
    next = serializers.CharField(required=False, allow_null=True)
    previous = serializers.CharField(required=False, allow_null=True)
    results = MountShareLinkPublicEntrySerializer(many=True)


class MountShareLinkPublicBrowseResponseSerializer(serializers.Serializer):
    """Public browse response: current entry + children if folder."""

    normalized_path = serializers.CharField()
    entry = MountShareLinkPublicEntrySerializer()
    children = MountShareLinkPublicBrowseChildrenSerializer(allow_null=True)
