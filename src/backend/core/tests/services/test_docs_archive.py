"""Mixed native folders retain files and export each live document into the ZIP."""

from contextlib import contextmanager
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth.models import AnonymousUser

import pytest
from suite_identity.document_transport import document_links

from core import factories, models
from core.services.docs_quota import initialize_usage
from core.services.storage_archive import archive_source, folder_download
from core.services.storage_inventory import scan_backend
from core.services.storage_transfer_location import resolve_location


@pytest.mark.django_db(transaction=True)
def test_mixed_native_archive_contains_files_and_document_tree(tmp_path, settings):  # noqa: PLR0915
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    user = factories.UserFactory()
    (tmp_path / "Folder").mkdir()
    (tmp_path / "Folder" / "file.txt").write_bytes(b"file")
    settings.MOUNTS_REGISTRY = [
        {
            "mount_id": "docs-archive",
            "provider": "localfs",
            "enabled": True,
            "params": {"root_dir": str(tmp_path)},
        }
    ]
    backend = models.StorageBackend.objects.create(
        registry_id="docs-archive", family="mount", name="Storage", organization="local"
    )
    space = models.StorageSpace.objects.create(
        backend=backend, owner=user, root_path="/", name="Space", explicit_access=True
    )
    models.StorageGrant.objects.create(space=space, user=user, writable=True, shareable=True)
    with patch("core.services.storage_inventory.refresh_policy"):
        scan_backend(backend.pk)
    folder = models.StorageResource.objects.get(namespace=backend.namespace, path="/Folder")
    document = models.Item.objects.create(type="docs", title="Document", creator=user)
    models.DocsBinding.objects.create(
        item=document, mounted_parent=folder, anchor_space=space, state="active", applied_revision=1
    )
    models.ItemAccess.objects.create(item=document, user=user, role="owner")
    child = models.Item.objects.create_child(
        parent=document, type="docs", title="Child", creator=user
    )
    models.DocsBinding.objects.create(item=child, state="active", applied_revision=1)
    initialize_usage(document, size=3, version="root")
    initialize_usage(child, size=4, version="child")
    source = resolve_location(folder.pk, user, space_id=space.pk)
    job = models.StorageMoveJob.objects.create(
        actor=user,
        kind="file_copy",
        space=space,
        source_path=str(folder.pk),
        source_identity=str(folder.pk),
        destination_path=str(folder.pk),
        payload={"archive_sources": [source.descriptor()], "name": "archive.zip"},
    )
    from core.services.storage_quota import StorageWriteConflict  # noqa: PLC0415
    from core.services.storage_transfer_impact import transfer_impact  # noqa: PLC0415

    with pytest.raises(StorageWriteConflict, match="nested documents"):
        transfer_impact([source, resolve_location(child.pk, user)], source, user, "copy")
    exported = []
    revisions = {
        str(binding.document_id): binding.revision for binding in models.DocsBinding.objects.all()
    }

    @contextmanager
    def pdf(data, *, actor, limit):
        assert actor == {"principal": str(user.pk)} and limit > 100
        assert data["revision"] == revisions[data["document_id"]]
        exported.append(data["document_id"])
        with BytesIO(b"%PDF-1.4\n" + data["document_id"].encode() + b"\n%%EOF") as stream:
            yield stream

    with (
        patch(
            "suite_identity.document_transport.actor_context",
            return_value={"principal": str(user.pk)},
        ),
        patch("suite_identity.document_transport.pdf_stream", side_effect=pdf),
        archive_source(job) as result,
        ZipFile(result) as archive,
    ):
        assert set(archive.namelist()) == {
            "Folder/",
            "Folder/file.txt",
            "Folder/Document.pdf",
            "Folder/Document/Child.pdf",
        }
        assert archive.read("Folder/file.txt") == b"file"
        assert archive.read("Folder/Document.pdf").startswith(b"%PDF-")
        assert archive.read("Folder/Document/Child.pdf").startswith(b"%PDF-")
    assert exported == [str(document.docs_binding.document_id), str(child.docs_binding.document_id)]
    with (
        patch(
            "suite_identity.document_transport.actor_context",
            return_value={"principal": str(user.pk)},
        ),
        patch("suite_identity.document_transport.pdf_stream", side_effect=pdf),
    ):
        response = folder_download(folder, user, space_id=space.pk)
        with ZipFile(BytesIO(b"".join(response.streaming_content))) as archive:
            assert set(archive.namelist()) == {"file.txt", "Document.pdf", "Document/Child.pdf"}
            assert archive.read("file.txt") == b"file"
            assert archive.read("Document.pdf").startswith(b"%PDF-")
    assert models.Item.objects.filter(type="docs").count() == 2
    from core.services.docs_links import append_mounted_documents  # noqa: PLC0415

    settings.DOCS_PUBLIC_URL = "https://docs.example.test"
    link = models.MountShareLink.objects.create(
        token="synthetic-mount-bearer",
        created_by=user,
        resource=folder,
        mount_id=str(space.pk),
        normalized_path="/Folder",
    )
    previous = document_links.set(
        {
            str(document.docs_binding.document_id): {
                "kind": "mount",
                "token": link.token,
            }
        }
    )
    try:
        assert document.get_abilities(AnonymousUser())["retrieve"]
        assert child.get_abilities(AnonymousUser())["retrieve"]
        page, paginator = [], SimpleNamespace(count=1, limit=1, offset=1)
        append_mounted_documents(page, paginator, source.mount, "/Folder", link.token)
        assert paginator.count == 2
        assert len(page) == 1 and page[0]["entry_type"] == "docs"
        assert page[0]["url_docs"].startswith("https://docs.example.test/docs/open/#")
        models.StorageGrant.objects.filter(space=space).update(shareable=False)
        assert not document.get_abilities(AnonymousUser())["retrieve"]
    finally:
        document_links.reset(previous)
