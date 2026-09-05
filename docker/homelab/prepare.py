"""Create local configuration once; never overwrite operator settings or secrets."""

import json
import os
from pathlib import Path
import secrets


def create_once(path, content):
    """Exclusive creation preserves manual changes on every subsequent run."""
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    except FileExistsError:
        return
    with os.fdopen(descriptor, "w") as stream:
        stream.write(content)


def prepare(root):
    config = root / "env.d" / "production"
    private = config / "secrets"
    (private / "nas").mkdir(parents=True, exist_ok=True, mode=0o750)
    create_once(config / "backend.local", (config / "backend.example").read_text())
    create_once(config / "mounts.local", "[]\n")
    for name in ("database_password", "django_secret_key", "s3_access_key", "s3_secret_key"):
        create_once(private / name, secrets.token_urlsafe(48) + "\n")
    for name in ("oidc_client_secret", "st_service_key"):
        create_once(private / name, "")
    create_once(private / "s3_config", json.dumps({"identities": [{
        "name": "drive", "credentials": [{
            "accessKey": (private / "s3_access_key").read_text().strip(),
            "secretKey": (private / "s3_secret_key").read_text().strip(),
        }], "actions": ["Admin:drive-media-storage", "Read:drive-media-storage", "Write:drive-media-storage", "List:drive-media-storage", "Tagging:drive-media-storage"],
    }]}) + "\n")


if __name__ == "__main__":
    prepare(Path(__file__).resolve().parents[2])
    print("Local configuration prepared. Set public origins, OIDC and ST references before starting.")
