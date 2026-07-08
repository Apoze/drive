"""
Test the recursive folder export endpoint.
"""

import io
import zipfile

import pytest
from rest_framework.test import APIClient

from core import factories, models
from core.tests.conftest import TEAM, USER, VIA

pytestmark = pytest.mark.django_db


def _zip_payload(response):
    return b"".join(response.streaming_content)


def _zip_names(response):
    """Return the filenames contained in a streamed zip response."""
    with zipfile.ZipFile(io.BytesIO(_zip_payload(response))) as archive:
        return archive.namelist()


def _zip_content(response, name):
    """Return the bytes stored at `name` in a streamed zip response."""
    with zipfile.ZipFile(io.BytesIO(_zip_payload(response))) as archive:
        with archive.open(name) as fh:
            return fh.read()


def test_api_items_export_anonymous_public():
    """Anonymous users can export a public folder."""
    folder = factories.ItemFactory(
        link_reach="public",
        type=models.ItemTypeChoices.FOLDER,
        title="public-folder",
    )
    factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"hello",
        upload_bytes__filename="hello.txt",
    )

    response = APIClient().get(f"/api/v1.0/items/{folder.pk}/export/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/zip"
    assert "public-folder.zip" in response["Content-Disposition"]
    assert _zip_names(response) == ["hello.txt"]


@pytest.mark.parametrize("reach", ["authenticated", "restricted"])
def test_api_items_export_anonymous_authenticated_or_restricted(reach):
    """Anonymous users cannot export folders that are not public."""
    folder = factories.ItemFactory(link_reach=reach, type=models.ItemTypeChoices.FOLDER)

    response = APIClient().get(f"/api/v1.0/items/{folder.pk}/export/")

    assert response.status_code == 401


def test_api_items_export_authenticated_restricted():
    """Authenticated users without access cannot export a restricted folder."""
    folder = factories.ItemFactory(link_reach="restricted", type=models.ItemTypeChoices.FOLDER)
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    response = client.get(f"/api/v1.0/items/{folder.pk}/export/")

    assert response.status_code == 403


@pytest.mark.parametrize("via", VIA)
def test_api_items_export_related(via, mock_user_teams):
    """Users with direct or team access can export a folder."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    folder = factories.ItemFactory(type=models.ItemTypeChoices.FOLDER, title="my-folder")
    factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"# readme",
        upload_bytes__filename="readme.md",
    )

    if via == USER:
        factories.UserItemAccessFactory(item=folder, user=user)
    elif via == TEAM:
        mock_user_teams.return_value = ["lasuite", "unknown"]
        factories.TeamItemAccessFactory(item=folder, team="lasuite")

    response = client.get(f"/api/v1.0/items/{folder.pk}/export/")

    assert response.status_code == 200
    assert _zip_content(response, "readme.md") == b"# readme"


def test_api_items_export_item_not_a_folder():
    """Files cannot be exported through the folder export endpoint."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    item = factories.ItemFactory(
        type=models.ItemTypeChoices.FILE,
        update_upload_state=models.ItemUploadStateChoices.READY,
        users=[(user, models.RoleChoices.OWNER)],
    )

    response = client.get(f"/api/v1.0/items/{item.pk}/export/")

    assert response.status_code == 403


def test_api_items_export_preserves_hierarchy():
    """Files keep their relative paths in the exported zip."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    root = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
        title="root",
        users=[(user, models.RoleChoices.OWNER)],
    )
    sub = factories.ItemFactory(parent=root, type=models.ItemTypeChoices.FOLDER, title="sub")
    factories.ItemFactory(
        parent=root,
        type=models.ItemTypeChoices.FILE,
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"top",
        upload_bytes__filename="top.txt",
    )
    factories.ItemFactory(
        parent=sub,
        type=models.ItemTypeChoices.FILE,
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"nested",
        upload_bytes__filename="nested.txt",
    )

    response = client.get(f"/api/v1.0/items/{root.pk}/export/")

    assert response.status_code == 200
    assert sorted(_zip_names(response)) == ["sub/", "sub/nested.txt", "top.txt"]


def test_api_items_export_sanitizes_zip_paths():
    """Archive names are sanitized so item names cannot produce zip-slip paths."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    root = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
        title="root",
        users=[(user, models.RoleChoices.OWNER)],
    )
    sub = factories.ItemFactory(parent=root, type=models.ItemTypeChoices.FOLDER, title="../sub")
    factories.ItemFactory(
        parent=sub,
        type=models.ItemTypeChoices.FILE,
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"safe",
        upload_bytes__filename="unsafe/name.txt",
    )

    response = client.get(f"/api/v1.0/items/{root.pk}/export/")

    assert response.status_code == 200
    assert _zip_names(response) == ["_sub/", "_sub/unsafe_name.txt"]


def test_api_items_export_skips_soft_deleted_descendants():
    """Soft-deleted descendants must not appear in the exported zip."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, models.RoleChoices.OWNER)],
    )
    keep = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"keep",
        upload_bytes__filename="keep.txt",
    )
    drop = factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"drop",
        upload_bytes__filename="drop.txt",
    )
    drop.soft_delete()

    response = client.get(f"/api/v1.0/items/{folder.pk}/export/")

    assert response.status_code == 200
    assert _zip_names(response) == [keep.filename]


@pytest.mark.parametrize(
    "upload_state",
    [
        state
        for state in models.ItemUploadStateChoices.values
        if state != models.ItemUploadStateChoices.READY
    ],
)
def test_api_items_export_skips_non_uploaded_files(upload_state):
    """Files that are not ready are excluded from the exported zip."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, models.RoleChoices.OWNER)],
    )
    factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        update_upload_state=models.ItemUploadStateChoices.READY,
        upload_bytes=b"ready",
        upload_bytes__filename="ready.txt",
    )
    factories.ItemFactory(
        parent=folder,
        type=models.ItemTypeChoices.FILE,
        filename="busy.txt",
        upload_state=upload_state,
    )

    response = client.get(f"/api/v1.0/items/{folder.pk}/export/")

    assert response.status_code == 200
    assert _zip_names(response) == ["ready.txt"]


def test_api_items_export_empty_folder():
    """Exporting an empty folder returns an empty zip archive."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
        users=[(user, models.RoleChoices.OWNER)],
    )

    response = client.get(f"/api/v1.0/items/{folder.pk}/export/")

    assert response.status_code == 200
    assert _zip_names(response) == []


def test_api_items_export_includes_empty_subfolders():
    """Subfolders must appear as directory entries in the zip."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    root = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
        title="root",
        users=[(user, models.RoleChoices.OWNER)],
    )
    sub = factories.ItemFactory(parent=root, type=models.ItemTypeChoices.FOLDER, title="sub")
    factories.ItemFactory(parent=sub, type=models.ItemTypeChoices.FOLDER, title="nested")

    response = client.get(f"/api/v1.0/items/{root.pk}/export/")

    assert response.status_code == 200
    assert sorted(_zip_names(response)) == ["sub/", "sub/nested/"]


def test_api_items_export_filename_with_spaces():
    """The Content-Disposition header must encode spaces safely."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    folder = factories.ItemFactory(
        type=models.ItemTypeChoices.FOLDER,
        title="ete 2026",
        users=[(user, models.RoleChoices.OWNER)],
    )

    response = client.get(f"/api/v1.0/items/{folder.pk}/export/")

    assert response.status_code == 200
    assert response["Content-Disposition"] == "attachment; filename*=UTF-8''ete%202026.zip"
