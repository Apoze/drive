"""Destination choices use the same space entrances as the explorer."""

import pytest
from rest_framework.exceptions import NotFound

from core import factories, models
from core.services.docs_destinations import destinations


@pytest.mark.django_db
def test_destination_paging_and_restricted_entrances(settings):
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    user, other = factories.UserFactory.create_batch(2)
    backend = models.StorageBackend.objects.create(
        registry_id="picker-s3",
        family="s3",
        name="S3",
        organization="local",
    )
    root = models.Item.objects.create(type="folder", title="Root", storage_backend=backend)
    space = models.StorageSpace.objects.create(
        backend=backend,
        name="Visible",
        root_item=root,
        explicit_access=True,
    )
    models.Item.objects.filter(pk=root.pk).update(storage_space=space)
    root.refresh_from_db()
    child = models.Item.objects.create_child(parent=root, type="folder", title="Allowed")
    models.StorageGrant.objects.create(space=space, user=user, root_item=child, writable=True)
    rows = destinations(user, {"space_id": space.pk})["results"]
    assert [row["id"] for row in rows] == [str(child.pk)]
    assert rows[0]["can_create"]
    current = destinations(user, {"space_id": space.pk, "parent_id": child.pk})["current"]
    assert current["id"] == str(child.pk) and current["can_create"]
    with pytest.raises(NotFound):
        destinations(other, {"space_id": space.pk, "parent_id": child.pk})
    with pytest.raises(NotFound):
        destinations(other, {"space_id": space.pk})
    mount = models.StorageBackend.objects.create(
        registry_id="picker-mount",
        family="mount",
        name="Mount",
        organization="local",
    )
    mounted_space = models.StorageSpace.objects.create(backend=mount, name="Mounted")
    models.StorageGrant.objects.create(space=mounted_space, user=user, path="/", writable=False)
    anchor = models.StorageResource.objects.create(
        namespace=mount.namespace,
        identity_key="picker-root",
        path="/",
        parent_path="/",
        name="Root",
        kind="folder",
    )
    page = destinations(user, {"limit": 1})
    assert page["count"] == 2 and page["next_offset"] == 1
    assert len(page["results"]) == 1
    mount_rows = destinations(user, {"space_id": mounted_space.pk})["results"]
    assert [row["id"] for row in mount_rows] == [str(anchor.pk)]
    assert not mount_rows[0]["can_create"]
    mounted_space.grants.update(writable=True)
    assert not destinations(user, {"space_id": mounted_space.pk})["results"][0]["can_create"]
    assert destinations(other, {})["count"] == 0


@pytest.mark.django_db
def test_mounted_children_page_keeps_docs_and_files_in_one_order(settings):
    from unittest.mock import patch  # noqa: PLC0415

    from rest_framework.test import APIRequestFactory, force_authenticate  # noqa: PLC0415

    from core.api.storage_resources import ResourceViewSet  # noqa: PLC0415

    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    user = factories.UserFactory()
    backend = models.StorageBackend.objects.create(
        registry_id="mixed-docs", family="mount", name="NAS", organization="local"
    )
    space = models.StorageSpace.objects.create(
        backend=backend, owner=user, root_path="/", name="Mixed"
    )
    root = models.StorageResource.objects.create(
        namespace=backend.namespace,
        identity_key="path:/",
        path="/",
        kind="folder",
        name="Root",
        parent_path="/",
    )
    file = models.StorageResource.objects.create(
        namespace=backend.namespace,
        identity_key="path:/A.txt",
        path="/A.txt",
        parent_path="/",
        kind="file",
        name="A.txt",
    )
    document = models.Item.objects.create(type="docs", title="B document", creator=user)
    models.DocsBinding.objects.create(
        item=document, mounted_parent=root, anchor_space=space, state="active", applied_revision=1
    )
    models.ItemAccess.objects.create(item=document, user=user, role="owner")
    request = APIRequestFactory().get("/children/", {"limit": 1, "offset": 1})
    force_authenticate(request, user=user)
    with (
        patch.object(ResourceViewSet, "_target", return_value=(root, space)),
        patch(
            "core.api.storage_resources.serialize_items",
            side_effect=lambda items, _request: [
                {"id": str(row.pk), "kind": row.type} for row in items
            ],
        ),
        patch(
            "core.api.storage_resources.serialize_mounted",
            side_effect=lambda row, *_args: {"id": str(row.pk), "kind": row.kind},
        ),
    ):
        response = ResourceViewSet.as_view({"get": "children"})(request, pk=str(root.pk))
        search = APIRequestFactory().get("/api/v1.0/resources/", {"space": str(space.pk)})
        force_authenticate(search, user)
        collection = ResourceViewSet.as_view({"get": "list"})(search)
    assert response.status_code == 200
    assert response.data["count"] == 2
    assert response.data["results"] == [{"id": str(document.pk), "kind": "docs"}]
    assert models.StorageResource.objects.filter(pk=file.pk).exists()
    assert collection.status_code == 200
    assert str(document.pk) in {row["id"] for row in collection.data["results"]}
