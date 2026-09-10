"""Prepare only the Docs/Drive peer connection; preserve IdP, NAS and suite settings."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import secrets
import tempfile

from prepare_local import write_private


def update_environment(path, values):
    if not path.is_file() or path.is_symlink():
        raise ValueError("An existing local application environment is required")
    lines = path.read_text().splitlines()
    for key, value in values.items():
        if any(character in str(value) for character in "\r\n\0$"):
            raise ValueError("Invalid document environment value")
        lines = [line for line in lines if line.split("=", 1)[0].strip() != key]
        lines.append(f"{key}={value}")
    original = path.stat()
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            os.fchmod(output.fileno(), 0o600)
            os.fchown(output.fileno(), original.st_uid, original.st_gid)
            output.write("\n".join(lines) + "\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def prepare(state, drive, *, mode="prepare", uid=1000):
    settings_path = state / "settings.json"
    if settings_path.is_symlink() or not settings_path.is_file():
        raise ValueError("An existing suite installation is required")
    installation = json.loads(settings_path.read_text())
    host = str(ipaddress.ip_address(installation["host"]))
    source = drive / "data/storage-secrets/docs-documents"
    native = state / "docs/keys/documents"
    environments = (drive / "env.d/development/common.local", state / "docs/backend.env")
    if not all(path.is_file() and not path.is_symlink() for path in environments):
        raise ValueError("Both existing application environments are required")
    issuers = []
    for env in environments:
        issuer = next((line.split("=", 1)[1].strip().strip('"\'')
                       for line in env.read_text().splitlines()
                       if line.startswith("SUITE_OIDC_ISSUER=")), "")
        if not issuer.startswith(("https://", "http://")):
            raise ValueError("Both application issuers must be explicitly configured")
        issuers.append(issuer)
    pairs = [(source / f"{direction}_{purpose}", native / f"{'outbound' if direction == 'inbound' else 'inbound'}_{purpose}") for direction in ("inbound", "outbound") for purpose in ("read", "mutation")]
    retained = []
    for left, right in pairs:
        values = []
        for path in (left, right):
            if path.is_symlink():
                raise ValueError("Document credentials must not be symlinks")
            if path.exists():
                value = path.read_text().strip()
                if not 40 <= len(value) <= 256 or not value.isascii() or any(char.isspace() for char in value):
                    raise ValueError("An existing document credential is invalid")
                values.append(value)
        if len(set(values)) > 1:
            raise ValueError("Peer credentials differ; do not silently rotate them")
        retained.append(values[0] if values else secrets.token_urlsafe(48))
    if len(set(retained)) != len(retained):
        raise ValueError("Read, mutation and direction credentials must be distinct")
    for pair, value in zip(pairs, retained, strict=True):
        for path in pair:
            write_private(path, value, uid=uid)
            os.chown(path.parent, uid, uid)
    for env, prefix, peer in zip(environments, ("/run/storage-secrets/docs-documents", "/run/suite/documents"), (8073, 8071), strict=True):
        values = {"DOCUMENT_PEER_API_URL": f"http://{host}:{peer}"}
        values["DOCUMENT_PEER_OIDC_ISSUER"] = issuers[1 if env == environments[0] else 0]
        for direction in ("inbound", "outbound"):
            for purpose in ("read", "mutation"):
                values[f"DOCUMENT_{direction.upper()}_{purpose.upper()}_KEY_FILE"] = f"{prefix}/{direction}_{purpose}"
        if mode != "prepare":
            values["DOCS_DRIVE_ENABLED"] = str(mode == "enable").lower()
        elif not any(line.startswith("DOCS_DRIVE_ENABLED=") for line in env.read_text().splitlines()):
            values["DOCS_DRIVE_ENABLED"] = "false"
        if env == environments[0]:
            values["DOCS_PUBLIC_URL"] = f"http://{host}:3002"
        else:
            values["DOCS_PDF_RENDERER_URL"] = "http://docs-pdf-renderer:4445"
        update_environment(env, values)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--drive", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--mode", choices=["prepare", "enable", "disable"], default="prepare")
    parser.add_argument("--uid", type=int, default=1000)
    options = parser.parse_args()
    os.umask(0o077)
    prepare(options.state.resolve(), options.drive.resolve(), mode=options.mode, uid=options.uid)
    print("Document peer configuration prepared; no services restarted and no credentials displayed.")
