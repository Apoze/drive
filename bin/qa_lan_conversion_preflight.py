#!/usr/bin/env python3
"""Validate the operator-enabled conversion LAN QA bootstrap safely."""

from __future__ import annotations

import http.cookies
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_LAN_HOST = "192.168.10.123"
DEFAULT_TIMEOUT_SECONDS = 60
BOOTSTRAP_PATH = "/api/v1.0/e2e/qa-browser-bootstrap/?include_conversion=1"


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
    headers: dict[str, str] | None = None,
) -> tuple[int, str | None, list[str], dict[str, str], bytes]:
    opener = urllib.request.build_opener(NoRedirectHandler)
    request = urllib.request.Request(url, headers=headers or {}, method="GET")

    try:
        with opener.open(request, timeout=timeout) as response:
            cookies = response.headers.get_all("Set-Cookie") or []
            return (
                response.status,
                response.headers.get("Location"),
                cookies,
                dict(response.headers),
                response.read(),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read()
        if 300 <= exc.code < 400:
            cookies = exc.headers.get_all("Set-Cookie") or []
            return exc.code, exc.headers.get("Location"), cookies, dict(exc.headers), body
        raise


def same_origin(left: str, right: str) -> bool:
    left_origin = urllib.parse.urlparse(left)
    right_origin = urllib.parse.urlparse(right)
    return (
        left_origin.scheme == right_origin.scheme
        and left_origin.netloc == right_origin.netloc
    )


def cookie_header(set_cookie_headers: list[str]) -> str:
    jar = http.cookies.SimpleCookie()
    for header in set_cookie_headers:
        jar.load(header)
    return "; ".join(f"{morsel.key}={morsel.value}" for morsel in jar.values())


def main() -> int:
    lan_host = os.environ.get("QA_LAN_HOST", DEFAULT_LAN_HOST).strip()
    base_url = env("QA_LAN_BASE_URL", f"http://{lan_host}:3000")
    api_origin = env("QA_LAN_API_ORIGIN", f"http://{lan_host}:8071")
    timeout_seconds = int(
        os.environ.get("QA_LAN_CONVERSION_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))
    )
    bootstrap_url = (
        os.environ.get("QA_LAN_CONVERSION_BOOTSTRAP_URL", f"{api_origin}{BOOTSTRAP_PATH}")
        .strip()
        or f"{api_origin}{BOOTSTRAP_PATH}"
    )

    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"

    while time.monotonic() <= deadline:
        try:
            status, location, cookies, headers, _body = request_without_redirect(
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
        conversion_status = headers.get("X-QA-Bootstrap-Conversion-Status", "")
        conversion_url = headers.get("X-QA-Bootstrap-Conversion-Url", "")
        conversion_title = headers.get("X-QA-Bootstrap-Conversion-Title", "")
        conversion_item_id = headers.get("X-QA-Bootstrap-Conversion-Item-Id", "")
        conversion_ability = headers.get("X-QA-Bootstrap-Conversion-Ability", "")
        regular_url = headers.get("X-QA-Bootstrap-Regular-Url", "")
        mount_status = headers.get("X-QA-Bootstrap-Mount-Status", "unknown")
        mount_url = headers.get("X-QA-Bootstrap-Mount-Url", "")

        print(f"[qa-lan-conversion] request: {bootstrap_url}")
        print(f"[qa-lan-conversion] status: {status}")
        print(f"[qa-lan-conversion] location: {absolute_location or '<missing>'}")
        print(
            "[qa-lan-conversion] set-cookie: "
            + ("present" if cookies else "missing")
        )
        if regular_url:
            print(f"[qa-lan-conversion] regular fixture URL: {regular_url}")
        print(f"[qa-lan-conversion] mount fixture: {mount_status}")
        if mount_url:
            print(f"[qa-lan-conversion] mount fixture URL: {mount_url}")
        print(f"[qa-lan-conversion] conversion fixture: {conversion_status or '<missing>'}")
        if conversion_url:
            print(f"[qa-lan-conversion] conversion fixture URL: {conversion_url}")
        if conversion_title:
            print(f"[qa-lan-conversion] conversion fixture title: {conversion_title}")
        print(
            "[qa-lan-conversion] conversion ability header: "
            f"{conversion_ability or '<missing>'}"
        )
        print(
            "[qa-lan-conversion] QA browser start URL: "
            f"{bootstrap_url}"
        )

        if status != 302:
            print("[qa-lan-conversion] FAIL: expected HTTP 302", file=sys.stderr)
            return 1
        if not location or not absolute_location:
            print("[qa-lan-conversion] FAIL: missing Location header", file=sys.stderr)
            return 1
        if not same_origin(absolute_location, base_url):
            expected_origin = urllib.parse.urlparse(base_url)
            actual_origin = urllib.parse.urlparse(absolute_location)
            print(
                "[qa-lan-conversion] FAIL: expected redirect origin "
                f"{expected_origin.scheme}://{expected_origin.netloc}, got "
                f"{actual_origin.scheme}://{actual_origin.netloc}",
                file=sys.stderr,
            )
            return 1
        if not cookies:
            print(
                "[qa-lan-conversion] FAIL: bootstrap did not set session cookies",
                file=sys.stderr,
            )
            return 1
        if conversion_status != "ready" or conversion_ability != "convert":
            print(
                "[qa-lan-conversion] FAIL: conversion fixture is not ready",
                file=sys.stderr,
            )
            return 1
        if not conversion_url or not same_origin(conversion_url, base_url):
            print(
                "[qa-lan-conversion] FAIL: conversion fixture URL is not LAN-facing",
                file=sys.stderr,
            )
            return 1
        if not conversion_title.endswith(".doc"):
            print(
                "[qa-lan-conversion] FAIL: conversion fixture is not a legacy .doc",
                file=sys.stderr,
            )
            return 1
        if not conversion_item_id:
            print("[qa-lan-conversion] FAIL: missing conversion item id", file=sys.stderr)
            return 1

        detail_url = f"{api_origin}/api/v1.0/items/{conversion_item_id}/"
        detail_status, _detail_location, _detail_cookies, _detail_headers, detail_body = (
            request_without_redirect(
                detail_url,
                timeout=5,
                headers={"Cookie": cookie_header(cookies)},
            )
        )
        if detail_status != 200:
            print(
                "[qa-lan-conversion] FAIL: conversion item detail is not readable",
                file=sys.stderr,
            )
            return 1
        detail = json.loads(detail_body.decode("utf-8"))
        can_convert = bool(detail.get("abilities", {}).get("convert"))
        print(f"[qa-lan-conversion] item detail status: {detail_status}")
        print(f"[qa-lan-conversion] item detail convert ability: {str(can_convert).lower()}")
        if not can_convert:
            print(
                "[qa-lan-conversion] FAIL: item detail does not expose convert ability",
                file=sys.stderr,
            )
            return 1

        print(
            "[qa-lan-conversion] PASS: authenticated LAN QA conversion fixture "
            f"is ready at {conversion_url}"
        )
        return 0

    print(
        "[qa-lan-conversion] FAIL: conversion bootstrap did not become ready; "
        f"last sanitized error: {last_error}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
