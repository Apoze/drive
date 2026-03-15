"""Tests for the E2E bootstrap contract."""

from pathlib import Path

from django.test.utils import override_settings

import pytest
from rest_framework.test import APIClient

from core import models
from core.mounts.providers import localfs
from core.tests.utils.urls import reload_urls

pytestmark = pytest.mark.django_db

S2S_TOKEN = "drive-e2e-s2s"


def _auth_headers():
    return {"HTTP_AUTHORIZATION": f"Bearer {S2S_TOKEN}"}


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_bootstrap_session_requires_s2s_token():
    """Bootstrap session must require the server-to-server bearer token."""
    reload_urls()
    client = APIClient()

    response = client.post(
        "/api/v1.0/e2e/bootstrap-session/",
        {
            "run_id": "run-a",
            "worker_id": "worker-0",
            "actor_key": "primary",
        },
        format="json",
    )
    assert response.status_code == 401

    response = client.post(
        "/api/v1.0/e2e/bootstrap-session/",
        {
            "run_id": "run-a",
            "worker_id": "worker-0",
            "actor_key": "primary",
        },
        format="json",
        **_auth_headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["actor"]["email"].startswith("e2e+")
    assert payload["workspace"]["main_workspace"] is True
    assert payload["scope"]["actor_email"] == payload["actor"]["email"]
    assert payload["scope"]["storage_state_slug"]
    assert payload["session"] == {
        "authenticated": True,
        "csrf_cookie_name": "csrftoken",
        "csrf_cookie_present": True,
    }

    me = client.get("/api/v1.0/users/me/")
    assert me.status_code == 200
    assert me.json()["email"] == payload["actor"]["email"]
    assert client.cookies.get("csrftoken") is not None


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_bootstrap_session_is_idempotent():
    """The same bootstrap session request should safely reuse actor/workspace."""
    reload_urls()
    client = APIClient()
    payload = {
        "run_id": "run-a",
        "worker_id": "worker-0",
        "actor_key": "primary",
    }

    first = client.post(
        "/api/v1.0/e2e/bootstrap-session/",
        payload,
        format="json",
        **_auth_headers(),
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1.0/e2e/bootstrap-session/",
        payload,
        format="json",
        **_auth_headers(),
    )
    assert second.status_code == 200

    first_json = first.json()
    second_json = second.json()
    assert first_json["actor"]["email"] == second_json["actor"]["email"]
    assert first_json["workspace"]["id"] == second_json["workspace"]["id"]

    user = models.User.objects.get(email=first_json["actor"]["email"])
    assert user.language == "en-us"
    assert user.full_name
    assert user.short_name


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_bootstrap_session_accepts_null_language():
    """Bootstrap session can intentionally create a null-language actor."""
    reload_urls()
    client = APIClient()

    response = client.post(
        "/api/v1.0/e2e/bootstrap-session/",
        {
            "run_id": "run-b",
            "worker_id": "worker-0",
            "actor_key": "primary",
            "language": None,
        },
        format="json",
        **_auth_headers(),
    )
    assert response.status_code == 200
    payload = response.json()

    user = models.User.objects.get(email=payload["actor"]["email"])
    assert user.language is None


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_bootstrap_session_bounds_generated_profile_fields():
    """Bootstrap session should keep generated actor profile fields model-safe."""
    reload_urls()
    client = APIClient()

    response = client.post(
        "/api/v1.0/e2e/bootstrap-session/",
        {
            "run_id": "run-c",
            "worker_id": "worker-0",
            "actor_key": "auth-language-sync-browser-language-syncs-to-backend-for-new-use",
        },
        format="json",
        **_auth_headers(),
    )
    assert response.status_code == 200
    payload = response.json()

    user = models.User.objects.get(email=payload["actor"]["email"])
    assert len(user.full_name) <= 100
    assert len(user.short_name) <= 100
    assert user.full_name == payload["actor"]["full_name"]
    assert user.short_name == payload["actor"]["short_name"]


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_bootstrap_scenario_isolated_workspace_root_is_idempotent():
    """The isolated workspace root must be namespaced and reusable."""
    reload_urls()
    client = APIClient()
    payload = {
        "kind": "isolated_workspace_root",
        "run_id": "run-a",
        "worker_id": "worker-0",
        "actor_key": "primary",
        "scenario_id": "crud-folder",
    }

    first = client.post(
        "/api/v1.0/e2e/bootstrap-scenario/",
        payload,
        format="json",
        **_auth_headers(),
    )
    second = client.post(
        "/api/v1.0/e2e/bootstrap-scenario/",
        payload,
        format="json",
        **_auth_headers(),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_json = first.json()
    second_json = second.json()
    assert (
        first_json["result"]["workspace_root"]["id"]
        == second_json["result"]["workspace_root"]["id"]
    )
    assert first_json["scope"]["scenario_slug"] == second_json["scope"]["scenario_slug"]


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_bootstrap_scenario_paired_share_creates_secondary_access():
    """Paired share bootstrap should provision both actors and the shared root."""
    reload_urls()
    client = APIClient()

    response = client.post(
        "/api/v1.0/e2e/bootstrap-scenario/",
        {
            "kind": "paired_share",
            "run_id": "run-share",
            "worker_id": "worker-1",
            "actor_key": "primary",
            "secondary_actor_key": "secondary",
            "scenario_id": "share-flow",
        },
        format="json",
        **_auth_headers(),
    )
    assert response.status_code == 200
    payload = response.json()

    shared_root_id = payload["result"]["shared_root"]["id"]
    secondary_email = payload["result"]["secondary_actor"]["email"]
    secondary_user = models.User.objects.get(email=secondary_email)
    shared_root = models.Item.objects.get(id=shared_root_id)
    assert models.ItemAccess.objects.filter(
        item=shared_root,
        user=secondary_user,
        role=models.RoleChoices.READER,
    ).exists()


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_bootstrap_scenario_search_dataset_creates_namespaced_tree():
    """Search dataset bootstrap should create the canonical tree under one scope root."""
    reload_urls()
    client = APIClient()

    response = client.post(
        "/api/v1.0/e2e/bootstrap-scenario/",
        {
            "kind": "search_dataset",
            "run_id": "run-search",
            "worker_id": "worker-2",
            "actor_key": "primary",
            "scenario_id": "search-flow",
        },
        format="json",
        **_auth_headers(),
    )
    assert response.status_code == 200
    payload = response.json()

    dataset_root = models.Item.objects.get(id=payload["result"]["dataset_root"]["id"])
    titles = list(dataset_root.children().values_list("title", flat=True))
    assert sorted(titles) == ["Dev Team", "Project 2025"]

    project = dataset_root.children().get(title="Project 2025")
    assert project.children().filter(title="Sales report").exists()
    deleted_folder = project.children().get(title="I am deleted")
    assert deleted_folder.deleted_at is not None


@override_settings(LOAD_E2E_URLS=True, SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN])
def test_api_e2e_bootstrap_scenario_preview_fixture_set_creates_ready_files():
    """Preview fixture bootstrap should create ready-to-preview file items."""
    reload_urls()
    client = APIClient()

    response = client.post(
        "/api/v1.0/e2e/bootstrap-scenario/",
        {
            "kind": "preview_fixture_set",
            "run_id": "run-preview",
            "worker_id": "worker-3",
            "actor_key": "primary",
            "scenario_id": "preview-flow",
        },
        format="json",
        **_auth_headers(),
    )
    assert response.status_code == 200
    payload = response.json()

    file_titles = sorted(file["title"] for file in payload["result"]["files"])
    assert file_titles == [
        "fixture-heic.heic",
        "fixture-preview.pdf",
        "fixture-readme.txt",
    ]

    for file_payload in payload["result"]["files"]:
        item = models.Item.objects.get(id=file_payload["id"])
        assert item.upload_state == models.ItemUploadStateChoices.READY


@override_settings(
    LOAD_E2E_URLS=True,
    SERVER_TO_SERVER_API_TOKENS=[S2S_TOKEN],
)
def test_api_e2e_bootstrap_scenario_mount_subtree_creates_deterministic_tree(
    tmp_path,
):
    """Mount subtree bootstrap should create a namespaced localfs tree."""
    reload_urls()
    client = APIClient()
    mount_root = Path(tmp_path) / "mount-root"

    with override_settings(
        MOUNTS_REGISTRY=[
            {
                "mount_id": "e2e-local",
                "display_name": "E2E Local",
                "provider": "localfs",
                "enabled": True,
                "params": {"root_dir": str(mount_root)},
            }
        ]
    ):
        response = client.post(
            "/api/v1.0/e2e/bootstrap-scenario/",
            {
                "kind": "mount_subtree",
                "run_id": "run-mount",
                "worker_id": "worker-4",
                "actor_key": "primary",
                "scenario_id": "mount-flow",
                "mount_id": "e2e-local",
            },
            format="json",
            **_auth_headers(),
        )

    assert response.status_code == 200
    payload = response.json()
    root_path = payload["result"]["root_path"]
    root_fs_path = localfs._fs_path(  # pylint: disable=protected-access
        root=mount_root,
        normalized_path=root_path,
    )
    assert root_fs_path.exists()
    assert (root_fs_path / "inbox").exists()
    assert (root_fs_path / "outbox").exists()
    assert (root_fs_path / "README.txt").read_text() == (
        f"E2E mount subtree for {payload['scope']['scenario_slug']}\n"
    )
