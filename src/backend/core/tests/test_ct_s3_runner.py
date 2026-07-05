"""Direct tests for CT-S3 runner helper contracts."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock
from uuid import NAMESPACE_DNS, uuid5

from django.test.utils import override_settings

from core.ct_s3 import constants
from core.ct_s3.http_client import HttpClientError
from core.ct_s3.runner import (
    _connect_url_for_presigned_url,
    _evidence_base,
    _failure_from_http_client_error,
    _make_key,
    _presigned_put_url_for_key,
    _safe_request_id,
    _signed_get_headers_for_key,
    _stable_uuid,
    dumps_json,
    render_human_report,
    resolve_provider_profile,
    run_ct_s3,
)
from core.ct_s3.types import ProviderProfile, RunnerOptions


def test_stable_uuid_and_make_key_are_deterministic():
    expected_uuid = uuid5(NAMESPACE_DNS, "ct-s3:run-1:CT-S3-001")

    assert _stable_uuid("run-1", "CT-S3-001") == expected_uuid
    assert _make_key("run-1", "CT-S3-001", "hello.txt") == f"item/{expected_uuid}/hello.txt"


@override_settings(
    AWS_S3_ENDPOINT_URL="http://internal-s3:8333",
    AWS_S3_DOMAIN_REPLACE="https://public-s3.example.test",
)
def test_resolve_provider_profile_reads_settings_and_storage(monkeypatch):
    monkeypatch.setattr(
        "core.ct_s3.runner.default_storage",
        SimpleNamespace(bucket_name="bucket-name"),
    )

    assert resolve_provider_profile("seaweedfs-s3") == ProviderProfile(
        profile_id="seaweedfs-s3",
        bucket_name="bucket-name",
        internal_endpoint_url="http://internal-s3:8333",
        external_signed_base_url="https://public-s3.example.test",
    )


def test_safe_request_id_prefers_known_headers():
    assert _safe_request_id({"x-amz-request-id": "amz"}) == "amz"
    assert _safe_request_id({"x-request-id": "req"}) == "req"
    assert _safe_request_id({"x-amzn-requestid": "amzn"}) == "amzn"
    assert _safe_request_id({"other": "x"}) is None


def test_evidence_base_hashes_profile_values_without_leaking_raw_values():
    profile = ProviderProfile(
        profile_id="seaweedfs-s3",
        bucket_name="bucket",
        internal_endpoint_url="http://internal-s3:8333",
        external_signed_base_url="https://public-s3.example.test",
    )

    evidence = _evidence_base(profile)

    assert evidence["profile_id"] == "seaweedfs-s3"
    assert evidence["bucket_hash"] != "bucket"
    assert evidence["internal_endpoint_hash"] != "http://internal-s3:8333"
    assert evidence["external_signed_base_hash"] != "https://public-s3.example.test"


def test_failure_from_http_client_error_maps_known_and_unknown_kinds():
    assert _failure_from_http_client_error(HttpClientError("connect_timeout")) == (
        "s3.net.connect_timeout",
        "Check S3 connectivity from the runner.",
    )
    assert _failure_from_http_client_error(HttpClientError("connect_refused")) == (
        "s3.net.connect_refused",
        "Check S3 endpoint is up and reachable.",
    )
    assert _failure_from_http_client_error(HttpClientError("dns_failure")) == (
        "s3.net.dns_failure",
        "Check S3 endpoint DNS/host resolution.",
    )
    assert _failure_from_http_client_error(HttpClientError("other")) == (
        "s3.net.connect_timeout",
        "Check S3 connectivity from the runner.",
    )


def test_signed_get_headers_for_key_adds_host_header(monkeypatch):
    signed_request = SimpleNamespace(
        url="http://internal-s3:8333/bucket/key",
        headers={"Authorization": "sigv4"},
    )
    monkeypatch.setattr(
        "core.ct_s3.runner.api_utils.generate_s3_authorization_headers",
        lambda key: signed_request,
    )

    url, headers = _signed_get_headers_for_key("bucket/key")

    assert url == "http://internal-s3:8333/bucket/key"
    assert headers["Authorization"] == "sigv4"
    assert headers["Host"] == "internal-s3:8333"


def test_presigned_put_url_for_key_uses_key_base_and_filename(monkeypatch):
    captured = {}

    def fake_generate_upload_policy(item):
        captured["key_base"] = item.key_base
        captured["filename"] = item.filename
        return "https://signed.example.test/upload"

    monkeypatch.setattr(
        "core.ct_s3.runner.api_utils.generate_upload_policy",
        fake_generate_upload_policy,
    )

    assert (
        _presigned_put_url_for_key("item/abc", "file.txt") == "https://signed.example.test/upload"
    )
    assert captured == {"key_base": "item/abc", "filename": "file.txt"}


def test_connect_url_for_presigned_url_reuses_connect_host_and_signed_path_query():
    connect_url, signed_host = _connect_url_for_presigned_url(
        "http://internal-s3:8333",
        "https://public-s3.example.test/bucket/key?X-Amz=1&foo=bar",
    )

    assert connect_url == "http://internal-s3:8333/bucket/key?X-Amz=1&foo=bar"
    assert signed_host == "public-s3.example.test"


def test_render_human_report_and_dumps_json_are_deterministic():
    report = {
        "run_id": "run-1",
        "gate_id": "s3.contracts.seaweedfs-s3",
        "overall_ok": False,
        "results": [
            {
                "check_id": "CT-S3-001",
                "audience": constants.AUDIENCE_INTERNAL_PROXY,
                "ok": False,
                "title": "Signed GET",
                "failure_class": "s3.http.signed_get_failed",
                "next_action_hint": "Check config.",
                "evidence": {},
            }
        ],
    }

    human = render_human_report(report)
    payload = dumps_json(report)

    assert "# CT-S3 Report" in human
    assert "`CT-S3-001` `INTERNAL_PROXY`: FAIL" in human
    assert '"gate_id": "s3.contracts.seaweedfs-s3"' in payload
    assert payload.endswith("\n")
    assert json.loads(payload)["run_id"] == "run-1"


def test_run_ct_s3_missing_envs_returns_sorted_failing_report(monkeypatch):
    monkeypatch.setattr(
        "core.ct_s3.runner.resolve_provider_profile",
        lambda _profile_id: ProviderProfile(
            profile_id="seaweedfs-s3",
            bucket_name="bucket",
            internal_endpoint_url="",
            external_signed_base_url=None,
        ),
    )
    monkeypatch.setattr(
        "core.ct_s3.runner.default_storage",
        SimpleNamespace(connection=SimpleNamespace(meta=SimpleNamespace(client=mock.Mock()))),
    )

    report = run_ct_s3(
        profile_id="seaweedfs-s3",
        run_id="run-fixed",
        options=RunnerOptions(),
    )

    assert report["schema_version"] == 1
    assert report["run_id"] == "run-fixed"
    assert report["gate_id"] == "s3.contracts.seaweedfs-s3"
    assert report["overall_ok"] is False
    assert report["results"] == sorted(
        report["results"],
        key=lambda result: (result["check_id"], result["audience"]),
    )
    assert all(result["failure_class"] == "s3.config.missing_env" for result in report["results"])
