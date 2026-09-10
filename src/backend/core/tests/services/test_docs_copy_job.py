"""A document subtree copy resumes through one identity per manifest entry."""

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from core import factories, models
from core.services.docs_jobs import enqueue
from core.services.docs_quota import initialize_usage
from core.services.storage_move_job import execute_move
from core.services.storage_transfer_location import resolve_location


@pytest.mark.django_db(transaction=True)
def test_copy_manifest_rejects_wrong_receipt_and_resumes(settings):
    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    settings.STORAGE_GOVERNANCE_ENABLED = False
    user = factories.UserFactory()
    backend = models.StorageBackend.objects.create(
        registry_id="docs-copy", family="s3", name="Storage", organization="local"
    )
    root = models.Item.objects.create(type="folder", title="Root", storage_backend=backend)
    space = models.StorageSpace.objects.create(
        backend=backend, name="Space", root_item=root, owner=user, explicit_access=True
    )
    models.Item.objects.filter(pk=root.pk).update(storage_space=space)
    models.StorageGrant.objects.create(space=space, user=user, writable=True, shareable=True)
    root.refresh_from_db()
    source = models.Item.objects.create_child(
        parent=root, type="docs", title="Parent", creator=user
    )
    models.DocsBinding.objects.create(item=source, state="active", applied_revision=1)
    models.ItemAccess.objects.create(item=source, user=user, role="owner")
    child = models.Item.objects.create_child(
        parent=source, type="docs", title="Child", creator=user
    )
    models.DocsBinding.objects.create(item=child, state="active", applied_revision=1)
    initialize_usage(source, size=3, version="source")
    initialize_usage(child, size=4, version="child")
    wrong_receipt = True

    def copy(_path, payload, **_kwargs):
        if wrong_receipt:
            return {"document_id": str(uuid4()), "state": "active"}
        binding = models.DocsBinding.objects.filter(document_id=payload["document_id"]).first()
        if not binding:
            parent = models.Item.objects.get(pk=payload["destination"])
            item = models.Item.objects.create_child(
                parent=parent, type="docs", title=payload["title"], creator=user
            )
            models.DocsBinding.objects.create(
                item=item,
                document_id=UUID(payload["document_id"]),
                state="active",
                applied_revision=1,
            )
            models.ItemAccess.objects.create(item=item, user=user, role="owner")
            initialize_usage(item, size=3 if parent.pk == root.pk else 4, version="copy")
        return {"document_id": payload["document_id"], "state": "active"}

    with (
        patch("core.services.docs_jobs.actor_context", return_value={"proof": {}}),
        patch("core.services.docs_jobs.resolve_actor", return_value=user),
        patch("core.services.docs_jobs.send", side_effect=copy),
        patch("core.services.storage_move_job.dispatch_move"),
    ):
        locations = (
            resolve_location(source.pk, user),
            resolve_location(root.pk, user, destination=True),
        )
        job = enqueue(user, *locations, mode="copy", request_key=uuid4())
        assert execute_move(job.pk) == "conflict"
        assert job.copy_entries.count() == 2
        assert not job.copy_entries.filter(done=True).exists()
        wrong_receipt = False
        enqueue(user, *locations, mode="copy", request_key=job.pk)
        for _ in range(3):
            if execute_move(job.pk) == "done":
                break
        job.refresh_from_db()
        assert job.state == "done"
        assert execute_move(job.pk) == "done"
    copied = models.Item.objects.get(pk=job.payload["result"])
    assert copied.parent().pk == root.pk
    assert copied.children().get().title == "Child"
    assert models.Item.objects.filter(type="docs").count() == 4
    assert models.StorageQuota.objects.get(key="instance:drive").used_bytes == 14


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("count", [20, 200])
def test_large_document_manifest_uses_batched_queries(settings, count, record_property):
    from django.db import connection  # noqa: PLC0415
    from django.test.utils import CaptureQueriesContext  # noqa: PLC0415

    from core.services.docs_jobs import _index  # noqa: PLC0415

    settings.DOCS_DRIVE_ENABLED = True
    settings.SUITE_IDENTITY_ENABLED = False
    user = factories.UserFactory()
    root = models.Item.objects.create(type="docs", title="Root", creator=user)
    models.DocsBinding.objects.create(item=root, state="active", applied_revision=1)
    models.ItemAccess.objects.create(item=root, user=user, role="owner")
    initialize_usage(root, size=0, version="root")
    children = []
    for number in range(count):
        key = uuid4()
        children.append(
            models.Item(
                id=key,
                path=f"{root.path}.{key}",
                type="docs",
                title=f"Child {number}",
                creator=user,
            )
        )
    models.Item.objects.bulk_create(children)
    models.DocsBinding.objects.bulk_create(
        [models.DocsBinding(item=item, state="active", applied_revision=1) for item in children]
    )
    models.StorageUsage.objects.bulk_create(
        [
            models.StorageUsage(
                key=f"fixture:{item.pk}", item=item, size=0, scope_keys=[], version="child"
            )
            for item in children
        ]
    )
    backend = models.StorageBackend.objects.create(
        registry_id="manifest", family="s3", organization="local", name="Storage"
    )
    space = models.StorageSpace.objects.create(backend=backend, owner=user, name="Space")
    job = models.StorageMoveJob.objects.create(
        actor=user,
        kind="docs_copy",
        space=space,
        source_path=str(root.pk),
        source_identity=str(root.pk),
        destination_path=str(root.pk),
        payload={},
    )
    import time  # noqa: PLC0415

    started = time.perf_counter()
    with CaptureQueriesContext(connection) as queries:
        _index(job, root)
    record_property("documents", count + 1)
    record_property("queries", len(queries))
    record_property("milliseconds", round((time.perf_counter() - started) * 1000, 2))
    assert len(queries) < 30
    parent = job.copy_entries.get(source_id=root.pk)
    assert job.copy_entries.filter(parent=parent).count() == count
    with CaptureQueriesContext(connection) as repeated:
        _index(job, root)
    assert len(repeated) == 0
    assert job.copy_entries.count() == count + 1


@pytest.mark.django_db(transaction=True)
def test_background_transfer_delegation_is_scoped_to_one_execution(settings):
    import time  # noqa: PLC0415

    from django.utils import timezone  # noqa: PLC0415

    from suite_identity.access import request_proofs  # noqa: PLC0415
    from suite_identity.document_transport import actor_context, resolve_actor  # noqa: PLC0415
    from suite_identity.models import Account  # noqa: PLC0415

    settings.SUITE_IDENTITY_ENABLED = True
    settings.SUITE_ORGANIZATION_ID = str(uuid4())
    settings.SUITE_OIDC_ISSUER = "https://idp.example.invalid"
    user = factories.UserFactory()
    account = Account.objects.create(
        user=user,
        active=True,
        principal_id=uuid4(),
        organization_id=settings.SUITE_ORGANIZATION_ID,
        checked_at=timezone.now(),
        policy_checked_at=timezone.now(),
        policy_allowed=True,
    )
    proof = {
        "principal_id": str(account.principal_id),
        "session_version": 0,
        "issuer": settings.SUITE_OIDC_ISSUER,
        "auth_until": time.time() + 60,
    }
    actor = {
        "principal": str(account.principal_id),
        "organization": settings.SUITE_ORGANIZATION_ID,
        "proof": proof,
    }
    token = request_proofs.set(None)
    try:
        with patch(
            "core.services.storage_move_job._execute_move",
            side_effect=lambda _job: actor_context(resolve_actor(actor)),
        ):
            assert execute_move(uuid4()) == actor
        assert request_proofs.get() is None
    finally:
        request_proofs.reset(token)
