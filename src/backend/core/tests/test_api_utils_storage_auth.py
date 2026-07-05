"""Direct contract tests for object-storage auth helpers."""
# pylint: disable=missing-function-docstring,missing-class-docstring,invalid-name

from __future__ import annotations

from types import SimpleNamespace

import botocore

from core.api import utils


class _FakeUnsignedClient:
    def __init__(self, *, expected_bucket: str, expected_key: str, url: str):
        self.expected_bucket = expected_bucket
        self.expected_key = expected_key
        self.url = url
        self.calls: list[tuple[str, int, dict]] = []

    def generate_presigned_url(self, operation_name, ExpiresIn, Params):
        self.calls.append((operation_name, ExpiresIn, Params))
        assert operation_name == "get_object"
        assert ExpiresIn == 0
        assert Params == {"Bucket": self.expected_bucket, "Key": self.expected_key}
        return self.url


class _FakeStorageClient:
    def __init__(self, *, region_name: str = "eu-west-3"):
        self.meta = SimpleNamespace(region_name=region_name)
        self._request_signer = SimpleNamespace(
            _credentials=SimpleNamespace(get_frozen_credentials=lambda: "frozen-creds")
        )
        self.generate_presigned_url_calls: list[dict] = []
        self.head_object_calls: list[dict] = []

    def generate_presigned_url(self, **kwargs):
        self.generate_presigned_url_calls.append(kwargs)
        return "policy-url"

    def head_object(self, **kwargs):
        self.head_object_calls.append(kwargs)
        return {"ETag": '"abc123"'}


class _FakeAuth:
    instances: list["_FakeAuth"] = []

    def __init__(self, credentials, service, region):
        self.credentials = credentials
        self.service = service
        self.region = region
        self.signed_requests = []
        self.__class__.instances.append(self)

    def add_auth(self, request):
        request.headers["Authorization"] = "signed-auth"
        request.headers["X-Test-Region"] = self.region
        self.signed_requests.append(request)


def test_generate_s3_authorization_headers_builds_signed_get_request(monkeypatch):
    unsigned_client = _FakeUnsignedClient(
        expected_bucket="drive-media-storage",
        expected_key="item/demo/report.pdf",
        url="http://s3.example.test/drive-media-storage/item/demo/report.pdf",
    )
    storage_client = _FakeStorageClient(region_name="ap-south-1")
    fake_storage = SimpleNamespace(
        bucket_name="drive-media-storage",
        unsigned_connection=SimpleNamespace(meta=SimpleNamespace(client=unsigned_client)),
        connection=SimpleNamespace(meta=SimpleNamespace(client=storage_client)),
    )
    monkeypatch.setattr(utils, "default_storage", fake_storage)
    monkeypatch.setattr(utils.botocore.auth, "S3SigV4Auth", _FakeAuth)
    _FakeAuth.instances.clear()

    request = utils.generate_s3_authorization_headers("item/demo/report.pdf")

    assert request.method.lower() == "get"
    assert request.url == "http://s3.example.test/drive-media-storage/item/demo/report.pdf"
    assert request.headers["Authorization"] == "signed-auth"
    assert request.headers["X-Test-Region"] == "ap-south-1"
    assert len(_FakeAuth.instances) == 1
    auth = _FakeAuth.instances[0]
    assert auth.credentials == "frozen-creds"
    assert auth.service == "s3"
    assert auth.region == "ap-south-1"
    assert auth.signed_requests == [request]


def test_generate_upload_policy_uses_domain_replace_client_when_configured(monkeypatch, settings):
    settings.AWS_S3_DOMAIN_REPLACE = "http://s3-replaced.example.test"
    settings.AWS_S3_ACCESS_KEY_ID = "access-key"
    settings.AWS_S3_SECRET_ACCESS_KEY = "secret-key"
    settings.AWS_S3_REGION_NAME = "eu-west-1"
    settings.AWS_S3_SIGNATURE_VERSION = "s3v4"
    settings.AWS_S3_UPLOAD_POLICY_EXPIRATION = 321

    storage_client = _FakeStorageClient()
    fake_storage = SimpleNamespace(
        bucket_name="drive-media-storage",
        connection=SimpleNamespace(meta=SimpleNamespace(client=storage_client)),
    )
    monkeypatch.setattr(utils, "default_storage", fake_storage)

    captured = {}

    def _fake_boto3_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured["kwargs"] = kwargs
        return storage_client

    monkeypatch.setattr(utils.boto3, "client", _fake_boto3_client)

    item = SimpleNamespace(key_base="item/123", filename="hello.txt")

    policy = utils.generate_upload_policy(item)

    assert policy == "policy-url"
    assert captured["service_name"] == "s3"
    assert captured["kwargs"]["aws_access_key_id"] == "access-key"
    assert captured["kwargs"]["aws_secret_access_key"] == "secret-key"
    assert captured["kwargs"]["endpoint_url"] == "http://s3-replaced.example.test"
    assert isinstance(captured["kwargs"]["config"], botocore.client.Config)
    assert captured["kwargs"]["config"].region_name == "eu-west-1"
    assert captured["kwargs"]["config"].signature_version == "s3v4"
    assert storage_client.generate_presigned_url_calls == [
        {
            "ClientMethod": "put_object",
            "Params": {
                "Bucket": "drive-media-storage",
                "Key": "item/123/hello.txt",
                "ACL": "private",
            },
            "ExpiresIn": 321,
        }
    ]


def test_generate_upload_policy_uses_default_storage_client_without_domain_replace(
    monkeypatch, settings
):
    settings.AWS_S3_DOMAIN_REPLACE = None
    settings.AWS_S3_UPLOAD_POLICY_EXPIRATION = 111

    storage_client = _FakeStorageClient()
    fake_storage = SimpleNamespace(
        bucket_name="drive-media-storage",
        connection=SimpleNamespace(meta=SimpleNamespace(client=storage_client)),
    )
    monkeypatch.setattr(utils, "default_storage", fake_storage)

    item = SimpleNamespace(key_base="item/456", filename="draft.docx")

    policy = utils.generate_upload_policy(item)

    assert policy == "policy-url"
    assert storage_client.generate_presigned_url_calls == [
        {
            "ClientMethod": "put_object",
            "Params": {
                "Bucket": "drive-media-storage",
                "Key": "item/456/draft.docx",
                "ACL": "private",
            },
            "ExpiresIn": 111,
        }
    ]


def test_get_item_file_head_object_uses_storage_bucket_and_item_key(monkeypatch):
    storage_client = _FakeStorageClient()
    fake_storage = SimpleNamespace(
        bucket_name="drive-media-storage",
        connection=SimpleNamespace(meta=SimpleNamespace(client=storage_client)),
    )
    monkeypatch.setattr(utils, "default_storage", fake_storage)

    item = SimpleNamespace(file_key="item/789/final.pdf")

    payload = utils.get_item_file_head_object(item)

    assert payload == {"ETag": '"abc123"'}
    assert storage_client.head_object_calls == [
        {
            "Bucket": "drive-media-storage",
            "Key": "item/789/final.pdf",
        }
    ]
