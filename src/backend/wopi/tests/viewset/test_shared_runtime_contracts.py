"""Targeted non-regression tests for shared WOPI runtime helpers/mixins."""

from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from wopi.viewsets import (
    WopiFileContentRuntimeMixin,
    build_wopi_check_file_info_base,
    build_wopi_get_file_streaming_response,
    build_wopi_put_file_success_response,
    get_wopi_max_expected_size_preflight_response,
    get_wopi_put_override_preflight_response,
)


def test_build_wopi_check_file_info_base_keeps_shared_contract():
    """The shared CheckFileInfo builder should keep the common WOPI fields stable."""
    user = SimpleNamespace(id="user-1", is_anonymous=False, full_name="Jane Doe")

    assert build_wopi_check_file_info_base(
        base_file_name="hello.txt",
        owner_id="owner-1",
        user=user,
        size=123,
        version="v-1",
    ) == {
        "BaseFileName": "hello.txt",
        "OwnerId": "owner-1",
        "IsAnonymousUser": False,
        "UserFriendlyName": "Jane Doe",
        "Size": 123,
        "UserId": "user-1",
        "Version": "v-1",
        "UserCanPresent": False,
        "UserCanAttend": False,
        "UserCanNotWriteRelative": True,
        "SupportsUpdate": True,
        "SupportsCobalt": False,
        "SupportsContainers": False,
        "SupportsEcosystem": False,
        "SupportsGetFileWopiSrc": False,
        "SupportsGetLock": True,
        "SupportsLocks": True,
        "SupportsUserInfo": False,
    }


def test_build_wopi_check_file_info_base_handles_anonymous_user():
    """The shared CheckFileInfo builder should keep anonymous user semantics stable."""
    user = AnonymousUser()

    payload = build_wopi_check_file_info_base(
        base_file_name="hello.txt",
        owner_id="owner-1",
        user=user,
        size=123,
        version="v-1",
    )

    assert payload["IsAnonymousUser"] is True
    assert payload["UserFriendlyName"] is None
    assert payload["UserId"] == str(user.id)


def test_get_wopi_max_expected_size_preflight_response_keeps_contract():
    """The shared GetFile max-expected-size helper should keep its 412 contract."""
    assert (
        get_wopi_max_expected_size_preflight_response(
            actual_size=10,
            max_expected_size="9",
        ).status_code
        == 412
    )
    assert (
        get_wopi_max_expected_size_preflight_response(
            actual_size=10,
            max_expected_size="10",
        )
        is None
    )
    assert (
        get_wopi_max_expected_size_preflight_response(
            actual_size=None,
            max_expected_size="1",
        )
        is None
    )


def test_build_wopi_get_file_streaming_response_keeps_headers_and_body():
    """The shared GetFile response builder should keep WOPI headers and streamed bytes."""
    response = build_wopi_get_file_streaming_response(
        streaming_content=iter([b"abc", b"def"]),
        content_type="text/plain",
        version="version-1",
        size=6,
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain"
    assert response.headers["X-WOPI-ItemVersion"] == "version-1"
    assert response.headers["Content-Length"] == "6"
    assert b"".join(response.streaming_content) == b"abcdef"


def test_build_wopi_get_file_streaming_response_omits_unknown_content_length():
    """The shared GetFile response builder should omit Content-Length when size is unknown."""
    response = build_wopi_get_file_streaming_response(
        streaming_content=iter([b"abc"]),
        content_type="text/plain",
        version="version-1",
        size=None,
    )

    assert response.status_code == 200
    assert response.headers["X-WOPI-ItemVersion"] == "version-1"
    assert "Content-Length" not in response.headers


def test_get_wopi_put_override_preflight_response_keeps_contract():
    """The shared PutFile override helper should keep the existing 404 contract."""
    assert get_wopi_put_override_preflight_response(override=None).status_code == 404
    assert get_wopi_put_override_preflight_response(override="LOCK").status_code == 404
    assert get_wopi_put_override_preflight_response(override="PUT") is None


def test_build_wopi_put_file_success_response_keeps_contract():
    """The shared PutFile success helper should keep the item-version header."""
    response = build_wopi_put_file_success_response(version="version-1")

    assert response.status_code == 200
    assert response.headers["X-WOPI-ItemVersion"] == "version-1"


class _DummyFileContentViewSet(WopiFileContentRuntimeMixin, viewsets.ViewSet):
    """Minimal harness used to validate the shared contents dispatch mixin."""

    def _get_file_content(self, request, pk=None):
        return Response({"method": request.method, "pk": pk})

    def _put_file_content(self, request, pk=None):
        return Response({"method": request.method, "pk": pk})


def test_wopi_file_content_runtime_mixin_dispatches_get_and_post():
    """The shared contents dispatch mixin should route GET/POST without alteration."""
    factory = APIRequestFactory()
    viewset = _DummyFileContentViewSet()

    get_response = viewset.file_content(factory.get("/"), pk="alpha")
    post_response = viewset.file_content(factory.post("/"), pk="beta")

    assert get_response.status_code == 200
    assert get_response.data == {"method": "GET", "pk": "alpha"}
    assert post_response.status_code == 200
    assert post_response.data == {"method": "POST", "pk": "beta"}


def test_wopi_file_content_runtime_mixin_returns_405_for_other_methods():
    """The shared contents dispatch mixin should keep rejecting unsupported methods."""
    factory = APIRequestFactory()
    viewset = _DummyFileContentViewSet()

    response = viewset.file_content(factory.put("/"), pk="gamma")

    assert response.status_code == 405
