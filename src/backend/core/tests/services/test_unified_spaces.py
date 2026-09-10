"""Space grants and budgets constrain the existing file endpoints."""

from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Group

import pytest
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.test import APIClient

from core import factories, models
from core.api import viewsets
from core.services import storage_quota as quota
from core.services.item_media import check_share_access
from core.services.storage_access import bound_queryset, cache_item_grants
from core.services.storage_inventory import initialize_items, item_usage
from core.services.storage_resources import revoke_incompatible_links
from core.services.storage_transfer_location import resolve_location
from core.services.storage_tree_transfer import enter_maintenance, reclassify_backend
from core.utils.share_links import compute_item_share_token, validate_item_share_token


@pytest.mark.django_db(transaction=True)
def test_my_files_retains_files_and_only_authorized_space_entrances(settings):
    """Home keeps file types, filters and pagination without exposing a shared sibling."""
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    owner, guest = factories.UserFactory.create_batch(2)
    backend = models.StorageBackend.objects.create(
        registry_id="home-s3", family="s3", legacy_s3=True, name="Home", organization="local"
    )
    file = factories.ItemFactory(
        type="file",
        parent=None,
        creator=owner,
        title="Report.pdf",
        filename="Report.pdf",
        update_upload_state="ready",
    )
    root = models.Item.objects.create(type="folder", title="Allocated", creator=owner)
    child = models.Item.objects.create_child(parent=root, type="folder", title="Shared part")
    for item in [file, root]:
        models.ItemAccess.objects.create(item=item, user=owner, role="owner")
        models.Item.objects.filter(pk=item.pk).update(storage_backend=backend)
        item.refresh_from_db()
        space = models.StorageSpace(
            backend=backend, root_item=item, name=item.title, explicit_access=True
        )
        # Reproduce legacy single-file allocations predating folder-only validation.
        models.StorageSpace.objects.bulk_create([space])
        models.Item.objects.filter(path__descendants=item.path).update(
            storage_backend=backend, storage_space=space
        )
        models.StorageGrant.objects.create(space=space, user=owner, writable=True, shareable=True)
    child.refresh_from_db()
    models.StorageGrant.objects.create(space=space, user=guest, root_item=child)
    api = APIClient()
    api.force_authenticate(owner)
    endpoint = "/api/v1.0/resources/"
    result = api.get(endpoint, {"mode": "home", "ordering": "-type,title", "limit": 1})
    assert result.status_code == 200, result.data
    assert result.data["count"] == 2
    assert result.data["results"][0]["id"] == str(root.pk)
    result = api.get(endpoint, {"mode": "home", "category": "pdf", "type": "file"})
    assert [row["id"] for row in result.data["results"]] == [str(file.pk)]
    assert result.data["results"][0]["kind"] == "file"
    assert result.data["results"][0]["adapter"]["kind"] == "item"
    assert (
        api.get(endpoint, {"mode": "home", "category": "image", "type": "file"}).data["count"] == 0
    )
    assert api.get(endpoint, {"mode": "home", "ordering": "invalid"}).status_code == 400
    assert api.get("/api/v1.0/spaces/").data["count"] == 1
    api.force_authenticate(guest)
    result = api.get(endpoint, {"mode": "home"})
    assert result.status_code == 200, result.data
    assert [row["id"] for row in result.data["results"]] == [str(child.pk)]


@pytest.mark.django_db
def test_group_grants_follow_membership_and_survive_group_rename():
    """Real local membership, discovery and revocation govern resource endpoints."""
    admin, member, stranger = factories.UserFactory.create_batch(3)
    admin.is_superuser = True
    admin.save(update_fields=["is_superuser"])
    group = Group.objects.create(name="Shared documents")
    member.groups.add(group)
    backend = models.StorageBackend.objects.create(
        registry_id="group-s3",
        family="s3",
        legacy_s3=True,
        name="Group files",
        organization="local",
    )
    root = models.Item.objects.create(type="folder", title="Group files", storage_backend=backend)
    space = models.StorageSpace.objects.create(
        backend=backend, root_item=root, name="Group files", explicit_access=True
    )
    models.Item.objects.filter(pk=root.pk).update(storage_space=space)
    api = APIClient()
    api.force_authenticate(admin)
    endpoint = f"/api/v1.0/storage-spaces-admin/{space.pk}/"
    choices = api.get(endpoint + "groups/", {"q": "Shared"})
    assert choices.data["results"] == [{"id": f"group:{group.pk}", "name": group.name}]
    granted = api.post(
        endpoint + "grants/", {"team": f"group:{group.pk}", "writable": False}, format="json"
    )
    assert granted.status_code == 201, granted.data
    assert api.get(endpoint + "grants/").data["results"][0]["beneficiary"] == group.name
    api.force_authenticate(member)
    assert api.get(f"/api/v1.0/resources/{root.pk}/").status_code == 200
    root.refresh_from_db()
    assert not root.get_abilities(member)["update"]
    group.name = "Renamed group"
    group.save(update_fields=["name"])
    assert root.get_abilities(member)["retrieve"]
    member.groups.remove(group)
    member.refresh_from_db()
    assert not root.get_abilities(member)["retrieve"]
    assert api.get(f"/api/v1.0/resources/{root.pk}/").status_code == 404
    api.force_authenticate(stranger)
    assert api.get(endpoint + "groups/").status_code == 404


@pytest.mark.django_db
def test_read_only_sharer_cannot_delegate_writes():
    """Sharing a resource never raises the grantor's space permission ceiling."""
    reader, recipient = factories.UserFactory.create_batch(2)
    backend = models.StorageBackend.objects.create(
        registry_id="sharing-s3", family="s3", legacy_s3=True, name="Storage", organization="local"
    )
    root = models.Item.objects.create(type="folder", title="Shared", storage_backend=backend)
    space = models.StorageSpace.objects.create(
        backend=backend, root_item=root, name="Shared", explicit_access=True, allow_sharing=True
    )
    models.Item.objects.filter(pk=root.pk).update(storage_space=space)
    root.refresh_from_db()
    models.StorageGrant.objects.create(space=space, user=reader, writable=False, shareable=True)
    api = APIClient()
    api.force_authenticate(reader)
    accesses = f"/api/v1.0/items/{root.pk}/accesses/"
    invitations = f"/api/v1.0/items/{root.pk}/invitations/"
    link = f"/api/v1.0/items/{root.pk}/link-configuration/"
    assert root.get_abilities(reader)["accesses_manage"]
    for role in ("editor", "administrator", "owner"):
        assert api.post(accesses, {"user_id": str(recipient.pk), "role": role}).status_code == 403
        assert (
            api.post(invitations, {"email": "guest@example.org", "role": role}).status_code == 403
        )
    assert api.put(link, {"link_reach": "public", "link_role": "editor"}).status_code == 400
    assert api.put(link, {"link_reach": "public", "link_role": "reader"}).status_code == 200
    result = api.post(accesses, {"user_id": str(recipient.pk), "role": "reader"})
    assert result.status_code == 201, result.data
    access = result.data["id"]
    assert api.patch(f"{accesses}{access}/", {"role": "editor"}).status_code == 403
    backend.enabled = False
    backend.save(update_fields=["enabled"])
    assert api.delete(f"{accesses}{access}/").status_code in {403, 404}


@pytest.mark.django_db(transaction=True)
def test_s3_space_subtree_revocation_and_independent_budgets(settings):
    """Accounting ownership grants no access; file shares cannot widen a subtree."""
    settings.STORAGE_GOVERNANCE_ENABLED = True
    admin, owner, reader = factories.UserFactory.create_batch(3)
    admin.is_superuser = True
    admin.save(update_fields=["is_superuser"])
    backend = models.StorageBackend.objects.create(
        registry_id="historical-s3",
        family="s3",
        legacy_s3=True,
        name="Storage",
        organization="local",
    )
    api = APIClient()
    api.force_authenticate(admin)
    result = api.post(
        "/api/v1.0/storage-spaces-admin/",
        {
            "name": "Shared space",
            "backend": str(backend.pk),
            "owner": str(owner.pk),
        },
        format="json",
    )
    assert result.status_code == 201, result.data
    space = models.StorageSpace.objects.get(pk=result.data["id"])
    root = space.root_item
    initialize_items()
    assert not root.get_abilities(owner)["retrieve"]
    child = models.Item.objects.create_child(parent=root, type="folder", title="Allowed")
    sibling = models.Item.objects.create_child(parent=root, type="folder", title="Private")
    file = models.Item.objects.create_child(
        parent=child,
        creator=admin,
        type="file",
        title="File",
        filename="file.txt",
        upload_state="ready",
    )
    item_usage(file, initial_size=4)
    grant = api.post(
        f"/api/v1.0/storage-spaces-admin/{space.pk}/grants/",
        {
            "user": str(reader.pk),
            "root_item": str(child.pk),
            "writable": False,
        },
        format="json",
    )
    assert grant.status_code == 201, grant.data
    models.ItemAccess.objects.create(item=root, user=reader, role="editor")
    assert file.get_abilities(reader)["retrieve"]
    assert not file.get_abilities(reader)["update"]
    assert not sibling.get_abilities(reader)["retrieve"]
    visible = bound_queryset(models.Item.objects.all(), reader, grants_only=True)
    assert set(visible.values_list("pk", flat=True)) == {child.pk, file.pk}
    api.force_authenticate(reader)
    catalogue = api.get("/api/v1.0/spaces/")
    assert catalogue.status_code == 200
    entrance = catalogue.data["results"][0]["roots"][0]
    assert not entrance["abilities"]["children_create"]
    assert [{key: value for key, value in entrance.items() if key != "abilities"}] == [
        {"id": str(child.pk), "title": "Allowed", "updated_at": child.updated_at}
    ]
    assert api.get(f"/api/v1.0/resources/{child.pk}/children/").status_code == 200
    assert api.get(f"/api/v1.0/items/{sibling.pk}/").status_code == 404
    assert api.get(f"/api/v1.0/items/{child.pk}/children/").status_code == 200
    quota.apply_policy({f"space:{space.pk}": {"limit_bytes": 4}}, revision="test")
    with pytest.raises(quota.StorageQuotaExceeded):
        quota.admit(key=file.storageusage.key, actor=reader, size=5)
    for key in ("instance:drive", f"space:{space.pk}", f"user:{owner.pk}", "backend:s3"):
        assert models.StorageQuota.objects.get(key=key).used_bytes == 4
    backend.enabled = False
    backend.save(update_fields=["enabled"])
    file.refresh_from_db()
    assert not file.get_abilities(reader)["retrieve"]


@pytest.mark.django_db
# One scenario checks the identity, visibility and quota boundaries together.
# pylint: disable-next=too-many-statements
def test_mounted_catalogue_keeps_identity_and_hides_siblings(tmp_path, settings):  # noqa: PLR0915
    """Inventory, favorites and the catalogue agree after a direct external rename."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_inventory import scan_backend  # noqa: PLC0415

    settings.STORAGE_UNIFIED_ENABLED = True
    settings.STORAGE_GOVERNANCE_ENABLED = True
    settings.MOUNTS_REGISTRY = [
        {
            "mount_id": "nas",
            "display_name": "NAS",
            "provider": "localfs",
            "params": {"root_dir": str(tmp_path)},
        }
    ]
    (tmp_path / "alice").mkdir()
    (tmp_path / "alice" / "file.txt").write_text("hello")
    (tmp_path / "private.txt").write_text("private")
    user = factories.UserFactory()
    backend = models.StorageBackend.objects.create(
        registry_id="nas", name="NAS", organization="local"
    )
    space = models.StorageSpace.objects.create(
        backend=backend, name="Files", root_path="/alice", explicit_access=True
    )
    group = Group.objects.create(name="NAS readers")
    user.groups.add(group)
    models.StorageGrant.objects.create(space=space, team=f"group:{group.pk}")
    scan_backend(backend.pk)
    api = APIClient()
    api.force_authenticate(user)

    with (
        patch(
            "core.api.viewsets.resolve_mount_provider_io_capabilities",
            wraps=viewsets.resolve_mount_provider_io_capabilities,
        ) as capabilities,
        patch(
            "core.mounts.providers.localfs.list_children",
            side_effect=AssertionError("must page index"),
        ),
    ):
        page = api.get(f"/api/v1.0/mounts/{space.pk}/browse/", {"path": "/", "limit": 1})
    assert page.status_code == 200, page.data
    assert page.data["children"]["count"] == 1
    assert page.data["children"]["results"][0]["name"] == "file.txt"
    assert capabilities.call_count == 1
    catalogue = api.get("/api/v1.0/spaces/")
    assert catalogue.status_code == 200
    root = catalogue.data["results"][0]["roots"][0]["id"]
    with pytest.raises(NotFound):
        resolve_location(root, user, space_id=space.pk, destination=True)
    models.StorageGrant.objects.filter(space=space).update(writable=True)
    assert resolve_location(root, user, space_id=space.pk, destination=True).path == "/"
    models.StorageGrant.objects.filter(space=space).update(writable=False)
    listing = api.get(f"/api/v1.0/resources/{root}/children/", {"space": str(space.pk)})
    assert listing.status_code == 200, listing.data
    assert listing.data["count"] == 1
    reference = listing.data["results"][0]["id"]
    bare_reference = api.get(f"/api/v1.0/resources/{reference}/")
    assert bare_reference.status_code == 200
    assert bare_reference.data["space"] == str(space.pk)
    assert api.get("/api/v1.0/resources/not-a-uuid/").status_code == 404
    old_link = api.get(
        "/api/v1.0/resources/resolve-legacy/", {"mount_id": "nas", "path": "/alice/file.txt"}
    )
    assert old_link.status_code == 200, old_link.data
    assert old_link.data["id"] == reference
    assert (
        api.get(
            "/api/v1.0/resources/resolve-legacy/", {"mount_id": "nas", "path": "/private.txt"}
        ).status_code
        == 404
    )
    assert (
        api.post(f"/api/v1.0/resources/{reference}/favorite/?space={space.pk}").status_code == 204
    )
    (tmp_path / "alice" / "file.txt").rename(tmp_path / "alice" / "renamed.txt")
    scan_backend(backend.pk)
    resolved = api.get(f"/api/v1.0/resources/{reference}/", {"space": str(space.pk)})
    assert resolved.status_code == 200, resolved.data
    assert resolved.data["title"] == "renamed.txt"
    assert models.StorageResourceFavorite.objects.get(resource_id=reference).favorite
    searched = api.get("/api/v1.0/resources/", {"q": "renamed"})
    assert searched.status_code == 200, searched.data
    assert searched.data["count"] == 1
    favorites = api.get("/api/v1.0/resources/", {"mode": "favorites"})
    assert favorites.status_code == 200, favorites.data
    assert favorites.data["results"][0]["id"] == reference
    user.groups.remove(group)
    user.refresh_from_db()
    assert api.get(f"/api/v1.0/resources/{reference}/", {"space": str(space.pk)}).status_code == 404


@pytest.mark.django_db
def test_space_administration_is_bounded_and_readable():
    """Delegates cannot acquire instance control or delegate a restricted subtree."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_inventory import organization_for  # noqa: PLC0415

    admin, delegate, outsider = factories.UserFactory.create_batch(3, claims={})
    admin.is_superuser = admin.is_staff = True
    admin.save(update_fields=["is_superuser", "is_staff"])
    backend = models.StorageBackend.objects.create(
        registry_id="s3-admin",
        family="s3",
        legacy_s3=True,
        name="Files",
        organization=organization_for(admin),
    )
    api = APIClient()
    api.force_authenticate(admin)
    result = api.post(
        "/api/v1.0/storage-spaces-admin/",
        {"name": "Team", "backend": str(backend.pk)},
        format="json",
    )
    assert result.status_code == 201, result.data
    space = models.StorageSpace.objects.get(pk=result.data["id"])
    folder = models.Item.objects.create_child(parent=space.root_item, title="Folder", type="folder")
    url = f"/api/v1.0/storage-spaces-admin/{space.pk}/"
    assert api.get(url + "folders/").data["results"][0]["title"] == "Folder"
    assert api.get(url + "impact/").data["active_operations"] == 0
    assert (
        api.post(
            url + "grants/",
            {"user": str(delegate.pk), "root_item": str(folder.pk), "manageable": True},
            format="json",
        ).status_code
        == 400
    )
    assert (
        api.post(
            url + "grants/", {"user": str(delegate.pk), "manageable": True}, format="json"
        ).status_code
        == 201
    )
    api.force_authenticate(delegate)
    config = api.get("/api/v1.0/storage-spaces-admin/configuration/")
    assert config.data["spaces_manage"] and not config.data["connections_manage"]
    assert config.data["connections"] == []
    assert api.get("/api/v1.0/storage-connections/").status_code == 403
    assert api.patch(url, {"enabled": False}, format="json").status_code == 403
    assert api.get(url + "grants/").data["results"][0]["beneficiary"] == (
        delegate.full_name or delegate.email
    )
    api.force_authenticate(outsider)
    assert api.get(url).status_code == 404


@pytest.mark.django_db(transaction=True)
# Nested allocations share one accounting setup and its final audit.
# pylint: disable-next=too-many-statements
def test_nested_s3_allocation_preserves_views_and_counts_bytes_once(settings):  # noqa: PLR0915
    """Existing subtrees get independent budgets without hiding their parent view."""
    settings.STORAGE_GOVERNANCE_ENABLED = True
    admin, owner, reader, writer = factories.UserFactory.create_batch(4)
    admin.is_superuser = True
    admin.save(update_fields=["is_superuser"])
    backend = models.StorageBackend.objects.create(
        registry_id="nested-s3", family="s3", legacy_s3=True, name="S3", organization="local"
    )
    api = APIClient()
    api.force_authenticate(admin)
    endpoint = "/api/v1.0/storage-spaces-admin/"
    result = api.post(endpoint, {"name": "Outer", "backend": str(backend.pk)}, format="json")
    assert result.status_code == 201, result.data
    outer = models.StorageSpace.objects.get(pk=result.data["id"])
    child = models.Item.objects.create_child(parent=outer.root_item, type="folder", title="Inner")
    sibling = models.Item.objects.create_child(parent=outer.root_item, type="folder", title="Other")
    file = models.Item.objects.create_child(
        parent=child,
        creator=admin,
        type="file",
        title="File",
        filename="file.txt",
        upload_state="ready",
    )
    models.Item.objects.filter(pk=file.pk).update(upload_state="ready")
    initialize_items()
    item_usage(file, initial_size=4)
    models.StorageGrant.objects.create(space=outer, user=reader)
    data = {
        "name": "Inner",
        "backend": str(backend.pk),
        "root_item": str(child.pk),
        "owner": str(owner.pk),
    }
    assert api.post(endpoint, data, format="json").status_code == 400
    enter_maintenance(backend)
    result = api.get(
        f"{endpoint}root-folders/", {"backend": str(backend.pk), "parent": str(child.pk)}
    )
    assert result.status_code == 200, result.data
    assert result.data["overlaps"] == [{"id": str(outer.pk), "name": "Outer"}]
    assert not result.data["allocated"]
    result = api.post(endpoint, data, format="json")
    assert result.status_code == 201, result.data
    inner = models.StorageSpace.objects.get(pk=result.data["id"])
    backend.refresh_from_db()
    assert backend.attribution_pending
    models.StorageGrant.objects.create(space=inner, user=writer, writable=True)
    reclassify_backend(backend.pk, admin.pk)
    file.refresh_from_db()
    assert file.storage_space_id == inner.pk
    assert file.storageusage.owner_id == owner.pk
    assert file.get_abilities(reader)["retrieve"]
    assert not file.get_abilities(reader)["update"]
    assert file.get_abilities(writer)["update"]
    assert not sibling.get_abilities(writer)["retrieve"]
    assert not file.get_abilities(owner)["retrieve"]
    cache_item_grants([file, sibling], writer)
    assert file.get_abilities(writer)["update"]
    assert not sibling.get_abilities(writer)["retrieve"]
    cache_item_grants([file, sibling], reader)
    assert file.get_abilities(reader)["retrieve"]
    assert not file.get_abilities(reader)["update"]
    assert file.pk in bound_queryset(
        models.Item.objects.all(), reader, grants_only=True
    ).values_list("pk", flat=True)
    assert sibling.pk not in bound_queryset(
        models.Item.objects.all(), writer, grants_only=True
    ).values_list("pk", flat=True)
    grant = models.StorageGrant(space=outer, user=writer, root_item=child)
    grant.full_clean()
    api.force_authenticate(reader)
    result = api.get("/api/v1.0/resources/", {"space": str(outer.pk), "q": "File"})
    assert result.status_code == 200, result.data
    assert str(file.pk) in {row["id"] for row in result.data["results"]}
    assert api.get(f"{endpoint}root-folders/", {"backend": str(backend.pk)}).status_code == 403
    for key in (
        "instance:drive",
        "backend:s3",
        f"space:{outer.pk}",
        f"space:{inner.pk}",
        f"user:{owner.pk}",
    ):
        assert models.StorageQuota.objects.get(key=key).used_bytes == 4
    for space in (outer, inner):
        quota.apply_policy({f"space:{space.pk}": {"limit_bytes": 4}}, revision=f"limit-{space.pk}")
        with pytest.raises(quota.StorageQuotaExceeded):
            quota.admit(key=file.storageusage.key, actor=writer, size=5)
        quota.apply_policy(
            {f"space:{space.pk}": {"limit_bytes": None}}, revision=f"unlimited-{space.pk}"
        )
    inner.enabled = False
    inner.save(update_fields=["enabled"])
    file.refresh_from_db()
    file.__dict__.pop("_storage_grants", None)
    assert file.get_abilities(reader)["retrieve"]
    assert not file.get_abilities(writer)["retrieve"]
    assert models.StorageQuota.objects.get(key="instance:drive").used_bytes == 4


@pytest.mark.django_db
def test_transfer_revocation_cannot_revive_old_public_token():
    """Re-enabling sharing issues a new token; old browse and media URLs remain denied."""

    owner = factories.UserFactory()
    backend = models.StorageBackend.objects.create(
        registry_id="revocation-s3",
        name="Revocation",
        family="s3",
        legacy_s3=True,
        organization="local",
    )
    root = models.Item.objects.create(
        type="folder", title="Shared", creator=owner, storage_backend=backend, link_reach="public"
    )
    space = models.StorageSpace.objects.create(
        backend=backend, root_item=root, name="Shared", explicit_access=True
    )
    models.Item.objects.filter(pk=root.pk).update(storage_space=space)
    models.StorageGrant.objects.create(space=space, user=owner, shareable=True, writable=True)
    root.refresh_from_db()
    old_token = compute_item_share_token(root.pk)
    api = APIClient()
    assert api.get(f"/api/v1.0/share-links/{old_token}/browse/").status_code == 200
    space.allow_sharing = False
    space.save(update_fields=["allow_sharing"])
    revoke_incompatible_links(root.pk)
    root.refresh_from_db()
    assert root.link_reach == "restricted"
    assert root.share_link_nonce
    space.allow_sharing = True
    space.save(update_fields=["allow_sharing"])
    root.link_reach = "public"
    root.save(update_fields=["link_reach"])
    new_token = compute_item_share_token(root.pk, root.share_link_nonce)
    assert validate_item_share_token(new_token) == root.pk
    assert api.get(f"/api/v1.0/share-links/{old_token}/browse/").status_code == 404
    assert api.get(f"/api/v1.0/share-links/{new_token}/browse/").status_code == 200
    with pytest.raises(PermissionDenied):
        check_share_access(root, AnonymousUser(), old_token)
    check_share_access(root, AnonymousUser(), new_token)
