"""Prepare the second IdP separately, with synthetic credentials and no Docker socket."""

import argparse
import ipaddress
import json
import os
import secrets
from pathlib import Path


def prepare(host):
    ipaddress.ip_address(host)
    folder = Path(__file__).resolve().parents[2] / "data/suite-authentik-qa"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
    path = folder / "secrets.json"
    secret = (
        json.loads(path.read_text())
        if path.exists()
        else {
            name: secrets.token_urlsafe(40)
            for name in ("postgres", "secret", "admin", "bootstrap_token")
        }
    )
    path.write_text(json.dumps(secret, indent=2))
    env = {
        "AUTHENTIK_POSTGRESQL__HOST": "postgres",
        "AUTHENTIK_POSTGRESQL__NAME": "authentik",
        "AUTHENTIK_POSTGRESQL__USER": "authentik",
        "AUTHENTIK_POSTGRESQL__PASSWORD": secret["postgres"],
        "AUTHENTIK_SECRET_KEY": secret["secret"],
        "AUTHENTIK_ERROR_REPORTING__ENABLED": "false",
        "AUTHENTIK_WEB__BASE_URL": f"http://{host}:19190",
    }
    common = {
        "image": "ghcr.io/goauthentik/server:2026.8.1",
        "environment": env,
        "volumes": ["data:/data"],
        "shm_size": "512mb",
        "depends_on": {"postgres": {"condition": "service_healthy"}},
    }
    services = {
        "postgres": {
            "image": "postgres:16",
            "environment": {
                "POSTGRES_USER": "authentik",
                "POSTGRES_DB": "authentik",
                "POSTGRES_PASSWORD": secret["postgres"],
            },
            "volumes": ["postgres:/var/lib/postgresql/data"],
            "healthcheck": {
                "test": ["CMD-SHELL", "pg_isready -U authentik"],
                "interval": "2s",
                "timeout": "3s",
                "retries": 30,
            },
        },
        "server": {**common, "command": ["server"], "ports": [f"{host}:19190:9000"]},
        "worker": {
            **common,
            "command": ["worker"],
            "environment": {
                **env,
                "AUTHENTIK_BOOTSTRAP_PASSWORD": secret["admin"],
                "AUTHENTIK_BOOTSTRAP_TOKEN": secret["bootstrap_token"],
                "AUTHENTIK_BOOTSTRAP_EMAIL": "admin@suite-qa.invalid",
            },
        },
    }
    target = folder / "compose.json"
    target.write_text(
        json.dumps(
            {
                "name": "suite-identity-authentik-qa",
                "services": services,
                "volumes": {"postgres": {}, "data": {}},
            },
            indent=2,
        )
    )
    for file in (target, path):
        file.chmod(0o600)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    parser.exit(
        message=f"Private Authentik qualification configuration prepared: {prepare(args.host)}\n"
    )
