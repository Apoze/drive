"""Bounded document pages reuse SQL decisions only while serializing that response."""

from unittest.mock import patch
from uuid import uuid4

from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from core import factories, models
from core.api.docs_documents import DocumentAuthorizationView
from core.services.docs_resources import document_abilities, document_page


@pytest.mark.django_db
def test_document_page_batches_locations_and_drops_permission_cache(settings):
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    owner = factories.UserFactory()
    backend = models.StorageBackend.objects.create(
        registry_id="docs-page", family="s3", name="Storage", organization="local"
    )
    folder = models.Item.objects.create(type="folder", title="Folder", storage_backend=backend)
    space = models.StorageSpace.objects.create(
        backend=backend,
        root_item=folder,
        owner=owner,
        name="Space",
        explicit_access=True,
        allow_sharing=False,
    )
    models.Item.objects.filter(pk=folder.pk).update(storage_space=space)
    grant = models.StorageGrant.objects.create(space=space, user=owner, writable=True)
    models.ItemAccess.objects.create(item=folder, user=owner, role="owner")
    identifiers = [uuid4() for _ in range(50)]
    models.Item.objects.bulk_create(
        [
            models.Item(
                id=identifier,
                path=f"{folder.path}.{identifier}",
                type="docs",
                title=f"Document {index}",
                creator=owner,
            )
            for index, identifier in enumerate(identifiers)
        ]
    )
    models.DocsBinding.objects.bulk_create(
        [
            models.DocsBinding(item_id=identifier, state="active", applied_revision=1)
            for identifier in identifiers
        ]
    )
    page = list(models.Item.objects.filter(pk__in=identifiers).select_related("docs_binding"))
    with CaptureQueriesContext(connection) as before:
        expected = [document_abilities(item, owner) for item in page]
    with CaptureQueriesContext(connection) as after, document_page(page, owner):
        observed = [document_abilities(item, owner) for item in page]
    assert observed == expected
    assert len(after) < 25 and len(after) < len(before) // 10
    assert all(row["update"] for row in observed)
    from core.api.filters import ItemFilter  # noqa: PLC0415

    document_filter = ItemFilter(
        {"category": "doc"}, queryset=models.Item.objects.filter(pk__in=identifiers)
    )
    assert document_filter.qs.count() == len(identifiers)
    models.ItemFavorite.objects.create(item=page[0], user=owner)
    request = APIRequestFactory().post("/authorization/", {}, format="json")
    force_authenticate(request, user=owner)
    ids = [str(item.docs_binding.document_id) for item in page]
    with (
        CaptureQueriesContext(connection) as api_queries,
        patch("suite_identity.document_transport.receive", return_value={"document_ids": ids}),
    ):
        result = DocumentAuthorizationView.as_view()(request)
    assert result.status_code == 200
    assert result.data[ids[0]]["is_favorite"]
    assert all(row["destination"] == str(folder.pk) for row in result.data.values())
    assert len(api_queries) < 30
    grant.writable = False
    grant.save(update_fields=["writable"])
    assert not document_abilities(page[0], owner)["update"]
