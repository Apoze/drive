"""Folder link contexts remain scoped and cannot outlive their original bearer."""

from contextlib import contextmanager
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from django.contrib.auth.models import AnonymousUser

import pytest
from suite_identity.document_transport import document_links

from core import factories, models
from core.utils.share_links import compute_item_share_token


@pytest.mark.django_db
def test_folder_context_limits_document_tree_and_follows_revocation(settings):
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    owner = factories.UserFactory()
    folder = models.Item.objects.create(type="folder", title="Folder", link_reach="public")
    models.ItemAccess.objects.create(item=folder, user=owner, role="owner")
    document, sibling = [
        models.Item.objects.create_child(parent=folder, type="docs", title=name, creator=owner)
        for name in ("Document", "Sibling")
    ]
    child = models.Item.objects.create_child(parent=document, type="docs", title="Child")
    for item in (document, sibling, child):
        models.DocsBinding.objects.create(item=item, state="active", applied_revision=1)
    anonymous = AnonymousUser()
    assert not document.get_abilities(anonymous)["retrieve"]
    bearer = compute_item_share_token(folder.pk, folder.share_link_nonce)
    previous = document_links.set(
        {str(document.docs_binding.document_id): {"kind": "item", "token": bearer}}
    )
    try:
        assert document.get_abilities(anonymous)["retrieve"]
        assert child.get_abilities(anonymous)["retrieve"]
        assert not sibling.get_abilities(anonymous)["retrieve"]
        assert not document.get_abilities(anonymous)["update"]
        assert not document.get_abilities(anonymous)["accesses_manage"]
        models.Item.objects.filter(pk=folder.pk).update(share_link_nonce=uuid4())
        assert not document.get_abilities(anonymous)["retrieve"]
        assert not child.get_abilities(anonymous)["retrieve"]
    finally:
        document_links.reset(previous)
    models.Item.objects.filter(pk=document.pk).update(link_reach="public")
    document.refresh_from_db()
    assert document.get_abilities(anonymous)["retrieve"]
    assert child.get_abilities(anonymous)["retrieve"]
    assert not sibling.get_abilities(anonymous)["retrieve"]
    from core.services.docs_quota import initialize_usage  # noqa: PLC0415
    from core.services.item_exports import build_zip_stream, export_descendants  # noqa: PLC0415

    for item in (document, sibling, child):
        initialize_usage(item, size=0, version="current")
    folder.refresh_from_db()
    link = {"kind": "item", "token": compute_item_share_token(folder.pk, folder.share_link_nonce)}

    @contextmanager
    def pdf(data, *, actor, limit):
        assert actor == {"links": {data["document_id"]: link}}
        assert data["version"] == "current" and limit > 100
        with BytesIO(b"%PDF-1.4\n%%EOF") as source:
            yield source

    with patch("suite_identity.document_transport.pdf_stream", side_effect=pdf):
        archive = build_zip_stream(
            export_descendants(folder, anonymous), anonymous, document_context=link
        )
        with ZipFile(BytesIO(b"".join(archive))) as result:
            assert set(result.namelist()) == {"Document.pdf", "Document/Child.pdf", "Sibling.pdf"}
