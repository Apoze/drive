#!/usr/bin/env python3
"""Validate that LAN browser QA receives a LAN-resolvable auth redirect."""

from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_LAN_HOST = "192.168.10.123"
DEFAULT_TIMEOUT_SECONDS = 60


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Return 3xx responses to the caller instead of following them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        return None


def env(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    return value.rstrip("/") if value else default


def sanitize_url(raw_url: str | None) -> str:
    if not raw_url:
        return "<missing>"

    parsed = urllib.parse.urlparse(raw_url)
    safe = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, "", "", "")
    )
    if parsed.query:
        safe += "?***"
    if parsed.fragment:
        safe += "#***"
    return safe


def request_without_redirect(url: str, timeout: int) -> tuple[int, str | None]:
    opener = urllib.request.build_opener(NoRedirectHandler)
    request = urllib.request.Request(url, method="GET")

    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.headers.get("Location")
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            return exc.code, exc.headers.get("Location")
        raise


def main() -> int:
    lan_host = os.environ.get("QA_LAN_HOST", DEFAULT_LAN_HOST).strip()
    base_url = env("QA_LAN_BASE_URL", f"http://{lan_host}:3000")
    api_origin = env("QA_LAN_API_ORIGIN", f"http://{lan_host}:8071")
    expected_edge_origin = env(
        "QA_LAN_EDGE_ORIGIN",
        f"http://{lan_host}:8083",
    )
    return_to = os.environ.get("QA_LAN_RETURN_TO", f"{base_url}/").strip()
    timeout_seconds = int(
        os.environ.get("QA_LAN_AUTH_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))
    )

    authenticate_url = (
        f"{api_origin}/api/v1.0/authenticate/?"
        + urllib.parse.urlencode({"silent": "false", "returnTo": return_to})
    )
    expected_origin = urllib.parse.urlparse(expected_edge_origin)

    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"

    while time.monotonic() <= deadline:
        try:
            status, location = request_without_redirect(authenticate_url, timeout=5)
        except Exception as exc:  # noqa: BLE001 - report sanitized retry reason.
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1)
            continue

        absolute_location = (
            urllib.parse.urljoin(authenticate_url, location) if location else None
        )
        actual_origin = urllib.parse.urlparse(absolute_location or "")

        print(f"[qa-lan-auth] request: {sanitize_url(authenticate_url)}")
        print(f"[qa-lan-auth] status: {status}")
        print(f"[qa-lan-auth] location: {sanitize_url(absolute_location)}")

        if status != 302:
            print("[qa-lan-auth] FAIL: expected HTTP 302", file=sys.stderr)
            return 1
        if not location:
            print("[qa-lan-auth] FAIL: missing Location header", file=sys.stderr)
            return 1
        if (
            actual_origin.scheme == expected_origin.scheme
            and actual_origin.netloc == expected_origin.netloc
        ):
            print(
                "[qa-lan-auth] PASS: redirect origin is "
                f"{expected_origin.scheme}://{expected_origin.netloc}"
            )
            return 0

        print(
            "[qa-lan-auth] FAIL: expected redirect origin "
            f"{expected_origin.scheme}://{expected_origin.netloc}, got "
            f"{actual_origin.scheme}://{actual_origin.netloc}",
            file=sys.stderr,
        )
        return 1

    print(
        "[qa-lan-auth] FAIL: authenticate endpoint did not become ready; "
        f"last sanitized error: {last_error}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
