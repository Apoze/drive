"""Migration planning preserves existing users and makes ambiguous destinations explicit."""

from uuid import uuid4

from django.contrib.auth.models import Group
from django.core.management.base import CommandError
from django.test.utils import override_settings
from django.utils import timezone

import pytest
from suite_identity.document_inventory import indexed_inventory, records
from suite_identity.models import Account, GroupMapping

from core import factories, models
from core.services.docs_lifecycle import synchronize
from core.services.docs_migration import _write_plan, compare, discard, finalize, plan, stage


@pytest.mark.django_db
def test_plan_resolves_principals_without_mutating_storage(tmp_path, settings):  # noqa: PLR0915
    settings.DOCS_DRIVE_ENABLED = False
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    organization, principal, native_user, document_id = [uuid4() for _ in range(4)]
    settings.SUITE_ORGANIZATION_ID = str(organization)
    owner, member = factories.UserFactory.create_batch(2)
    child_id, native_member, member_principal, group_id = [uuid4() for _ in range(4)]
    group = Group.objects.create(name="Commenters")
    member.groups.add(group)
    GroupMapping.objects.create(
        group_id=group_id,
        organization_id=organization,
        local_group=group,
        display_name="Commenters",
    )
    Account.objects.create(
        user=member,
        organization_id=organization,
        principal_id=member_principal,
        group_ids=[str(group_id)],
    )
    captured = timezone.now()
    Account.objects.create(user=owner, organization_id=organization, principal_id=principal)
    backend = models.StorageBackend.objects.create(
        registry_id="migration", family="s3", name="Storage", organization="local"
    )
    root = models.Item.objects.create(type="folder", title="Private", storage_backend=backend)
    space = models.StorageSpace.objects.create(
        backend=backend, root_item=root, owner=owner, name="Personal", explicit_access=True
    )
    models.Item.objects.filter(pk=root.pk).update(storage_space=space)
    models.StorageGrant.objects.create(space=space, user=owner, writable=True, shareable=True)
    inventory = tmp_path / "private" / "inventory.jsonl"
    _write_plan(
        inventory,
        {
            "schema": "native-docs-inventory",
            "id": str(uuid4()),
            "organization": str(organization),
            "coherent_checkpoint": True,
            "content_metadata": True,
            "tree_step": 4,
            "invitation_validity_seconds": 86400,
        },
        [
            {
                "kind": "document",
                "id": str(document_id),
                "creator_id": str(native_user),
                "depth": 1,
                "path": "0001",
                "title": "Existing document",
                "created_at": timezone.now(),
                "updated_at": timezone.now(),
                "deleted_at": None,
                "ancestors_deleted_at": None,
                "link_reach": "restricted",
                "link_role": "reader",
            },
            {
                "kind": "document",
                "id": str(child_id),
                "creator_id": str(native_user),
                "depth": 2,
                "path": "00010001",
                "title": "Trashed child",
                "created_at": captured,
                "updated_at": captured,
                "deleted_at": captured,
                "ancestors_deleted_at": captured,
                "link_reach": "restricted",
                "link_role": "reader",
            },
            {"kind": "charge", "document_id": str(child_id), "size": 7, "version": "child-version"},
            {
                "kind": "account",
                "user_id": str(native_member),
                "principal_id": str(member_principal),
                "organization_id": str(organization),
                "group_ids": [str(group_id)],
            },
            {
                "kind": "access",
                "id": str(uuid4()),
                "document_id": str(document_id),
                "user_id": None,
                "team": str(group_id),
                "role": "commenter",
            },
            {
                "kind": "favorite",
                "id": str(uuid4()),
                "document_id": str(document_id),
                "user_id": str(native_member),
                "created_at": captured,
            },
            {
                "kind": "visit",
                "id": str(uuid4()),
                "document_id": str(document_id),
                "user_id": str(native_member),
                "created_at": captured,
                "updated_at": captured,
            },
            {
                "kind": "invitation",
                "id": str(uuid4()),
                "document_id": str(document_id),
                "issuer_id": str(native_user),
                "email": member.email,
                "role": "reader",
                "created_at": captured,
            },
            {"kind": "charge", "document_id": str(document_id), "size": 4, "version": "v1"},
            {
                "kind": "account",
                "user_id": str(native_user),
                "principal_id": str(principal),
                "organization_id": str(organization),
            },
            {
                "kind": "access",
                "id": str(uuid4()),
                "document_id": str(document_id),
                "user_id": str(native_user),
                "team": "",
                "role": "owner",
            },
        ],
    )
    output = inventory.parent / "plan.jsonl"
    counts = plan(inventory, output)
    assert counts["migration_root"] == 1 and counts["issue"] == 0
    with indexed_inventory(output) as (database, checkpoint, _receipt):
        destination = next(records(database, "migration_root", document=document_id))
        assert destination["space_id"] == str(space.pk)
        assert destination["create_folder"]["owner"] == str(owner.pk)
        assert destination["create_folder"]["parent"] == str(root.pk)
        assert checkpoint["frozen_inventory"]
    assert models.Item.objects.count() == 1
    assert not models.DocsBinding.objects.exists()
    assert models.User.objects.count() == 2
    another = models.Item.objects.create(type="folder", title="Other", storage_backend=backend)
    models.StorageSpace.objects.create(
        backend=backend, owner=owner, root_item=another, name="Other"
    )
    assert plan(inventory, inventory.parent / "ambiguous.jsonl")["issue"] == 1
    assert models.Item.objects.count() == 2

    assert stage(inventory, output) == 2
    binding = models.DocsBinding.objects.get(document_id=document_id)
    assert binding.state == "pending" and binding.applied_revision == 0
    assert binding.item.title == "Existing document"
    usage = models.StorageUsage.objects.get(item=binding.item)
    assert usage.size == 4 and usage.owner == owner
    assert stage(inventory, output) == 2
    assert models.DocsBinding.objects.count() == 2
    assert models.StorageUsage.objects.get(pk=usage.pk).size == 4
    assert models.ItemAccess.objects.filter(item=binding.item).count() == 2
    assert (
        models.DocsInvitation.objects.count()
        == models.ItemFavorite.objects.count()
        == models.LinkTrace.objects.count()
        == 1
    )
    child = models.DocsBinding.objects.get(document_id=child_id)
    assert child.item.parent().pk == binding.item_id
    assert models.StorageUsage.objects.get(item=child.item).size == 7

    attachment = inventory.parent / "attachment.jsonl"
    assert compare(inventory, output, attachment)["attachment"] == 2
    assert not settings.DOCS_DRIVE_ENABLED
    assert models.DocsBinding.objects.get(pk=binding.pk).state == "pending"

    with override_settings(DOCS_DRIVE_ENABLED=True):
        assert synchronize(binding.pk) is False
    with indexed_inventory(attachment) as (manifest, header, digest):
        native_header = {
            **header,
            "schema": "native-docs-attached",
            "attachment_sha256": digest["sha256"],
        }
        native_rows = list(records(manifest, "attachment"))
    native_receipt = inventory.parent / "native.jsonl"
    _write_plan(native_receipt, native_header, native_rows)
    assert (
        finalize(inventory, output, attachment, native_receipt, inventory.parent / "active.jsonl")[
            "attachment"
        ]
        == 2
    )
    assert (
        finalize(
            inventory, output, attachment, native_receipt, inventory.parent / "active-replay.jsonl"
        )["attachment"]
        == 2
    )
    binding.refresh_from_db()
    assert binding.state == "active" and binding.applied_revision == binding.revision
    child.refresh_from_db()
    assert child.state == "trash"
    with override_settings(DOCS_DRIVE_ENABLED=True):
        assert binding.item.get_abilities(member)["comment"]
        assert not binding.item.get_abilities(member)["update"]
        assert child.item.get_abilities(owner)["restore"]
        assert not child.item.get_abilities(member)["retrieve"]
    intruder = factories.UserFactory()
    models.ItemAccess.objects.create(item=binding.item.parent(), user=intruder, role="reader")
    with pytest.raises(CommandError, match="inherited"):
        compare(inventory, output, inventory.parent / "unsafe.jsonl")

    models.ItemAccess.objects.filter(item=binding.item.parent(), user=intruder).delete()
    detached = inventory.parent / "detached.jsonl"
    _write_plan(detached, {**native_header, "schema": "native-docs-detached"}, native_rows)
    assert (
        finalize(
            inventory,
            output,
            attachment,
            detached,
            inventory.parent / "rollback.jsonl",
            rollback=True,
        )["attachment"]
        == 2
    )
    assert not models.DocsBinding.objects.exclude(state="purged").exists()
    assert (
        finalize(
            inventory,
            output,
            attachment,
            detached,
            inventory.parent / "rollback-replay.jsonl",
            rollback=True,
        )["attachment"]
        == 2
    )
    assert not models.StorageUsage.objects.filter(pk=usage.pk).exists()
    assert models.Item.objects.count() == 2

    # A failed preparation can be discarded without requiring a successful comparison.
    assert stage(inventory, output) == 2
    unbound = inventory.parent / "unbound.jsonl"
    _write_plan(unbound, {**native_header, "schema": "native-docs-unbound"}, [])
    assert discard(inventory, output, unbound, inventory.parent / "discard.jsonl")["discarded"] == 2
    assert (
        discard(inventory, output, unbound, inventory.parent / "discard-replay.jsonl")["discarded"]
        == 2
    )
    assert models.Item.objects.count() == 2
    assert not models.StorageUsage.objects.filter(item__type="docs").exists()
