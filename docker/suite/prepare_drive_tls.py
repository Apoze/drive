"""Prepare an optional LAN TLS facade over the existing Drive services."""

import argparse
import ipaddress
import json
import os
from pathlib import Path

from prepare_local import write_private
from prepare_mail import update_environment


def prepare(state, tls, host, port=8445):
    host = str(ipaddress.ip_address(host))
    if ":" in host or not 1024 <= port <= 65535:
        raise ValueError("An IPv4 LAN address and unprivileged port are required")
    state, tls = state.resolve(), tls.resolve()
    if not all((tls / name).is_file() for name in ("server.crt", "server.key")):
        raise ValueError("Provide an existing certificate and key for the LAN address")
    os.umask(0o077)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    origin = f"https://{host}:{port}"
    write_private(
        state / "nginx.conf",
        f"""events {{}}
http {{
 access_log off;
 map $http_upgrade $connection_upgrade {{ default upgrade; '' close; }}
 server {{
  listen 8443 ssl;
  ssl_certificate /run/tls/server.crt;
  ssl_certificate_key /run/tls/server.key;
  client_max_body_size 128m;
  proxy_set_header Host $http_host;
  proxy_set_header X-Forwarded-Proto https;
  proxy_set_header X-Forwarded-For $remote_addr;
  proxy_request_buffering off;
  proxy_buffering off;
  proxy_read_timeout 300s;
  location /api/ {{ proxy_pass http://{host}:8071; }}
  location / {{
   proxy_pass http://{host}:3000;
   proxy_http_version 1.1;
   proxy_set_header Host $http_host;
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection $connection_upgrade;
  }}
 }}
}}
""",
    )
    write_private(
        state / "compose.json",
        json.dumps(
            {
                "name": "suite-drive-tls",
                "services": {
                    "edge": {
                        "image": "nginx:1.28.0-alpine@sha256:30f1c0d78e0ad60901648be663a710bdadf19e4c10ac6782c235200619158284",
                        "restart": "unless-stopped",
                        "mem_limit": "64m",
                        "ports": [f"{host}:{port}:8443"],
                        "volumes": [
                            f"{state}/nginx.conf:/etc/nginx/nginx.conf:ro",
                            f"{tls}/server.crt:/run/tls/server.crt:ro",
                            f"{tls}/server.key:/run/tls/server.key:ro",
                        ],
                    },
                },
            },
            indent=2,
        )
        + "\n",
    )
    env_path = Path(__file__).resolve().parents[2] / "env.d/development/common.local"
    existing = dict(
        line.split("=", 1)
        for line in env_path.read_text().splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    )
    updates = {
        "CHAT_PICKER_PUBLIC_URL": origin,
        "SECURE_PROXY_SSL_HEADER": "HTTP_X_FORWARDED_PROTO,https",
    }
    for key, value in [
        ("CSRF_TRUSTED_ORIGINS", origin),
        ("OIDC_REDIRECT_ALLOWED_HOSTS", f"{host}:{port}"),
    ]:
        values = existing.get(key, "").strip("\"'").split(",")
        updates[key] = ",".join(dict.fromkeys([v for v in values if v] + [value]))
    update_environment(env_path, updates)
    return origin


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--tls", type=Path, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8445)
    args = parser.parse_args()
    prepare(args.state, args.tls, args.host, args.port)
