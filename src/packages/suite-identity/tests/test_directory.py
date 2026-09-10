"""A partial or conflicting import must not change current authorizations."""

from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from django.utils import timezone

import pytest
from suite_identity.directory import SnapshotError, synchronize
from suite_identity.models import Account, DirectoryState, GroupMapping, IdentityBinding


@pytest.mark.django_db
def test_complete_snapshot_replay_removal_and_failed_page():
    org, principal, group_id = uuid4(), uuid4(), uuid4()
    user = get_user_model().objects.create(username="existing")
    local = Group.objects.create(name="existing-storage-grant")
    GroupMapping.objects.create(
        group_id=group_id, organization_id=org, local_group=local, display_name="Old"
    )
    original = Account.objects.create(
        user=user,
        principal_id=principal,
        organization_id=org,
        active=True,
        checked_at=timezone.now(),
        policy_allowed=True,
        policy_checked_at=timezone.now(),
    )
    data = {
        "principals": [{"id": str(principal), "active": True, "session_version": 0}],
        "groups": [{"id": str(group_id), "name": "New"}],
        "memberships": [
            {
                "id": str(uuid4()),
                "principal_id": str(principal),
                "group_id": str(group_id),
            }
        ],
        "identities": [
            {
                "id": str(uuid4()),
                "principal_id": str(principal),
                "issuer": "https://qa.invalid",
                "subject": "opaque/sub",
                "enabled": True,
            }
        ],
    }
    revision = 1

    def fetch(params):
        kind = params["kind"]
        return {
            "version": 1,
            "organization_id": str(org),
            "app_id": "drive",
            "revision": revision,
            "kind": kind,
            "results": data.get(kind, []),
            "next": None,
        }

    with override_settings(SUITE_ORGANIZATION_ID=str(org), SUITE_APP_ID="drive"):
        synchronize(fetch)
        synchronize(fetch)
        assert list(user.groups.values_list("pk", flat=True)) == [local.pk]
        assert IdentityBinding.objects.get().user_id == user.pk
        assert Account.objects.get(user=user).policy_checked_at == original.policy_checked_at
        checkpoint = DirectoryState.objects.get().checked_at
        revision = 2

        def broken(params):
            page = fetch(params)
            if params["kind"] == "memberships":
                raise SnapshotError("network_failure")
            return page

        with pytest.raises(SnapshotError):
            synchronize(broken)
        assert DirectoryState.objects.get().checked_at == checkpoint
        assert user.groups.filter(pk=local.pk).exists()

        revision = 3
        data["memberships"] = []
        synchronize(fetch)
        assert not user.groups.exists()
        assert GroupMapping.objects.get().local_group_id == local.pk
        assert GroupMapping.objects.get().display_name == "New"
        revision = 1
        with pytest.raises(SnapshotError, match="older_snapshot"):
            synchronize(fetch)
