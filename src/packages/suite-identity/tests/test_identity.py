"""Critical identity and revocation boundaries; no source-text assertions."""

from datetime import timedelta
from io import StringIO
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

import pytest
from suite_identity.access import DirectoryUnavailable, private_url_ttl, require_access
from suite_identity.login import AuthenticationRequired
from suite_identity.models import Account, IdentityBinding
from suite_identity.oidc import validate_claims, verified_email


def test_invitation_email_requires_explicit_idp_verification():
    assert verified_email({"email": "Recipient@example.test", "email_verified": True}) == "recipient@example.test"
    for value in [False, "true", 1, None]:
        assert verified_email({"email": "recipient@example.test", "email_verified": value}) == ""
    assert verified_email({"email": ["recipient@example.test"], "email_verified": True}) == ""


@pytest.mark.parametrize(
    "change",
    [
        {"iss": "https://other.invalid"},
        {"aud": "other-client"},
        {"exp": 990},
        {"iat": 1100},
        {"auth_time": 1},
        {"nbf": 1100},
        {"sub": ""},
        {"aud": ["drive", "other"], "azp": "other"},
        {"aud": ["drive", 1], "azp": "drive"},
        {"exp": True},
        {"auth_time": float("nan")},
    ],
)
def test_wrong_oidc_context_rejected(change):
    """A valid signature alone does not authorize a claim context."""
    payload = {
        "iss": "https://id.invalid",
        "aud": "drive",
        "sub": "opaque/subject",
        "exp": 1200,
        "iat": 990,
        "auth_time": 990,
    }
    with pytest.raises((SuspiciousOperation, AuthenticationRequired)):
        validate_claims(
            payload | change,
            issuer="https://id.invalid",
            client_id="drive",
            max_age=900,
            now=1000,
        )
    validate_claims(payload, issuer="https://id.invalid", client_id="drive", max_age=900, now=1000)


@pytest.mark.django_db
def test_binding_preserves_accounts_and_refuses_collision():
    """Issuer scoping, dry run and replay preserve the same user and principal."""
    users = [
        get_user_model().objects.create(username=f"u{i}", email="same@example.invalid")
        for i in range(2)
    ]
    org = uuid4()
    args = {
        "user_id": str(users[0].pk),
        "principal_id": uuid4(),
        "organization_id": str(org),
        "issuer": "https://one.invalid",
        "subject": "opaque/subject",
        "stdout": StringIO(),
    }
    call_command("suite_bind_identity", **args)
    assert not IdentityBinding.objects.exists()
    unbound = {key: value for key, value in args.items() if key not in {"issuer", "subject"}}
    call_command("suite_bind_identity", **unbound, apply=True)
    assert Account.objects.get(user=users[0]).principal_id == args["principal_id"]
    assert not IdentityBinding.objects.exists()
    with pytest.raises(CommandError):
        call_command("suite_bind_identity", **unbound, issuer="https://one.invalid", apply=True)
    call_command("suite_bind_identity", **args, apply=True)
    call_command("suite_bind_identity", **args, apply=True)
    call_command(
        "suite_bind_identity",
        **(
            args
            | {
                "issuer": "https://two.invalid",
                "user_id": str(users[1].pk),
                "principal_id": uuid4(),
            }
        ),
        apply=True,
    )
    assert IdentityBinding.objects.count() == 2
    with pytest.raises(CommandError):
        call_command("suite_bind_identity", **(args | {"user_id": str(users[1].pk)}), apply=True)
    assert get_user_model().objects.count() == 2


@pytest.mark.django_db
def test_expiry_suspension_and_url_lease_do_not_slide():
    """Workers reread suspension, and private URL TTL cannot extend stale rights."""
    user = get_user_model().objects.create(username="member")
    now = timezone.now()
    Account.objects.create(
        user=user,
        principal_id=uuid4(),
        organization_id=uuid4(),
        active=True,
        checked_at=now,
        policy_checked_at=now,
        policy_allowed=True,
    )
    assert require_access(user).user_id == user.pk
    assert 1 <= private_url_ttl(user, 3600) <= 90
    Account.objects.filter(user=user).update(active=False)
    with pytest.raises(PermissionDenied):
        require_access(user)
    Account.objects.filter(user=user).update(active=True, checked_at=now - timedelta(seconds=91))
    with pytest.raises(DirectoryUnavailable):
        require_access(user)
    assert Account.objects.get(user=user).checked_at == now - timedelta(seconds=91)
