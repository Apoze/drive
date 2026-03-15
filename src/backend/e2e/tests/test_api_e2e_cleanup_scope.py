"""Tests for precise E2E scope cleanup."""

from django.test.utils import override_settings

import pytest
from lasuite.drf.models.choices import LinkReachChoices
from rest_framework.test import APIClient

from core import models
from core.tests.utils.urls import reload_urls

from e2e.utils import find_main_workspace

pytestmark = pytest.mark.django_db

S2S_TOKEN = "drive-e2e-s2s"


def _auth_headers():
    return {"HTTP_AUTHORIZATION": f"Bearer {S2S_TOKEN}"}


def _bootstrap_scenario(client, *, run_id, worker_id, scenario_id):
    response = client.post(
        "/api/v1.0/e2e/bootstrap-scenario/",
        {
            "kind": "isolated_workspace_root",
            "run_id": run_id,
            "worker_id": worker_id,
            "actor_key": "primary",
            "scenario_id": scenario_id,
        },
        format="json",
        **_auth_headers(),
    )
    assert response.status_code == 200
    return response.json()


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_cleanup_scope_validates_scope_hierarchy():
    """Scenario cleanup requires both worker and actor coordinates."""
    reload_urls()
    client = APIClient()

    missing_worker = client.post(
        "/api/v1.0/e2e/cleanup-scope/",
        {
            "run_id": "run-a",
            "scenario_id": "scenario-a",
        },
        format="json",
        **_auth_headers(),
    )

    assert missing_worker.status_code == 400
    payload = missing_worker.json()
    assert payload["type"] == "validation_error"
    errors = {error["attr"]: error for error in payload["errors"]}
    assert errors["worker_id"]["detail"] == (
        "This field is required when scenario_id is provided."
    )

    missing_actor = client.post(
        "/api/v1.0/e2e/cleanup-scope/",
        {
            "run_id": "run-a",
            "worker_id": "worker-0",
            "scenario_id": "scenario-a",
        },
        format="json",
        **_auth_headers(),
    )

    assert missing_actor.status_code == 400
    payload = missing_actor.json()
    assert payload["type"] == "validation_error"
    errors = {error["attr"]: error for error in payload["errors"]}
    assert errors["actor_key"]["detail"] == (
        "This field is required when scenario_id is provided."
    )


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_cleanup_scope_can_remove_one_scenario_without_touching_another():
    """Scenario cleanup must only remove the targeted deterministic root."""
    reload_urls()
    client = APIClient()

    first = _bootstrap_scenario(
        client,
        run_id="run-scenario",
        worker_id="worker-0",
        scenario_id="scenario-alpha",
    )
    second = _bootstrap_scenario(
        client,
        run_id="run-scenario",
        worker_id="worker-0",
        scenario_id="scenario-beta",
    )

    user = models.User.objects.get(email=first["actor"]["email"])
    workspace = find_main_workspace(user)
    assert workspace is not None
    assert (
        workspace.children()
        .filter(title=first["result"]["workspace_root"]["title"])
        .exists()
    )
    assert (
        workspace.children()
        .filter(title=second["result"]["workspace_root"]["title"])
        .exists()
    )

    cleanup = client.post(
        "/api/v1.0/e2e/cleanup-scope/",
        {
            "run_id": "run-scenario",
            "worker_id": "worker-0",
            "actor_key": "primary",
            "scenario_id": "scenario-alpha",
        },
        format="json",
        **_auth_headers(),
    )

    assert cleanup.status_code == 200
    payload = cleanup.json()
    assert payload["cleanup"]["mode"] == "scenario"
    assert (
        first["result"]["workspace_root"]["title"]
        in payload["cleanup"]["deleted_titles"]
    )
    assert (
        not workspace.children()
        .filter(title=first["result"]["workspace_root"]["title"])
        .exists()
    )
    assert (
        workspace.children()
        .filter(title=second["result"]["workspace_root"]["title"])
        .exists()
    )


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_cleanup_scope_can_remove_one_worker_without_touching_others():
    """Worker cleanup must only clear the users attached to one worker slug."""
    reload_urls()
    client = APIClient()

    worker_a = _bootstrap_scenario(
        client,
        run_id="run-worker",
        worker_id="worker-0",
        scenario_id="scenario-alpha",
    )
    worker_b = _bootstrap_scenario(
        client,
        run_id="run-worker",
        worker_id="worker-1",
        scenario_id="scenario-bravo",
    )

    user_a = models.User.objects.get(email=worker_a["actor"]["email"])
    user_b = models.User.objects.get(email=worker_b["actor"]["email"])
    workspace_a = find_main_workspace(user_a)
    workspace_b = find_main_workspace(user_b)
    assert workspace_a is not None
    assert workspace_b is not None
    assert workspace_a.children().exists()
    assert workspace_b.children().exists()

    cleanup = client.post(
        "/api/v1.0/e2e/cleanup-scope/",
        {
            "run_id": "run-worker",
            "worker_id": "worker-0",
        },
        format="json",
        **_auth_headers(),
    )

    assert cleanup.status_code == 200
    payload = cleanup.json()
    assert payload["cleanup"]["mode"] == "worker"
    assert worker_a["actor"]["email"] in payload["cleanup"]["matched_user_emails"]
    assert worker_b["actor"]["email"] not in payload["cleanup"]["matched_user_emails"]

    assert not workspace_a.children().exists()
    assert (
        workspace_b.children()
        .filter(title=worker_b["result"]["workspace_root"]["title"])
        .exists()
    )


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_cleanup_scope_actor_cleanup_removes_link_traces_and_favorites():
    """Actor cleanup must purge item-bound relations before deleting the subtree."""
    reload_urls()
    client = APIClient()

    scenario = _bootstrap_scenario(
        client,
        run_id="run-actor",
        worker_id="worker-0",
        scenario_id="scenario-link-trace",
    )

    user = models.User.objects.get(email=scenario["actor"]["email"])
    workspace = find_main_workspace(user)
    assert workspace is not None
    root = workspace.children().get(title=scenario["result"]["workspace_root"]["title"])

    linked_item = models.Item.objects.create_child(
        parent=root,
        creator=user,
        link_reach=LinkReachChoices.AUTHENTICATED,
        type=models.ItemTypeChoices.FOLDER,
        title="Link Trace Folder",
        main_workspace=False,
    )
    models.LinkTrace.objects.create(item=linked_item, user=user)
    models.ItemFavorite.objects.create(item=linked_item, user=user)

    cleanup = client.post(
        "/api/v1.0/e2e/cleanup-scope/",
        {
            "run_id": "run-actor",
            "worker_id": "worker-0",
            "actor_key": "primary",
        },
        format="json",
        **_auth_headers(),
    )

    assert cleanup.status_code == 200
    payload = cleanup.json()
    assert payload["cleanup"]["mode"] == "actor"
    assert not workspace.children().exists()
    assert not models.LinkTrace.objects.filter(item=linked_item).exists()
    assert not models.ItemFavorite.objects.filter(item=linked_item).exists()


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_cleanup_scope_actor_cleanup_supports_custom_email_actor():
    """Actor cleanup should still match actors bootstrapped with an explicit email."""
    reload_urls()
    client = APIClient()

    session = client.post(
        "/api/v1.0/e2e/bootstrap-session/",
        {
            "run_id": "run-custom-email",
            "worker_id": "worker-0",
            "actor_key": "primary",
            "email": "drive@example.com",
        },
        format="json",
        **_auth_headers(),
    )
    assert session.status_code == 200

    user = models.User.objects.get(email="drive@example.com")
    workspace = find_main_workspace(user)
    assert workspace is not None
    models.Item.objects.create_child(
        parent=workspace,
        creator=user,
        link_reach=LinkReachChoices.RESTRICTED,
        type=models.ItemTypeChoices.FOLDER,
        title="Custom Email Root",
        main_workspace=False,
    )

    cleanup = client.post(
        "/api/v1.0/e2e/cleanup-scope/",
        {
            "run_id": "run-custom-email",
            "worker_id": "worker-0",
            "actor_key": "primary",
        },
        format="json",
        **_auth_headers(),
    )

    assert cleanup.status_code == 200
    payload = cleanup.json()
    assert payload["cleanup"]["mode"] == "actor"
    assert payload["cleanup"]["matched_user_emails"] == ["drive@example.com"]
    assert not workspace.children().exists()
