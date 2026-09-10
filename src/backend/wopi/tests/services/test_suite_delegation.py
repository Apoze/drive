"""Private editor and stream tickets share the suite revocation boundary."""

import time
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.utils import timezone

import pytest
from suite_identity.access import delegation_proof, private_url_ttl, request_proofs
from suite_identity.models import Account

from core.factories import ItemFactory, UserFactory, UserItemAccessFactory
from core.services.mount_stream_access import MountStreamAccessService, NewMountStreamAccess
from wopi.services.access import AccessUserItemService, AccessUserMountEntryService


@pytest.mark.django_db
def test_suite_epoch_and_issuer_revoke_s3_mount_and_stream_tickets(settings):
    """Existing private tickets fail after logout/cutover; browser proof never slides."""
    settings.SUITE_IDENTITY_ENABLED = True
    settings.SUITE_OIDC_ISSUER = "https://idp.suite-qa.invalid"
    user = UserFactory()
    item = ItemFactory(creator=user)
    UserItemAccessFactory(user=user, item=item, role="owner")
    now = timezone.now()
    account = Account.objects.create(
        user=user,
        principal_id=uuid4(),
        organization_id=uuid4(),
        active=True,
        policy_allowed=True,
        checked_at=now,
        policy_checked_at=now,
    )
    proof = delegation_proof(user)
    proof["auth_until"] = time.time() + 30
    context = request_proofs.set({user.pk: proof})
    try:
        s3 = AccessUserItemService()
        native = AccessUserMountEntryService()
        stream = MountStreamAccessService()
        s3_token, _ = s3.insert_new_access(item, user)
        native_token, _, _ = native.insert_new_access(
            mount_id="qa", normalized_path="/file.odt", user=user
        )
        stream_token, _ = stream.insert_new_access(
            NewMountStreamAccess(
                mount_id="qa",
                normalized_path="/file.pdf",
                user=user,
                version="v1",
                filename="file.pdf",
                content_type="application/pdf",
                content_length=10,
                disposition="inline",
                purpose="preview",
                supports_range=True,
            )
        )
        assert 1 <= private_url_ttl(user, 3600) <= 30
        checks = [
            (s3.get_access_user_item, s3_token),
            (native.get_access_user_mount_entry, native_token),
            (stream.get_access_user_mount_stream, stream_token),
        ]
        for read, token in checks:
            assert read(token).identity_proof["auth_until"] == proof["auth_until"]
        Account.objects.filter(pk=account.pk).update(session_version=1)
        for read, token in checks:
            with pytest.raises(PermissionDenied):
                read(token)
        Account.objects.filter(pk=account.pk).update(session_version=0)
        settings.SUITE_OIDC_ISSUER = "https://replacement.suite-qa.invalid"
        for read, token in checks:
            with pytest.raises(PermissionDenied):
                read(token)
        assert ItemFactory._meta.model.objects.filter(pk=item.pk).exists()
    finally:
        request_proofs.reset(context)
