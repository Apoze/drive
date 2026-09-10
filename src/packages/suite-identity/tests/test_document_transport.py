"""Scoped document credentials and real durable-account revocation boundaries."""

import json
import time
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.utils import timezone

import pytest
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from suite_identity.access import request_proofs
from suite_identity.document_transport import actor_context, receive, resolve_actor
from suite_identity.models import Account


@pytest.mark.django_db
def test_document_actor_and_scoped_credentials(settings, tmp_path):
    """A mutation key, live epoch and actual session are independently required."""
    org = uuid4()
    settings.SUITE_ORGANIZATION_ID = str(org)
    settings.SUITE_OIDC_ISSUER = "https://identity.example.invalid"
    user = get_user_model().objects.create(username="document-reader")
    account = Account.objects.create(
        user=user, principal_id=uuid4(), organization_id=org, active=True,
        checked_at=timezone.now(), policy_checked_at=timezone.now(), policy_allowed=True,
    )
    proof = {"principal_id": str(account.principal_id), "session_version": 0,
             "issuer": settings.SUITE_OIDC_ISSUER, "auth_until": time.time() + 60}
    token = request_proofs.set({})
    try:
        with pytest.raises(PermissionDenied):
            actor_context(user)
        request_proofs.get()[user.pk] = proof
        actor = actor_context(user)
        assert resolve_actor(actor).pk == user.pk
        foreign = actor | {"proof": proof | {"issuer": "https://peer.example.invalid"}}
        with pytest.raises(DjangoPermissionDenied):
            resolve_actor(foreign)
        settings.DOCS_DRIVE_ENABLED = True
        settings.DOCUMENT_PEER_OIDC_ISSUER = "https://peer.example.invalid"
        assert resolve_actor(foreign).pk == user.pk
        assert actor_context(user) == foreign
        settings.DOCUMENT_PEER_OIDC_ISSUER = "https://new-peer.example.invalid"
        with pytest.raises(DjangoPermissionDenied):
            resolve_actor(foreign)
        request_proofs.get()[user.pk] = proof
        retained = {field: getattr(account, field) for field in ("principal_id", "organization_id", "active", "checked_at", "policy_checked_at", "policy_allowed")}
        account.delete()
        with patch("suite_identity.directory.synchronize", side_effect=lambda: Account.objects.create(user=user, **retained)) as projection:
            assert resolve_actor(actor).pk == user.pk
            projection.assert_called_once()
        account = Account.objects.get(user=user)
        with pytest.raises(AuthenticationFailed):
            resolve_actor(actor | {"organization": str(uuid4())})
        with pytest.raises(DjangoPermissionDenied):
            resolve_actor(actor | {"proof": proof | {"auth_until": time.time() - 1}})
        for purpose in ("read", "mutation"):
            credential = tmp_path / purpose
            credential.write_text(purpose.ljust(48, "-"))
            credential.chmod(0o600)
            setattr(settings, f"DOCUMENT_INBOUND_{purpose.upper()}_KEY_FILE", str(credential))
        factory = APIRequestFactory()

        def request(key):
            return Request(factory.post(
                "/internal/documents/", json.dumps({"actor": actor, "payload": {"id": "x"}}),
                content_type="application/json", HTTP_X_DOCUMENT_KEY=key,
            ))

        with pytest.raises(AuthenticationFailed):
            receive(request("read".ljust(48, "-")), purpose="mutation")
        authorized = request("mutation".ljust(48, "-"))
        assert receive(authorized, purpose="mutation") == {"id": "x"}
        assert authorized.user.pk == user.pk
        account.session_version = 1
        account.save(update_fields=["session_version"])
        with pytest.raises(DjangoPermissionDenied):
            receive(request("mutation".ljust(48, "-")), purpose="mutation")
    finally:
        request_proofs.reset(token)


def test_folder_bearer_never_becomes_a_human_identity(settings):
    from django.contrib.auth.models import AnonymousUser
    from suite_identity.document_transport import document_links, validated_links

    settings.SUITE_IDENTITY_ENABLED = True
    identifier = str(uuid4())
    link = {"kind": "mount", "token": "synthetic-bearer"}
    previous = document_links.set({identifier: link})
    try:
        actor = actor_context(AnonymousUser())
        assert actor == {"links": {identifier: link}}
        assert not resolve_actor(actor).is_authenticated
        assert document_links.get() == {identifier: link}
        assert validated_links({identifier.upper(): link}) == {identifier: link}
        with pytest.raises(AuthenticationFailed):
            validated_links({identifier: {**link, "role": "owner"}})
        with pytest.raises(AuthenticationFailed):
            validated_links({str(uuid4()): link for _ in range(9)})
        with pytest.raises(AuthenticationFailed):
            resolve_actor({"links": {identifier: link}, "principal": str(uuid4())})
        assert not resolve_actor(None).is_authenticated
        assert document_links.get() == {}
    finally:
        document_links.reset(previous)


def test_document_command_validation_is_not_an_outage(settings, tmp_path):
    from urllib.error import HTTPError
    from rest_framework.exceptions import APIException
    from suite_identity.document_transport import send

    credential = tmp_path / "mutation"
    credential.write_text("synthetic-key".ljust(48, "-"))
    credential.chmod(0o600)
    settings.DOCUMENT_OUTBOUND_MUTATION_KEY_FILE = str(credential)
    settings.DOCUMENT_PEER_API_URL = "http://peer.invalid"
    with patch("suite_identity.document_transport.read_json", side_effect=HTTPError(
        "http://peer.invalid", 400, "Invalid intent", {}, None,
    )):
        with pytest.raises(APIException) as refused:
            send("/command/", {}, purpose="mutation")
    assert refused.value.status_code == 400
