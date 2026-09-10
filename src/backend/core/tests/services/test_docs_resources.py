"""Document identities and native file boundaries on real PostgreSQL."""

import json
import time
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

import pytest
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.test import APIRequestFactory
from suite_identity.models import Account, GroupMapping

from core import factories, models
from core.api.docs_documents import DocumentAuthorizationView, DocumentListView, DocumentVisitView
from core.services.docs_lifecycle import (
    change_document,
    command_status,
    create_document,
    synchronize,
)
from core.services.docs_resources import visible_documents
from core.services.docs_sharing import access_page, change_access
from core.services.storage_access import bound_queryset


@pytest.mark.django_db
def test_document_tree_identity_access_and_file_boundary(settings):  # noqa: PLR0915
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    owner, reader = factories.UserFactory.create_batch(2)
    root = models.Item.objects.create(type="docs", title="Document", creator=owner)
    models.DocsBinding.objects.create(item=root, state="active", applied_revision=1)
    models.ItemAccess.objects.create(item=root, user=owner, role="owner")
    group = Group.objects.create(name="Document readers")
    reader.groups.add(group)
    models.ItemAccess.objects.create(item=root, team=f"group:{group.pk}", role="reader")
    child = models.Item.objects.create_child(parent=root, type="docs", title="Child")
    models.DocsBinding.objects.create(item=child, state="active", applied_revision=1)
    assert child.get_abilities(reader)["retrieve"]
    assert not child.get_abilities(reader)["update"]
    access = models.ItemAccess.objects.get(item=root, team=f"group:{group.pk}")
    access.role = "commenter"
    access.save()
    assert child.get_role(reader) == "commenter"
    assert child.get_abilities(reader)["comment"]
    assert not child.get_abilities(reader)["update"]
    assert "commenter" in access.get_abilities(owner)["set_role_to"]
    assert child.get_abilities(owner)["update"]
    assert all(
        not child.get_abilities(owner)[action]
        for action in (
            "download",
            "upload_policy",
            "upload_ended",
            "wopi",
            "convert",
            "text",
        )
    )
    with pytest.raises(ValidationError):
        _ = child.file_key
    with pytest.raises(ValidationError):
        models.Item.objects.create_child(parent=root, type="file", filename="not-a-document.txt")
    reader.groups.remove(group)
    reader.refresh_from_db()
    assert not child.get_abilities(reader)["retrieve"]
    root.link_reach = "authenticated"
    root.save(update_fields=["link_reach"])
    reader.is_active = False
    assert not child.get_abilities(reader).get("retrieve")
    identities = (root.pk, child.pk, child.docs_binding.document_id)
    root.soft_delete()
    child.refresh_from_db()
    assert not child.get_abilities(owner)["update"]
    assert child.get_abilities(owner)["retrieve"]
    assert not child.get_abilities(owner)["restore"]
    root.restore()
    child.refresh_from_db()
    assert child.get_abilities(owner)["update"]
    assert identities == (root.pk, child.pk, child.docs_binding.document_id)
    with pytest.raises(ValidationError):
        root.accesses.get(role="owner").delete()
    models.ItemAccess.objects.create(item=root, user=reader, role="owner")
    with pytest.raises(ValidationError), transaction.atomic():
        root.accesses.filter(role="owner").delete()
    assert root.accesses.filter(role="owner").count() == 2
    root.accesses.filter(user=reader).delete()
    models.Item.objects.filter(pk=root.pk).update(creator=None)
    with pytest.raises(ValidationError), transaction.atomic():
        owner.delete()
    assert models.User.objects.filter(pk=owner.pk).exists()
    models.Item.objects.filter(pk=root.pk).update(creator=owner)
    with pytest.raises(ValidationError):
        root.move(child)
    with pytest.raises(ValidationError), transaction.atomic():
        models.Item.objects.filter(pk=child.pk).delete()
    destination = models.Item.objects.create(type="folder", title="Another folder")
    child.refresh_from_db()
    before_revision = child.docs_binding.revision
    root.move(destination)
    child.refresh_from_db()
    assert child.docs_binding.revision == before_revision + 1
    assert child.docs_binding.document_id == identities[2]
    assert child.parent().pk == root.pk


@pytest.mark.django_db
def test_document_quota_is_logical_stable_and_blocks_growth(settings, monkeypatch):  # noqa: PLR0915
    """NAS capacity is separate; a second editor consumes the original owner's budget."""
    from core.services import storage_quota as quota  # noqa: PLC0415
    from core.services.docs_quota import initialize_usage, reserve, transition  # noqa: PLC0415

    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    # This scenario isolates accounting; anchor IO has its own real-provider check.
    monkeypatch.setattr("core.services.docs_resources.current_anchor", lambda *_: True)
    owner, editor = factories.UserFactory.create_batch(2)
    backend = models.StorageBackend.objects.create(
        registry_id="docs-quota", family="mount", name="NAS", organization="local"
    )
    space = models.StorageSpace.objects.create(backend=backend, name="Documents", owner=owner)
    anchor = models.StorageResource.objects.create(
        namespace=backend.namespace,
        identity_key="quota-anchor",
        path="/",
        parent_path="/",
        name="Root",
        kind="folder",
    )
    item = models.Item.objects.create(type="docs", title="Budget", creator=owner)
    binding = models.DocsBinding.objects.create(
        item=item, state="active", applied_revision=1, mounted_parent=anchor, anchor_space=space
    )
    models.ItemAccess.objects.create(item=item, user=owner, role="owner")
    models.ItemAccess.objects.create(item=item, user=editor, role="editor")
    usage = initialize_usage(item, size=3, version="initial")
    assert usage.backend_id is None
    assert set(usage.scope_keys) == {
        "instance:drive",
        "organization:local",
        f"space:{space.pk}",
        f"user:{owner.pk}",
    }
    models.StorageQuota.objects.filter(key=f"user:{owner.pk}").update(limit_bytes=10)
    key = uuid4()
    with patch("core.services.docs_quota.refresh_policy"):
        operation = reserve(editor, document_id=binding.document_id, operation_id=key, size=8)
        assert reserve(editor, document_id=binding.document_id, operation_id=key, size=8).pk == key
    assert operation.reserved_bytes == 5
    publication = {
        "action": "begin",
        "operation_id": key,
        "document_id": binding.document_id,
        "size": 8,
        "version": "initial",
        "digest": "a" * 64,
    }
    assert transition(editor, publication)["state"] == "publishing"
    assert transition(editor, publication)["state"] == "publishing"
    with pytest.raises(quota.StorageWriteConflict):
        transition(editor, {**publication, "digest": "b" * 64})
    with pytest.raises(quota.StorageWriteConflict):
        transition(editor, {**publication, "action": "cancel"})
    publication.update(action="commit", version="saved")
    assert transition(editor, publication)["state"] == "committed"
    item.refresh_from_db()
    saved_at = item.updated_at
    assert item.size == 8
    assert transition(editor, publication)["state"] == "committed"
    item.refresh_from_db()
    assert item.updated_at == saved_at
    assert initialize_usage(item).size == 8
    with (
        patch("core.services.docs_quota.refresh_policy"),
        pytest.raises(quota.StorageQuotaExceeded),
    ):
        reserve(editor, document_id=binding.document_id, operation_id=uuid4(), size=11)
    with patch("core.services.docs_quota.refresh_policy"):
        pending = reserve(editor, document_id=binding.document_id, operation_id=uuid4(), size=9)
    publication.update(action="begin", operation_id=pending.pk, size=9)
    transition(editor, publication)
    publication.update(action="cancel", unpublished=True)
    with pytest.raises(PermissionDenied):
        transition(editor, publication)
    assert transition(AnonymousUser(), publication)["state"] == "cancelled"
    reduction = {
        "action": "reduce",
        "document_id": binding.document_id,
        "version": "saved",
        "size": 5,
    }
    with pytest.raises(PermissionDenied):
        transition(editor, reduction)
    with pytest.raises(quota.StorageWriteConflict):
        transition(AnonymousUser(), {**reduction, "size": 9})
    assert transition(AnonymousUser(), reduction)["size"] == 5
    item.link_reach, item.link_role = "public", "editor"
    item.save(update_fields=["link_reach", "link_role"])
    with patch("core.services.docs_quota.refresh_policy"):
        public_write = reserve(
            AnonymousUser(), document_id=binding.document_id, operation_id=uuid4(), size=6
        )
    assert public_write.actor_id is None
    item.link_reach = "restricted"
    item.save(update_fields=["link_reach"])
    public_intent = {
        "action": "begin",
        "document_id": binding.document_id,
        "operation_id": public_write.pk,
        "size": 6,
        "version": "saved",
        "digest": "c" * 64,
    }
    with pytest.raises(PermissionDenied):
        transition(AnonymousUser(), public_intent)
    transition(AnonymousUser(), {**public_intent, "action": "cancel"})
    item.soft_delete()
    assert models.StorageQuota.objects.get(key=f"user:{owner.pk}").used_bytes == 5
    item.hard_delete()
    with patch("suite_identity.document_transport.send", side_effect=APIException()):
        assert not synchronize(binding.pk)
    assert models.StorageQuota.objects.get(key=f"user:{owner.pk}").used_bytes == 5
    binding.refresh_from_db()
    with patch(
        "suite_identity.document_transport.send",
        return_value={"item_id": str(item.pk), "revision": binding.revision, "state": "purged"},
    ):
        assert synchronize(binding.pk)
        binding.refresh_from_db()
        assert binding.mounted_parent_id is None and binding.anchor_space_id is None
    assert models.StorageQuota.objects.get(key=f"user:{owner.pk}").used_bytes == 0
    from core.tasks.item import process_item_purge  # noqa: PLC0415

    process_item_purge(str(item.pk))
    binding.refresh_from_db()
    assert binding.item_id is None
    regular = models.Item.objects.create(
        type="file", title="Regular", filename="regular.txt", creator=owner
    )
    regular_usage = quota.observe_usage(
        key=quota.resource_key(str(regular.pk)),
        item=regular,
        size=0,
        scope_keys=["instance:drive"],
        organization="local",
    )
    with pytest.raises(quota.StorageWriteConflict):
        quota.admit(key=regular_usage.key, actor=None, size=0)


@pytest.mark.django_db
def test_document_activation_and_native_placement_constraints(settings):
    settings.DOCS_DRIVE_ENABLED = False
    with pytest.raises(ValidationError):
        models.Item.objects.create(type="docs", title="Disabled")
    settings.DOCS_DRIVE_ENABLED = True
    backend = models.StorageBackend.objects.create(
        registry_id="document-test", family="s3", name="Files", organization="local"
    )
    with pytest.raises(ValidationError):
        models.Item.objects.create(type="docs", title="Wrong storage", storage_backend=backend)
    with pytest.raises(ValidationError):
        models.Item.objects.create(type="docs", title="Wrong bytes", filename="fake.docs")
    folder = models.Item.objects.create(type="folder", title="Folder")
    with pytest.raises(ValidationError):
        models.ItemAccess.objects.create(
            item=folder, user=factories.UserFactory(), role="commenter"
        )
    with pytest.raises(ValidationError):
        models.Invitation.objects.create(
            item=folder, email="reader@example.invalid", role="commenter"
        )
    wrong_binding = models.DocsBinding(item=folder)
    with pytest.raises(ValidationError):
        wrong_binding.clean()


@pytest.mark.django_db
def test_document_sharing_uses_stable_people_group_and_keeps_inherited_grants(settings):
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.SUITE_ORGANIZATION_ID = str(uuid4())
    owner, member = factories.UserFactory.create_batch(2)
    item = models.Item.objects.create(type="docs", title="Shared", creator=owner)
    models.DocsBinding.objects.create(item=item, state="active", applied_revision=1)
    models.ItemAccess.objects.create(item=item, user=owner, role="owner")
    group = Group.objects.create(name="Local group")
    member.groups.add(group)
    mapping = GroupMapping.objects.create(
        group_id=uuid4(),
        organization_id=settings.SUITE_ORGANIZATION_ID,
        local_group=group,
        display_name="People group",
    )
    with transaction.atomic():
        access = change_access(
            item,
            owner,
            {
                "action": "grant_access",
                "group_id": mapping.pk,
                "role": "commenter",
            },
        )
    assert access.team == f"group:{group.pk}"
    assert item.get_abilities(member)["comment"]
    page = access_page(item, owner, offset=0, limit=100)
    row = next(row for row in page["results"] if row["group_id"])
    assert row["group_id"] == str(mapping.pk)
    mapping.display_name = "Renamed group"
    mapping.save()
    assert item.get_abilities(member)["comment"]
    child = models.Item.objects.create_child(parent=item, type="docs", title="Child")
    models.DocsBinding.objects.create(item=child, state="active", applied_revision=1)
    inherited = access_page(child, owner, offset=0, limit=100)["results"]
    assert all(row["inherited"] and not row["abilities"]["destroy"] for row in inherited)
    with transaction.atomic():
        assert (
            change_access(
                child, owner, {"action": "grant_access", "group_id": mapping.pk, "role": "reader"}
            )
            is None
        )
    assert not child.accesses.exists()
    assert child.get_role(member) == "commenter"
    with pytest.raises(NotFound), transaction.atomic():
        change_access(child, owner, {"action": "revoke_access", "access_id": access.pk})
    with transaction.atomic():
        change_access(item, owner, {"action": "revoke_access", "access_id": access.pk})
    assert not item.get_abilities(member)["retrieve"]


@pytest.mark.django_db
def test_private_document_authority_revokes_access(settings, tmp_path):
    """Exercise the actual API boundary, not a mocked permission calculation."""
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = True
    settings.SUITE_ORGANIZATION_ID = str(uuid4())
    settings.SUITE_OIDC_ISSUER = "https://id.example.invalid"
    key = tmp_path / "docs-read-key"
    key.write_text("isolated-document-read-key".ljust(48, "-"))
    key.chmod(0o600)
    settings.DOCUMENT_INBOUND_READ_KEY_FILE = str(key)
    user = factories.UserFactory()
    account = Account.objects.create(
        user=user,
        principal_id=uuid4(),
        organization_id=settings.SUITE_ORGANIZATION_ID,
        active=True,
        policy_allowed=True,
        checked_at=timezone.now(),
        policy_checked_at=timezone.now(),
    )
    item = models.Item.objects.create(type="docs", title="Private")
    binding = models.DocsBinding.objects.create(item=item, state="active", applied_revision=1)
    access = models.ItemAccess.objects.create(item=item, user=user, role="commenter")
    missing = str(uuid4())
    body = {
        "actor": {
            "principal": str(account.principal_id),
            "organization": settings.SUITE_ORGANIZATION_ID,
            "proof": {
                "principal_id": str(account.principal_id),
                "session_version": 0,
                "issuer": settings.SUITE_OIDC_ISSUER,
                "auth_until": time.time() + 60,
            },
        },
        "payload": {"document_ids": [str(binding.document_id), missing]},
    }
    factory = APIRequestFactory()

    def call(credential):
        return DocumentAuthorizationView.as_view()(
            factory.post(
                "/internal/docs/authorize/",
                json.dumps(body),
                content_type="application/json",
                HTTP_X_DOCUMENT_KEY=credential,
            )
        )

    assert call("wrong").status_code in {401, 403}
    result = call(key.read_text())
    assert result.status_code == 200
    assert result.data[missing] == {"abilities": {}, "role": None}
    allowed = result.data[str(binding.document_id)]
    assert 0 < allowed["access_ttl"] <= 15
    assert allowed["abilities"]["comment"]
    assert not allowed["abilities"]["update"]
    body["payload"] = {"limit": 1}
    page_request = factory.post(
        "/internal/docs/list/",
        json.dumps(body),
        content_type="application/json",
        HTTP_X_DOCUMENT_KEY=key.read_text(),
    )
    page = DocumentListView.as_view()(page_request)
    assert page.status_code == 200
    assert page.data["count"] == 1
    assert page.data["results"][0]["document_id"] == str(binding.document_id)
    mutation_key = tmp_path / "docs-mutation-key"
    mutation_key.write_text("isolated-visit-mutation-key".ljust(48, "-"))
    mutation_key.chmod(0o600)
    settings.DOCUMENT_INBOUND_MUTATION_KEY_FILE = str(mutation_key)

    def visit(credential):
        return DocumentVisitView.as_view()(
            factory.post(
                "/internal/docs/visit/",
                {**body, "payload": {"document_id": str(binding.document_id)}},
                format="json",
                HTTP_X_DOCUMENT_KEY=credential,
            )
        )

    assert visit(key.read_text()).status_code in {401, 403}
    assert visit(mutation_key.read_text()).status_code == 200
    assert visit(mutation_key.read_text()).status_code == 200
    assert models.LinkTrace.objects.filter(item=item, user=user).count() == 1
    body["payload"] = {"document_ids": [str(binding.document_id), missing]}
    access.delete()
    result = call(key.read_text())
    assert result.data[str(binding.document_id)] == {"abilities": {}, "role": None}
    assert visit(mutation_key.read_text()).status_code == 404


@pytest.mark.django_db
def test_document_space_filter_precedes_count_and_hides_missing_anchor(settings):
    """Both placement families constrain results in SQL, before pagination."""
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    user = factories.UserFactory()
    backend = models.StorageBackend.objects.create(
        registry_id="docs-s3",
        family="s3",
        name="S3",
        organization="local",
    )
    folder = models.Item.objects.create(type="folder", title="Root", storage_backend=backend)
    space = models.StorageSpace.objects.create(
        backend=backend,
        name="S3 space",
        root_item=folder,
        explicit_access=True,
        allow_sharing=False,
    )
    models.Item.objects.filter(pk=folder.pk).update(storage_space=space)
    folder.refresh_from_db()
    doc = models.Item.objects.create_child(parent=folder, type="docs", title="Hidden")
    models.DocsBinding.objects.create(item=doc, state="active", applied_revision=1)
    models.ItemAccess.objects.create(item=doc, user=user, role="owner")

    def visible():
        return bound_queryset(models.Item.objects.filter(type="docs"), user)

    assert visible().count() == 0
    grant = models.StorageGrant.objects.create(space=space, user=user)
    assert list(visible().values_list("pk", flat=True)) == [doc.pk]
    from core.services.storage_access import cache_item_grants  # noqa: PLC0415

    other = models.Item.objects.create_child(
        parent=folder, type="folder", title="Allowed only here"
    )
    grant.root_item = other
    grant.save(update_fields=["root_item"])
    space.allow_sharing = True
    space.save(update_fields=["allow_sharing"])
    cache_item_grants([doc], user)
    assert not doc.get_abilities(user)["retrieve"]
    grant.root_item = None
    grant.save(update_fields=["root_item"])
    space.allow_sharing = False
    space.save(update_fields=["allow_sharing"])

    backend.enabled = False
    backend.save()
    assert visible().count() == 0
    mount = models.StorageBackend.objects.create(
        registry_id="docs-mount",
        family="mount",
        name="Mount",
        organization="local",
    )
    mounted_space = models.StorageSpace.objects.create(backend=mount, name="NAS", owner=user)
    anchor = models.StorageResource.objects.create(
        namespace=mount.namespace,
        identity_key="docs-anchor",
        path="/folder",
        parent_path="/",
        name="folder",
        kind="folder",
    )
    mounted_doc = models.Item.objects.create(type="docs", title="Mounted")
    models.DocsBinding.objects.create(
        item=mounted_doc,
        state="active",
        applied_revision=1,
        mounted_parent=anchor,
        anchor_space=mounted_space,
    )
    assert list(visible().values_list("pk", flat=True)) == [mounted_doc.pk]
    anchor.missing = True
    anchor.save()
    assert visible().count() == 0


@pytest.mark.django_db(transaction=True)
def test_document_creation_and_revision_retry_are_idempotent(settings):  # noqa: PLR0915
    """A lost peer response or stale acknowledgement never creates another identity."""
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    user = factories.UserFactory()
    parent = models.Item.objects.create(type="docs", title="Parent", creator=user)
    models.DocsBinding.objects.create(item=parent, state="active", applied_revision=1)
    models.ItemAccess.objects.create(item=parent, user=user, role="owner")
    key = uuid4()
    actor = {"principal": str(uuid4()), "organization": str(uuid4())}
    with patch("suite_identity.document_transport.actor_context", return_value=actor):
        binding = create_document(user, title="Child", request_key=key, destination=parent.pk)
        repeated = create_document(user, title="Child", request_key=key, destination=parent.pk)
        assert binding.pk == repeated.pk
    with patch("suite_identity.document_transport.send", side_effect=APIException()):
        assert not synchronize(binding.pk)
    binding.refresh_from_db()
    assert binding.state == "pending"
    assert binding.applied_revision == 0

    def acknowledge(_path, payload, **_kwargs):
        assert not connection.in_atomic_block
        return {"item_id": payload["item_id"], "revision": payload["revision"]}

    with patch("suite_identity.document_transport.send", side_effect=acknowledge):
        assert synchronize(binding.pk)
        for favorite in (True, True, False):
            change_document(
                user,
                {"action": "favorite", "document_id": binding.document_id, "favorite": favorite},
            )
            assert models.ItemFavorite.objects.filter(item=binding.item, user=user).count() == int(
                favorite
            )
        result = change_document(
            user,
            {
                "action": "link_configuration",
                "document_id": binding.document_id,
                "link_reach": "public",
                "link_role": "commenter",
            },
        )
        assert result["revision"] == result["applied_revision"]
    children = visible_documents(user, {"parent_document_id": parent.docs_binding.document_id})
    assert list(children.values_list("pk", flat=True)) == [binding.item_id]
    binding.refresh_from_db()
    assert binding.state == "active"
    item = binding.item
    item.title = "Renamed"
    item.save(update_fields=["title"])
    binding.refresh_from_db()
    assert binding.revision == 3 and binding.applied_revision == 2

    def concurrent_change(path, payload, **kwargs):
        item.title = "Newer title"
        item.save(update_fields=["title"])
        return acknowledge(path, payload, **kwargs)

    with patch("suite_identity.document_transport.send", side_effect=concurrent_change):
        assert not synchronize(binding.pk)
    binding.refresh_from_db()
    assert binding.revision == 4 and binding.applied_revision == 2
    with patch("suite_identity.document_transport.send", side_effect=acknowledge):
        assert synchronize(binding.pk)
    operation = {"action": "trash", "document_id": binding.document_id, "request_key": uuid4()}
    with patch("suite_identity.document_transport.send", side_effect=acknowledge):
        first = change_document(user, operation)
        repeated = change_document(user, operation)
    assert first == repeated
    assert models.DocsCommand.objects.filter(pk=operation["request_key"]).count() == 1
    assert command_status(user, operation["request_key"]) == first
    other_user = factories.UserFactory()
    with pytest.raises(NotFound):
        command_status(other_user, operation["request_key"])
    with pytest.raises(PermissionDenied):
        change_document(other_user, operation)
