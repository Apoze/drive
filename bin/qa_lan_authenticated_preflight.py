#!/usr/bin/env python3
"""Validate the authenticated LAN browser QA bootstrap without leaking secrets."""

from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_LAN_HOST = "192.168.10.123"
DEFAULT_TIMEOUT_SECONDS = 60
BOOTSTRAP_PATH = "/api/v1.0/e2e/qa-browser-bootstrap/"


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Return 3xx responses to the caller instead of following them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        return None


def env(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    return value.rstrip("/") if value else default


def request_without_redirect(
    url: str,
    timeout: int,
) -> tuple[int, str | None, list[str], dict[str, str]]:
    opener = urllib.request.build_opener(NoRedirectHandler)
    request = urllib.request.Request(url, method="GET")

    try:
        with opener.open(request, timeout=timeout) as response:
            cookies = response.headers.get_all("Set-Cookie") or []
            return (
                response.status,
                response.headers.get("Location"),
                cookies,
                dict(response.headers),
            )
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            cookies = exc.headers.get_all("Set-Cookie") or []
            return exc.code, exc.headers.get("Location"), cookies, dict(exc.headers)
        raise


def same_origin(left: str, right: str) -> bool:
    left_origin = urllib.parse.urlparse(left)
    right_origin = urllib.parse.urlparse(right)
    return (
        left_origin.scheme == right_origin.scheme
        and left_origin.netloc == right_origin.netloc
    )


def main() -> int:
    lan_host = os.environ.get("QA_LAN_HOST", DEFAULT_LAN_HOST).strip()
    base_url = env("QA_LAN_BASE_URL", f"http://{lan_host}:3000")
    api_origin = env("QA_LAN_API_ORIGIN", f"http://{lan_host}:8071")
    timeout_seconds = int(
        os.environ.get("QA_LAN_AUTHENTICATED_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))
    )
    bootstrap_url = (
        os.environ.get("QA_LAN_BROWSER_BOOTSTRAP_URL", f"{api_origin}{BOOTSTRAP_PATH}")
        .strip()
        or f"{api_origin}{BOOTSTRAP_PATH}"
    )

    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"

    while time.monotonic() <= deadline:
        try:
            status, location, cookies, headers = request_without_redirect(
                bootstrap_url,
                timeout=5,
            )
        except Exception as exc:  # noqa: BLE001 - report sanitized retry reason.
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1)
            continue

        absolute_location = (
            urllib.parse.urljoin(bootstrap_url, location) if location else None
        )
        regular_url = headers.get("X-QA-Bootstrap-Regular-Url", "")
        mount_status = headers.get("X-QA-Bootstrap-Mount-Status", "unknown")
        mount_url = headers.get("X-QA-Bootstrap-Mount-Url", "")

        print(f"[qa-lan-authenticated] request: {bootstrap_url}")
        print(f"[qa-lan-authenticated] status: {status}")
        print(f"[qa-lan-authenticated] location: {absolute_location or '<missing>'}")
        print(
            "[qa-lan-authenticated] set-cookie: "
            + ("present" if cookies else "missing")
        )
        if regular_url:
            print(f"[qa-lan-authenticated] regular fixture URL: {regular_url}")
        print(f"[qa-lan-authenticated] mount fixture: {mount_status}")
        if mount_url:
            print(f"[qa-lan-authenticated] mount fixture URL: {mount_url}")
        print(
            "[qa-lan-authenticated] QA browser start URL: "
            f"{bootstrap_url}"
        )

        if status != 302:
            print("[qa-lan-authenticated] FAIL: expected HTTP 302", file=sys.stderr)
            return 1
        if not location or not absolute_location:
            print(
                "[qa-lan-authenticated] FAIL: missing Location header",
                file=sys.stderr,
            )
            return 1
        if not same_origin(absolute_location, base_url):
            expected_origin = urllib.parse.urlparse(base_url)
            actual_origin = urllib.parse.urlparse(absolute_location)
            print(
                "[qa-lan-authenticated] FAIL: expected redirect origin "
                f"{expected_origin.scheme}://{expected_origin.netloc}, got "
                f"{actual_origin.scheme}://{actual_origin.netloc}",
                file=sys.stderr,
            )
            return 1
        if not cookies:
            print(
                "[qa-lan-authenticated] FAIL: bootstrap did not set session cookies",
                file=sys.stderr,
            )
            return 1
        if not regular_url or not same_origin(regular_url, base_url):
            print(
                "[qa-lan-authenticated] FAIL: missing LAN regular fixture URL",
                file=sys.stderr,
            )
            return 1
        if mount_url and not same_origin(mount_url, base_url):
            print(
                "[qa-lan-authenticated] FAIL: mount fixture URL is not LAN-facing",
                file=sys.stderr,
            )
            return 1

        print(
            "[qa-lan-authenticated] PASS: bootstrap sets a dev session and "
            f"redirects to {base_url}"
        )
        return 0

    print(
        "[qa-lan-authenticated] FAIL: bootstrap endpoint did not become ready; "
        f"last sanitized error: {last_error}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
