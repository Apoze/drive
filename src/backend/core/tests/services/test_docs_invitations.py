"""One workflow covers explicit acceptance, replay, revocation and uncertain mail."""

from unittest.mock import patch
from uuid import uuid4

from django.utils import timezone

import pytest
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate
from suite_identity.access import request_proofs

from core import factories, models
from core.api.docs_documents import DocumentCommandSerializer
from core.api.viewsets import InvitationViewset
from core.services.docs_invitations import accept, acceptance_token, deliver, legacy_offer, page
from core.services.docs_lifecycle import change_document


@pytest.fixture
def invitation_proofs():
    proofs = {}
    token = request_proofs.set(proofs)
    yield proofs
    request_proofs.reset(token)


@pytest.mark.django_db(transaction=True)
def test_document_invitation_requires_explicit_proof_and_does_not_regrant(  # noqa: PLR0915
    settings, invitation_proofs
):
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    settings.EMAIL_HOST = "test.invalid"
    settings.DOCS_PUBLIC_URL = "https://docs.example.invalid"
    owner, recipient, stranger = factories.UserFactory.create_batch(3)
    invitation_proofs.update(
        {user.pk: {"verified_email": user.email} for user in [recipient, stranger]}
    )
    item = models.Item.objects.create(type="docs", title="Invitations", creator=owner)
    binding = models.DocsBinding.objects.create(item=item, state="active", applied_revision=1)
    owner_access = models.ItemAccess.objects.create(item=item, user=owner, role="owner")
    invite = DocumentCommandSerializer(
        data={
            "action": "invite",
            "document_id": binding.document_id,
            "request_key": uuid4(),
            "email": recipient.email,
            "role": "reader",
        }
    )
    assert invite.is_valid(), invite.errors

    def receipt(_path, payload, **_kwargs):
        return {"item_id": payload["item_id"], "revision": payload["revision"]}

    with patch("suite_identity.document_transport.send", side_effect=receipt):
        change_document(owner, invite.validated_data)
        change_document(owner, invite.validated_data)
    state = models.DocsInvitation.objects.get(invitation__item=item)
    assert state.context["delivery"] == "queued"
    request = APIRequestFactory().post(
        "/invitations/", {"email": recipient.email, "role": "reader"}, format="json"
    )
    force_authenticate(request, user=owner)
    with patch("suite_identity.document_transport.send", side_effect=receipt):
        response = InvitationViewset.as_view({"post": "create"})(request, resource_id=str(item.pk))
    assert response.status_code == 201 and response.data["delivery_state"] == "queued"
    assert models.DocsInvitation.objects.filter(invitation__item=item).count() == 1
    assert page(item, owner, {})["count"] == 1
    with pytest.raises(PermissionDenied):
        page(item, recipient, {})
    assert legacy_offer(recipient, binding.document_id)["token"] is None
    state.context["legacy_native_id"] = str(uuid4())
    state.save(update_fields=["context"])
    assert legacy_offer(stranger, binding.document_id)["token"] is None
    token = legacy_offer(recipient, binding.document_id)["token"]
    assert token == acceptance_token(state)
    recipient.email = "stale-profile@example.invalid"
    with pytest.raises(PermissionDenied):
        verified = invitation_proofs[recipient.pk].pop("verified_email")
        legacy_offer(recipient, binding.document_id)
    invitation_proofs[recipient.pk]["verified_email"] = verified
    assert legacy_offer(recipient, binding.document_id)["token"] == token
    with patch(
        "suite_identity.document_transport.actor_context",
        side_effect=lambda user: {"principal": str(user.pk), "organization": str(uuid4())},
    ):
        with pytest.raises(PermissionDenied):
            accept(stranger, token)
        with pytest.raises(PermissionDenied):
            accept(recipient, token + "invalid")
        assert accept(recipient, token)["state"] == "accepted"
        models.ItemAccess.objects.filter(item=item, user=recipient).delete()
        assert accept(recipient, token)["state"] == "accepted"
        assert not models.ItemAccess.objects.filter(item=item, user=recipient).exists()

    with patch("suite_identity.document_transport.send", side_effect=receipt):
        change_document(owner, {**invite.validated_data, "request_key": uuid4()})
    state.refresh_from_db()
    assert state.context["status"] == "pending"
    assert acceptance_token(state) != token
    assert "accepted_by" not in state.context
    assert not state.invitation.is_expired

    second = {**invite.validated_data, "request_key": uuid4(), "email": stranger.email}
    with patch("suite_identity.document_transport.send", side_effect=receipt):
        change_document(owner, second)
    pending = models.DocsInvitation.objects.get(invitation__email=stranger.email)
    old_token = acceptance_token(pending)
    with patch("core.services.docs_invitations.EmailMultiAlternatives.send", side_effect=OSError):
        deliver(pending.pk)
    pending.refresh_from_db()
    assert pending.context["delivery"] == "uncertain"
    with patch(
        "core.services.docs_invitations.EmailMultiAlternatives.send", return_value=1
    ) as mail:
        deliver(pending.pk)
        assert mail.call_count == 0
        with patch("suite_identity.document_transport.send", side_effect=receipt):
            change_document(
                owner,
                {
                    "action": "resend_invitation",
                    "document_id": binding.document_id,
                    "invitation_id": pending.invitation_id,
                    "request_key": uuid4(),
                },
            )
        deliver(pending.pk)
        deliver(pending.pk)
        assert mail.call_count == 1
    pending.refresh_from_db()
    assert pending.context["delivery"] == "sent"
    with patch(
        "suite_identity.document_transport.actor_context",
        return_value={"principal": str(stranger.pk)},
    ):
        with pytest.raises(PermissionDenied):
            accept(stranger, old_token)
        pending.context["expires"] = int(timezone.now().timestamp()) - 1
        pending.save(update_fields=["context"])
        with pytest.raises(PermissionDenied):
            accept(stranger, acceptance_token(pending))
        pending.context["expires"] += 3600
        pending.save(update_fields=["context"])
        models.ItemAccess.objects.create(item=item, user=recipient, role="owner")
        owner_access.delete()
        with pytest.raises(PermissionDenied):
            accept(stranger, acceptance_token(pending))


@pytest.mark.django_db
def test_document_request_notifications_follow_current_inherited_managers(settings):
    from django.contrib.auth.models import Group  # noqa: PLC0415

    from suite_identity.models import Account, GroupMapping  # noqa: PLC0415

    from core.services.docs_sharing import notification_recipients  # noqa: PLC0415

    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_ORGANIZATION_ID = str(uuid4())
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    owner, manager, requester = factories.UserFactory.create_batch(3)
    accounts = {
        user.pk: Account.objects.create(
            user=user,
            principal_id=uuid4(),
            organization_id=settings.SUITE_ORGANIZATION_ID,
            active=True,
        )
        for user in [owner, manager, requester]
    }
    group = Group.objects.create(name="Current document managers")
    GroupMapping.objects.create(
        group_id=uuid4(),
        local_group=group,
        organization_id=settings.SUITE_ORGANIZATION_ID,
        display_name=group.name,
    )
    manager.groups.add(group)
    item = models.Item.objects.create(type="docs", title="Notify", creator=owner)
    binding = models.DocsBinding.objects.create(item=item, state="active", applied_revision=1)
    models.ItemAccess.objects.create(item=item, user=owner, role="owner")
    access = models.ItemAccess.objects.create(
        item=item, team=f"group:{group.pk}", role="administrator"
    )
    child = models.Item.objects.create_child(parent=item, type="docs", title="Nested")
    binding = models.DocsBinding.objects.create(item=child, state="active", applied_revision=1)
    query = lambda: notification_recipients(
        binding.document_id, accounts[requester.pk].principal_id
    )
    assert {row["email"] for row in query()["results"]} == {owner.email, manager.email}
    access.delete()
    assert {row["email"] for row in query()["results"]} == {owner.email}
    binding.refresh_from_db()
    assert binding.revision > 1
    binding.state = "trash"
    binding.save(update_fields=["state"])
    assert query()["results"] == []
