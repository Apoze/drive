"""Bounded machine JSON exchanges; credentials never follow a redirect."""

import json
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    """Retain credentials only for the explicitly configured destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: PLR0913
        """The stdlib handler signature is fixed; every redirect is refused."""
        return None


def read_credential(path):
    """Read only the bounded opaque machine credential from its private file."""
    with Path(path).open(encoding="utf-8") as source:
        value = source.read(258).strip()
    if not 32 <= len(value) <= 256 or "\n" in value or "\r" in value:
        raise ValueError("Invalid machine credential")
    return value


@contextmanager
def open_response(url, *, headers, data=None, timeout=5):
    """Keep credentials on the configured HTTP(S) endpoint, including binary reads."""
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or (parsed.username or parsed.password or parsed.fragment)
    ):
        raise ValueError("Invalid machine endpoint")
    request = Request(url, data=data, headers=headers)  # noqa: S310 - HTTP(S) checked above.
    with build_opener(NoRedirect).open(request, timeout=timeout) as response:
        yield response


def read_json(url, *, headers, data=None, limit, timeout=5):
    """Accept HTTP(S) only and cap time and bytes before parsing a response."""
    with open_response(url, headers=headers, data=data, timeout=timeout) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Machine response exceeds the byte limit")
    return json.loads(raw)
