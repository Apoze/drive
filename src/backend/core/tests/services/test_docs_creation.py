"""Creation visibility follows content publication, not just metadata delivery."""

from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser

import pytest
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory
from suite_identity.models import Account

from core import factories, models
from core.api.docs_documents import DocumentCommandSerializer
from core.api.serializers import CreateItemSerializer, ItemSerializer
from core.services.docs_lifecycle import (
    change_document,
    command_status,
    create_document,
    pending_creations,
    synchronize,
)
from core.services.docs_quota import reserve, transition


@pytest.mark.django_db(transaction=True)
def test_initial_content_stays_private_until_committed(settings):  # noqa: PLR0915
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    user, stranger = factories.UserFactory.create_batch(2)
    parent = models.Item.objects.create(type="docs", title="Imports", creator=user)
    models.DocsBinding.objects.create(item=parent, state="active", applied_revision=1)
    models.ItemAccess.objects.create(item=parent, user=user, role="owner")
    key = uuid4()
    actor = {"principal": str(uuid4()), "organization": str(uuid4())}
    initial = {"size": 4, "digest": "a" * 64}
    with patch("suite_identity.document_transport.actor_context", return_value=actor):
        binding = create_document(
            user,
            title="Import",
            request_key=key,
            destination=parent.pk,
            initial_content=initial,
        )
    with patch(
        "suite_identity.document_transport.send",
        return_value={
            "item_id": str(binding.item_id),
            "revision": 1,
        },
    ):
        assert synchronize(binding.pk)
    binding.refresh_from_db()
    assert binding.state == "preparing"
    assert not binding.item.get_abilities(user)["retrieve"]
    with pytest.raises(PermissionDenied):
        reserve(stranger, document_id=binding.document_id, operation_id=key, size=4)
    with pytest.raises(PermissionDenied):
        reserve(user, document_id=binding.document_id, operation_id=uuid4(), size=4)
    with patch("core.services.docs_quota.refresh_policy"):
        pending = pending_creations(user, limit=1)
        assert pending["count"] == 1
        assert pending["results"][0]["destination"] == str(parent.pk)
        assert pending_creations(factories.UserFactory())["count"] == 0
        reserve(user, document_id=binding.document_id, operation_id=key, size=4)
    publication = {
        "action": "begin",
        "document_id": binding.document_id,
        "operation_id": key,
        "size": 4,
        "digest": initial["digest"],
        "version": "",
    }
    with pytest.raises(PermissionDenied):
        transition(user, {**publication, "digest": "b" * 64})
    assert transition(user, publication)["state"] == "publishing"
    binding.item.title = "Still preparing"
    binding.item.save(update_fields=["title"])
    binding.refresh_from_db()
    assert binding.state == "preparing"
    assert (
        transition(
            AnonymousUser(),
            {
                **publication,
                "action": "commit",
                "version": "native-version",
            },
        )["state"]
        == "committed"
    )
    binding.refresh_from_db()
    assert binding.state == "preparing"
    with patch(
        "suite_identity.document_transport.send",
        return_value={
            "item_id": str(binding.item_id),
            "revision": binding.revision,
        },
    ):
        assert synchronize(binding.pk)
    binding.refresh_from_db()
    assert binding.state == "active"
    binding.item.refresh_from_db()
    assert binding.item.get_abilities(user)["retrieve"]
    settings.DOCS_PUBLIC_URL = "https://docs.example.invalid"
    request = APIRequestFactory().get("/items/")
    request.user = user
    serialized = ItemSerializer(binding.item, context={"request": request}).data
    assert serialized["document"]["id"] == str(binding.document_id)
    assert (
        serialized["document"]["url"] == f"https://docs.example.invalid/docs/{binding.document_id}/"
    )
    assert serialized["url"] is None
    invalid = CreateItemSerializer(data={"type": "docs", "title": "Unbound"})
    assert not invalid.is_valid() and "type" in invalid.errors
    invitation = models.Invitation.objects.create(
        item=binding.item,
        email="native-invitee@example.invalid",
        role="reader",
    )
    invitee = factories.UserFactory(email=invitation.email)
    assert models.Invitation.objects.filter(pk=invitation.pk).exists()
    assert not models.ItemAccess.objects.filter(item=binding.item, user=invitee).exists()
    Account.objects.create(
        user=user,
        principal_id=actor["principal"],
        organization_id=actor["organization"],
        active=True,
    )
    tombstone = models.DocsBinding.objects.create(state="purged", creation_context=actor)
    assert command_status(user, tombstone.request_key)["state"] == "purged"
    with pytest.raises(NotFound):
        command_status(stranger, tombstone.request_key)


@pytest.mark.django_db(transaction=True)
def test_abandoned_creation_retains_quota_until_native_purge(settings):
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    user = factories.UserFactory()
    parent = models.Item.objects.create(type="docs", title="Parent", creator=user)
    models.DocsBinding.objects.create(item=parent, state="active", applied_revision=1)
    models.ItemAccess.objects.create(item=parent, user=user, role="owner")
    key = uuid4()
    with patch(
        "suite_identity.document_transport.actor_context",
        return_value={
            "principal": str(uuid4()),
            "organization": str(uuid4()),
        },
    ):
        binding = create_document(
            user,
            title="Interrupted",
            request_key=key,
            destination=parent.pk,
            initial_content={"size": 4, "digest": "a" * 64},
        )

    with patch("core.services.docs_quota.refresh_policy"):
        reserve(user, document_id=binding.document_id, operation_id=key, size=4)
    backend = models.StorageBackend.objects.create(
        registry_id="cancel-copy", family="s3", organization="local", name="Storage"
    )
    space = models.StorageSpace.objects.create(backend=backend, owner=user, name="Space")
    job = models.StorageMoveJob.objects.create(
        actor=user,
        space=space,
        kind="docs_copy",
        state="conflict",
        source_path=str(parent.pk),
        destination_path=str(parent.pk),
        source_identity=str(parent.pk),
    )
    models.StorageCopyEntry.objects.create(
        job=job,
        source_id=parent.pk,
        kind="docs",
        name="Copy",
        source={"document_id": str(parent.docs_binding.document_id)},
        publication={"document_id": str(binding.document_id)},
    )
    settings.STORAGE_GOVERNANCE_ENABLED = True
    request = {
        "action": "cancel_creation",
        "document_id": binding.document_id,
        "request_key": uuid4(),
    }
    with patch("suite_identity.document_transport.send", side_effect=PermissionDenied()):
        assert change_document(user, request)["state"] == "purging"
    assert models.StorageReservation.objects.get(pk=key).state == "publishing"

    def deleted(_path, payload, **_kwargs):
        assert payload["abort_request_key"] == str(key)
        transition(
            AnonymousUser(),
            {
                "action": "cancel",
                "document_id": binding.document_id,
                "operation_id": key,
                "unpublished": True,
                "version": "",
            },
        )
        return {"item_id": payload["item_id"], "revision": payload["revision"], "state": "purged"}

    with patch("suite_identity.document_transport.send", side_effect=deleted):
        assert change_document(user, request)["state"] == "purged"
        assert change_document(user, request)["state"] == "purged"
    job.refresh_from_db()
    assert job.state == "failed"
    assert models.StorageReservation.objects.get(pk=key).state == "cancelled"
    assert models.StorageUsage.objects.get(item=binding.item).size == 0
    models.StorageReservation.objects.filter(pk=key).delete()
    assert (
        transition(
            AnonymousUser(),
            {
                "action": "cancel",
                "document_id": binding.document_id,
                "operation_id": key,
                "unpublished": True,
                "version": "",
            },
        )["state"]
        == "cancelled"
    )
    with pytest.raises(NotFound):
        transition(
            AnonymousUser(),
            {
                "action": "cancel",
                "document_id": binding.document_id,
                "operation_id": uuid4(),
                "unpublished": True,
                "version": "",
            },
        )


@pytest.mark.django_db(transaction=True)
def test_cancel_before_receipt_fences_a_delayed_creation(settings):
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    user = factories.UserFactory()
    actor = {"principal": str(uuid4()), "organization": str(uuid4())}
    document_id, key = uuid4(), uuid4()
    serializer = DocumentCommandSerializer(
        data={
            "action": "cancel_creation",
            "document_id": document_id,
            "creation_key": key,
            "request_key": uuid4(),
        }
    )
    assert serializer.is_valid(), serializer.errors
    with patch("suite_identity.document_transport.actor_context", return_value=actor):
        first = change_document(user, serializer.validated_data)
        assert first["state"] == "purged" and first["item_id"] is None
        assert change_document(user, serializer.validated_data) == first
        with pytest.raises(ValidationError):
            create_document(
                user, title="Delayed", request_key=key, document_id=document_id, destination=uuid4()
            )
    with patch(
        "suite_identity.document_transport.actor_context",
        return_value={
            **actor,
            "principal": str(uuid4()),
        },
    ):
        with pytest.raises(PermissionDenied):
            change_document(user, serializer.validated_data)
