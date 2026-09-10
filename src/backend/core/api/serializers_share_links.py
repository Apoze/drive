"""Serializers for token-enforced public share links (unauthenticated)."""

from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from rest_framework import serializers

from core import models
from core.api import utils
from core.utils.public_url import join_public_url


class PublicShareItemSerializer(serializers.ModelSerializer):
    """Public-facing item serializer for share link browsing."""

    upload_state = serializers.SerializerMethodField(read_only=True)
    url = serializers.SerializerMethodField(read_only=True)
    url_permalink = serializers.SerializerMethodField(read_only=True)
    url_preview = serializers.SerializerMethodField(read_only=True)
    url_docs = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = models.Item
        fields = [
            "id",
            "title",
            "type",
            "filename",
            "mimetype",
            "size",
            "created_at",
            "updated_at",
            "upload_state",
            "url",
            "url_permalink",
            "url_preview",
            "url_docs",
        ]
        read_only_fields = fields

    def _share_query(self) -> str:
        token = self.context.get("share_token")
        if not token:
            return ""
        return urlencode({"share_token": token})

    def _with_share_token(self, base_url: str | None) -> str | None:
        if not base_url:
            return None
        q = self._share_query()
        if not q:
            return base_url
        return f"{base_url}{'&' if '?' in base_url else '?'}{q}"

    def get_upload_state(self, item):
        """Return the effective upload state (pending TTL applied deterministically)."""
        return item.effective_upload_state()

    def get_url_docs(self, item):
        """Carry the folder bearer in a fragment, never in a server request URL."""
        if item.type != "docs" or not settings.DOCS_DRIVE_ENABLED or not settings.DOCS_PUBLIC_URL:
            return None
        token = self.context.get("share_token")
        if not token:
            return None
        from core.services.docs_links import context_url  # noqa: PLC0415

        return context_url(item, self.context.get("share_kind", "item"), token)

    def get_url(self, item):
        """Return the token-bound media URL for a shared file (or None)."""
        effective_upload_state = item.effective_upload_state()
        if (
            item.type != models.ItemTypeChoices.FILE
            or effective_upload_state
            in {
                models.ItemUploadStateChoices.PENDING,
                models.ItemUploadStateChoices.EXPIRED,
            }
            or item.filename is None
        ):
            return None

        base = utils.item_media_url(item)
        return self._with_share_token(base)

    def get_url_permalink(self, item):
        """Return the token-bound download endpoint for a shared file."""
        if self.get_url(item) is None:
            return None
        path = reverse("items-download", kwargs={"pk": item.id})
        return self._with_share_token(join_public_url(settings.MEDIA_BASE_URL, path))

    def get_url_preview(self, item):
        """Return the token-bound preview URL for a shared file (or None)."""
        effective_upload_state = item.effective_upload_state()
        if (
            item.type != models.ItemTypeChoices.FILE
            or effective_upload_state
            in {
                models.ItemUploadStateChoices.PENDING,
                models.ItemUploadStateChoices.EXPIRED,
            }
            or item.filename is None
            or not utils.is_previewable_item(item)
        ):
            return None

        base = utils.item_media_url(item, preview=True)
        return self._with_share_token(base)
