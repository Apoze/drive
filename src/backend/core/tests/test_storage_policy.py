"""Storage policies follow accounting organizations independently of user membership."""

import json
import urllib.parse
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest
import responses
from rest_framework.test import APIClient

from core import factories, models
from core.services.storage_inventory import _apply_storage_policy, item_usage, resource_metrics
from core.services.storage_quota import apply_policy

pytestmark = pytest.mark.django_db
ENTITLEMENTS_URL = "https://st.example.test/api/v1.0/entitlements/"
ENTITLEMENTS_BACKEND_PARAMETERS = {
    "base_url": ENTITLEMENTS_URL,
    "api_key": "test-service-key",
    "service_id": 8,
}


@responses.activate
def test_shared_storage_policy_uses_its_organization(settings):
    """Apply both independent budgets and acknowledge known unlimited spaces."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.services.storage_inventory import refresh_policy  # noqa: PLC0415

    settings.STORAGE_GOVERNANCE_ENABLED = True
    settings.STORAGE_ADMIN_URL = "https://st.example.test"
    settings.ENTITLEMENTS_BACKEND = (
        "core.entitlements.backends.deploycenter.DeployCenterEntitlementsBackend"
    )
    settings.ENTITLEMENTS_BACKEND_PARAMETERS = {
        **ENTITLEMENTS_BACKEND_PARAMETERS,
        "organization_claim": "organization_id",
        "oidc_claims": [],
    }
    organization_a, organization_b = str(uuid.uuid4()), str(uuid.uuid4())
    actor = factories.UserFactory(claims={"organization_id": organization_a})
    backend = models.StorageBackend.objects.create(
        organization=organization_b,
        name="Shared storage",
        family="s3",
        registry_id="shared-policy",
    )
    space = models.StorageSpace.objects.create(backend=backend, name="Shared")

    def policy_response(request):
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(request.url).query)
        organization = params["organization_id"][0]
        if organization == organization_b:
            assert params["account_type"] == ["organization"]
            assert params["account_id"] == [organization_b]
            metrics = json.loads(request.body)["usage_metrics"]
            assert all(entry["organization_id"] == organization_b for entry in metrics)
            assert not any(entry["account"]["type"] == "user" for entry in metrics)
        return (
            200,
            {},
            json.dumps(
                {
                    "organization": {"id": organization},
                    "operator": {"id": organization_b},
                    "entitlements": {
                        "can_access": True,
                        "storage_policy": {
                            "revision": "a" * 64 if organization == organization_a else "b" * 64,
                            "version": 1,
                            "resources": [],
                            "account": {"limit_bytes": 5, "growth_blocked": False},
                            "organization": {
                                "limit_bytes": 10 if organization == organization_a else 20,
                                "growth_blocked": False,
                            },
                        },
                    },
                }
            ),
        )

    responses.add_callback(responses.POST, ENTITLEMENTS_URL, callback=policy_response)
    with mock.patch("core.services.storage_inventory.app.send_task"):
        refresh_policy(actor, organization=organization_b)
    budgets = {row.key: row for row in models.StorageQuota.objects.all()}
    assert budgets[f"user:{actor.pk}"].limit_bytes == 5
    assert budgets[f"organization:{organization_a}"].limit_bytes == 10
    assert budgets[f"organization:{organization_b}"].limit_bytes == 20
    assert budgets[f"space:{space.pk}"].limit_bytes is None
    assert budgets[f"space:{space.pk}"].policy_applied_at is not None
    assert budgets[f"backend:{backend.namespace}"].policy_origin.endswith(organization_b)
    actor.is_superuser = True
    actor.save(update_fields=["is_superuser"])
    api = APIClient()
    api.force_authenticate(actor)
    link = api.get(f"/api/v1.0/storage-spaces-admin/{space.pk}/quota-link/")
    assert link.status_code == 200
    url = urllib.parse.urlsplit(link.data["url"])
    assert url.netloc == "st.example.test"
    assert url.path == f"/operators/{organization_b}/organizations/{organization_b}"
    assert urllib.parse.parse_qs(url.query) == {
        "service_id": ["8"],
        "resource_type": ["storage_space"],
        "resource_id": [str(space.pk)],
    }
    api.force_authenticate(factories.UserFactory())
    assert api.get(f"/api/v1.0/storage-spaces-admin/{space.pk}/quota-link/").status_code == 404


@pytest.mark.django_db(transaction=True)
def test_legacy_s3_policies_cannot_replace_another_organization_budget(settings):
    """Per-organization aliases preserve the pre-migration global S3 ceiling."""
    settings.STORAGE_GOVERNANCE_ENABLED = True
    apply_policy({"backend:s3": {"limit_bytes": 100}}, revision="historical")
    connections = []
    for index, organization in enumerate(("organization-a", "organization-b")):
        backend = models.StorageBackend.objects.create(
            registry_id=organization,
            name=organization,
            family="s3",
            organization=organization,
            legacy_s3=True,
        )
        connections.append(backend)
        item = factories.ItemFactory(storage_backend=backend, size=4)
        item_usage(item, initial_size=4)
        policy = {
            "revision": organization,
            "version": index + 1,
            "organization": {"limit_bytes": 20},
            "resources": [
                {
                    "type": "storage_backend",
                    "id": "s3",
                    "limit_bytes": 10 + index,
                    "growth_blocked": False,
                }
            ],
        }
        _apply_storage_policy(SimpleNamespace(service_id=8), policy, organization)
        metrics = resource_metrics(organization, None)
        metric = next(row for row in metrics if row["account"]["type"] == "storage_backend")
        assert metric["account"]["id"] == str(backend.namespace)
        assert metric["metrics"]["storage_used"] == 4
    for index, backend in enumerate(connections):
        assert (
            models.StorageQuota.objects.get(key=f"backend:{backend.namespace}").limit_bytes
            == 10 + index
        )
    original = models.StorageQuota.objects.get(key="backend:s3")
    assert original.limit_bytes == 100
    assert original.used_bytes == 8
    assert original.policy_revision == "historical"
    policy["version"] += 1
    policy["revision"] = "isolated-update"
    policy["resources"].extend(
        [
            {
                "type": "storage_backend",
                "id": str(connections[0].namespace),
                "limit_bytes": 1,
                "growth_blocked": False,
            },
            {
                "type": "storage_backend",
                "id": str(connections[1].namespace),
                "limit_bytes": 15,
                "growth_blocked": False,
            },
        ]
    )
    _apply_storage_policy(SimpleNamespace(service_id=8), policy, connections[1].organization)
    assert (
        models.StorageQuota.objects.get(key=f"backend:{connections[0].namespace}").limit_bytes == 10
    )
    assert (
        models.StorageQuota.objects.get(key=f"backend:{connections[1].namespace}").limit_bytes == 15
    )
