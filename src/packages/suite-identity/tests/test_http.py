"""Machine credentials stay on the approved endpoint and response reads stay bounded."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.error import HTTPError

import pytest
from suite_identity.http import read_json


def test_pdf_exchange_checks_size_and_digest(settings, tmp_path):
    import hashlib

    from suite_identity.document_transport import DocumentServiceUnavailable, pdf_stream

    body, corrupt = b"%PDF-1.4\ntransport\n%%EOF", False
    credential = tmp_path / "read-key"
    credential.write_text("isolated-pdf-test".ljust(48, "-"))
    settings.DOCUMENT_OUTBOUND_READ_KEY_FILE = str(credential)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-SHA256", "invalid" if corrupt else hashlib.sha256(body).hexdigest())
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings.DOCUMENT_PEER_API_URL = f"http://127.0.0.1:{server.server_port}"
    try:
        with pdf_stream({}, actor=None) as stream:
            assert stream.read() == body
        corrupt = True
        with pytest.raises(DocumentServiceUnavailable):
            with pdf_stream({}, actor=None):
                pytest.fail("An invalid digest cannot produce a complete export.")
        with pytest.raises(DocumentServiceUnavailable):
            with pdf_stream({}, actor=None, limit=6):
                pytest.fail("An oversized response cannot be accepted.")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_machine_exchange_refuses_redirects_schemes_and_oversized_json():
    """Exercise real HTTP without an IdP, credentials or external network access."""
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/forbidden-target")
                body = b""
            else:
                self.send_response(200)
                body = b'{"ok":true}' if self.path == "/ok" else b" " * 128
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        assert read_json(base + "/ok", headers={}, limit=64) == {"ok": True}
        with pytest.raises(HTTPError):
            read_json(base + "/redirect", headers={}, limit=64)
        with pytest.raises(ValueError):
            read_json(base + "/large", headers={}, limit=64)
        with pytest.raises(ValueError):
            read_json("file:///unread", headers={}, limit=64)
        assert seen == ["/ok", "/redirect", "/large"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
