"""Tests for mount browser-stream access helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

from uuid import uuid4

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache

import pytest

from core import factories
from core.services.mount_stream_access import (
    AccessUserMountStream,
    MountStreamAccessInvalidDataError,
    MountStreamAccessNotAllowed,
    MountStreamAccessNotFoundError,
    MountStreamAccessService,
    NewMountStreamAccess,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_mount_stream_cache():
    cache.clear()
    yield
    cache.clear()


def _access_dict(*, user_id: str | None) -> dict:
    return {
        "mount_id": "alpha-mount",
        "normalized_path": "/folder/report.pdf",
        "user": user_id,
        "version": "v1",
        "filename": "report.pdf",
        "content_type": "application/pdf",
        "content_length": 42,
        "disposition": "inline",
        "purpose": "preview",
        "supports_range": True,
    }


def test_access_user_mount_stream_to_dict_and_from_dict_round_trip():
    user = factories.UserFactory()
    access = AccessUserMountStream(
        mount_id="alpha-mount",
        normalized_path="/folder/report.pdf",
        user=user,
        version="v1",
        filename="report.pdf",
        content_type="application/pdf",
        content_length=42,
        disposition="inline",
        purpose="preview",
        supports_range=True,
    )

    serialized = access.to_dict()
    restored = AccessUserMountStream.from_dict(serialized)

    assert serialized["user"] == str(user.id)
    assert restored.mount_id == "alpha-mount"
    assert restored.normalized_path == "/folder/report.pdf"
    assert restored.user == user
    assert restored.version == "v1"
    assert restored.supports_range is True


def test_access_user_mount_stream_from_dict_normalizes_path():
    user = factories.UserFactory()

    restored = AccessUserMountStream.from_dict(
        {
            **_access_dict(user_id=str(user.id)),
            "normalized_path": "///folder/./nested//report.pdf",
        }
    )

    assert restored.normalized_path == "/folder/nested/report.pdf"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.pop("mount_id"),
        lambda payload: payload.__setitem__("normalized_path", "/../secret.txt"),
        lambda payload: payload.__setitem__("version", ""),
        lambda payload: payload.__setitem__("disposition", "download"),
        lambda payload: payload.__setitem__("purpose", "edit"),
        lambda payload: payload.__setitem__("content_length", -1),
        lambda payload: payload.__setitem__("supports_range", "yes"),
    ],
)
def test_access_user_mount_stream_from_dict_rejects_invalid_data(mutation):
    user = factories.UserFactory()
    payload = _access_dict(user_id=str(user.id))

    mutation(payload)

    with pytest.raises(MountStreamAccessInvalidDataError):
        AccessUserMountStream.from_dict(payload)


def test_access_user_mount_stream_from_dict_raises_not_found_when_user_is_missing():
    with pytest.raises(MountStreamAccessNotFoundError):
        AccessUserMountStream.from_dict(_access_dict(user_id=str(uuid4())))


def test_mount_stream_access_service_rejects_anonymous_user():
    service = MountStreamAccessService()

    with pytest.raises(MountStreamAccessNotAllowed):
        service.insert_new_access(
            NewMountStreamAccess(
                mount_id="alpha-mount",
                normalized_path="/folder/report.pdf",
                user=AnonymousUser(),
                version="v1",
                filename="report.pdf",
                content_type="application/pdf",
                content_length=42,
                disposition="inline",
                purpose="preview",
                supports_range=True,
            )
        )


def test_mount_stream_access_service_stores_normalized_payload_and_reads_cache_hit(monkeypatch):
    user = factories.UserFactory()
    service = MountStreamAccessService()
    monkeypatch.setattr(service, "generate_token", lambda: "stream-token")

    token, expires_at = service.insert_new_access(
        NewMountStreamAccess(
            mount_id=" alpha-mount ",
            normalized_path=" //folder/./report.pdf ",
            user=user,
            version="v1",
            filename="report.pdf",
            content_type="application/pdf",
            content_length=42,
            disposition="inline",
            purpose="preview",
            supports_range=True,
        )
    )

    cached = cache.get(token)
    resolved = service.get_access_user_mount_stream(token)

    assert token == "stream-token"
    assert isinstance(expires_at, int)
    assert cached["mount_id"] == "alpha-mount"
    assert cached["normalized_path"] == "/folder/report.pdf"
    assert resolved.user == user
    assert resolved.normalized_path == "/folder/report.pdf"


def test_mount_stream_access_service_raises_not_found_on_cache_miss():
    service = MountStreamAccessService()

    with pytest.raises(MountStreamAccessNotFoundError):
        service.get_access_user_mount_stream("missing-token")
