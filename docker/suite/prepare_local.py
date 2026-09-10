"""Prepare persistent LAN configuration; never start services or overwrite private settings."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import UUID


def write_private(path, content, *, uid=None):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(content)
    path.chmod(0o600)
    if uid is not None:
        os.chown(path, uid, uid)


def environment(path, values):
    lines = []
    for key, value in values.items():
        value = str(value)
        if any(char in value for char in "\r\n\0$"):
            raise ValueError(f"Invalid environment value for {key}")
        lines.append(f"{key}={value}")
    write_private(path, "\n".join(lines) + "\n")


def write_storage_config(state, settings):
    """Keep dedicated application identities on every configuration regeneration."""
    s3 = settings["s3"]
    identities = [
        {
            "name": "docs",
            "credentials": [
                {"accessKey": s3["access_key"], "secretKey": s3["secret_key"]}
            ],
            "actions": [
                f"{action}:{s3['bucket']}"
                for action in ("Read", "Write", "List", "Tagging")
            ],
        },
        {
            "name": "installation",
            "credentials": [
                {
                    "accessKey": settings["s3_admin"]["access_key"],
                    "secretKey": settings["s3_admin"]["secret_key"],
                }
            ],
            "actions": ["Admin", "Read", "Write", "List", "Tagging"],
        },
    ]
    for name, consumer in settings.get("storage_consumers", {}).items():
        if name in {"docs", "installation"}:
            raise ValueError("Reserved storage identity")
        identities.append({
            "name": name,
            "credentials": [{"accessKey": consumer["access_key"], "secretKey": consumer["secret_key"]}],
            "actions": [f"{action}:{consumer['bucket']}" for action in ("Read", "Write", "List", "Tagging")],
        })
    write_private(
        state / "docs/s3.json", json.dumps({"identities": identities}) + "\n", uid=1000
    )


def prepare(args):
    ipaddress.ip_address(args.host)
    organization = str(UUID(args.organization_id))
    issuer = args.issuer
    parsed = urlsplit(issuer)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Explicit OIDC issuer required")
    with urlopen(
        issuer.rstrip("/") + "/.well-known/openid-configuration", timeout=5
    ) as response:
        data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError("OIDC discovery exceeds 1 MiB")
        discovery = json.loads(data)
    if discovery.get("issuer") != issuer:
        raise ValueError("OIDC discovery issuer mismatch")
    state = args.state.resolve()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.chmod(0o700)
    settings_path = state / "settings.json"
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
        if (settings["host"], settings["issuer"], settings["organization_id"]) != (
            args.host,
            issuer,
            organization,
        ):
            raise ValueError(
                "Existing installation differs; use the documented migration procedure"
            )
    else:
        settings = {
            "host": args.host,
            "issuer": issuer,
            "organization_id": organization,
            "postgres_password": secrets.token_urlsafe(40),
            "collaboration_key": secrets.token_urlsafe(40),
            "s3": {
                "endpoint": "http://docs-s3:8333",
                "bucket": "docs-media-storage",
                "access_key": secrets.token_urlsafe(32),
                "secret_key": secrets.token_urlsafe(40),
            },
            "apps": {
                app: {
                    "client_id": "drive" if app == "drive" else "apoze-" + app,
                    "client_secret": secrets.token_urlsafe(40),
                    "read_key": secrets.token_urlsafe(40),
                    "mutation_key": secrets.token_urlsafe(40),
                    "policy_key": secrets.token_urlsafe(40),
                    "policy_service_id": "",
                    "db_password": secrets.token_urlsafe(40),
                    "django_secret": secrets.token_urlsafe(40),
                }
                for app in ("drive", "st", "people", "docs")
            },
        }
        write_private(settings_path, json.dumps(settings, indent=2) + "\n")
    if "s3_admin" not in settings:
        settings["s3_admin"] = {
            "access_key": secrets.token_urlsafe(32),
            "secret_key": secrets.token_urlsafe(40),
        }
        write_private(settings_path, json.dumps(settings, indent=2) + "\n")
    write_storage_config(state, settings)
    if args.activate and any(
        not app["policy_service_id"] for app in settings["apps"].values()
    ):
        raise ValueError(
            "Associate all ST service IDs in private settings before activation"
        )
    write_private(state / "postgres-password", settings["postgres_password"], uid=999)
    sql = []
    for app in ("people", "docs"):
        password = settings["apps"][app]["db_password"].replace("'", "''")
        sql += [
            f"CREATE USER {app} WITH PASSWORD '{password}';",
            f"CREATE DATABASE {app} OWNER {app};",
        ]
    write_private(state / "postgres-init/00-databases.sql", "\n".join(sql), uid=999)
    os.chown(state / "postgres-init", 999, 999)
    environment(
        state / "compose.env",
        {
            "SUITE_HOST": args.host,
            "SUITE_PRIVATE_DIR": state,
            "PEOPLE_REPO": args.people.resolve(),
            "DOCS_REPO": args.docs.resolve(),
            "SUITE_UID": args.uid,
            "SUITE_GID": args.uid,
        },
    )
    for index, app in enumerate(("people", "docs")):
        config = settings["apps"][app]
        api = f"http://{args.host}:{8072 + index}"
        frontend = f"http://{args.host}:{3001 + index}"
        keys = state / app / "keys"
        for field in ("read_key", "mutation_key", "policy_key"):
            write_private(keys / field, config[field], uid=args.uid)
        os.chown(keys, args.uid, args.uid)
        env = {
            "DJANGO_CONFIGURATION": "Development",
            "DJANGO_SECRET_KEY": config["django_secret"],
            "DB_HOST": "suite-postgres",
            "DB_PORT": "5432",
            "DB_NAME": app,
            "DB_USER": app,
            "DB_PASSWORD": config["db_password"],
            "REDIS_URL": f"redis://suite-redis:6379/{index}",
            "CELERY_BROKER_URL": f"redis://suite-redis:6379/{index + 2}",
            "DJANGO_CELERY_BROKER_URL": f"redis://suite-redis:6379/{index + 2}",
            "PYTHONPATH": "/code",
            "DJANGO_ALLOWED_HOSTS": f"{args.host},localhost,127.0.0.1,{app}",
            "DJANGO_CSRF_TRUSTED_ORIGINS": api + "," + frontend,
            "CSRF_TRUSTED_ORIGINS": api + "," + frontend,
            "CORS_ALLOWED_ORIGINS": api + "," + frontend,
            "SESSION_COOKIE_NAME": f"suite_{app}_sessionid",
            "CSRF_COOKIE_NAME": f"suite_{app}_csrftoken",
            "OIDC_RP_CLIENT_ID": config["client_id"],
            "OIDC_RP_CLIENT_SECRET": config["client_secret"],
            "OIDC_RP_SCOPES": "openid email profile",
            "OIDC_USE_PKCE": "true",
            "OIDC_TIMEOUT": "5",
            "OIDC_AUTH_REQUEST_EXTRA_PARAMS": '{"max_age":900}',
            "OIDC_FALLBACK_TO_EMAIL_FOR_IDENTIFICATION": "false",
            "OIDC_CREATE_USER": "false",
            "DJANGO_OIDC_CREATE_USER": "false",
            "OIDC_RESOURCE_SERVER_ENABLED": "false",
            "OIDC_USERINFO_FULLNAME_FIELDS": "given_name,family_name",
            "USER_OIDC_ESSENTIAL_CLAIMS": "",
            "LOGIN_REDIRECT_URL": frontend,
            "LOGIN_REDIRECT_URL_FAILURE": frontend,
            "LOGOUT_REDIRECT_URL": frontend,
            "SUITE_IDENTITY_ENABLED": str(args.activate).lower(),
            "SUITE_APP_ID": app,
            "SUITE_OIDC_ISSUER": issuer,
            "SUITE_ORGANIZATION_ID": organization,
            "SUITE_DIRECTORY_URL": "http://people:8000/api/v1.0/suite-directory/",
            "SUITE_DIRECTORY_TOKEN_FILE": "/run/suite/read_key",
            "SUITE_POLICY_URL": f"http://{args.host}:8961/api/v1.0/suite-policy/",
            "SUITE_POLICY_SERVICE_ID": config["policy_service_id"],
            "SUITE_POLICY_TOKEN_FILE": "/run/suite/policy_key",
            "SUITE_CATALOGUE_URL": f"http://{args.host}:8961/api/v1.0/suite-catalogue/",
            "SUITE_LOGOUT_URL": "http://people:8000/api/v1.0/suite-revoke-sessions/",
            "SUITE_LOGOUT_TOKEN_FILE": "/run/suite/mutation_key",
            "SUITE_IDENTITY_REQUEST_URL": "http://people:8000/api/v1.0/suite-identity-requests/",
            "DJANGO_EMAIL_HOST": "mailcatcher",
            "DJANGO_EMAIL_PORT": "1025",
            "DJANGO_EMAIL_USE_TLS": "false",
            "DJANGO_EMAIL_USE_SSL": "false",
            "AI_FEATURE_ENABLED": "false",
            "SIGNUP_NEW_USER_TO_MARKETING_EMAIL": "false",
        }
        for setting, name in {
            "OIDC_OP_AUTHORIZATION_ENDPOINT": "authorization_endpoint",
            "OIDC_OP_TOKEN_ENDPOINT": "token_endpoint",
            "OIDC_OP_USER_ENDPOINT": "userinfo_endpoint",
            "OIDC_OP_JWKS_ENDPOINT": "jwks_uri",
            "OIDC_OP_LOGOUT_ENDPOINT": "end_session_endpoint",
        }.items():
            endpoint = discovery.get(name, "")
            if name != "end_session_endpoint" and not endpoint:
                raise ValueError(f"Required OIDC discovery field absent: {name}")
            env[setting] = endpoint
        if app == "docs":
            s3 = settings["s3"]
            env.update(
                {
                    "AWS_S3_ENDPOINT_URL": s3["endpoint"],
                    "AWS_STORAGE_BUCKET_NAME": s3["bucket"],
                    "AWS_S3_ACCESS_KEY_ID": s3["access_key"],
                    "AWS_S3_SECRET_ACCESS_KEY": s3["secret_key"],
                    "AWS_S3_REGION_NAME": "us-east-1",
                    "MEDIA_BASE_URL": f"http://{args.host}:8084",
                    "COLLABORATION_API_URL": "http://docs-collaboration:4444/collaboration/api/",
                    "COLLABORATION_WS_URL": f"ws://{args.host}:4444/collaboration/ws/",
                    "COLLABORATION_SERVER_SECRET_FILE": "/run/suite/collaboration",
                    "Y_PROVIDER_API_KEY_FILE": "/run/suite/collaboration",
                    "Y_PROVIDER_API_BASE_URL": "http://docs-collaboration:4444",
                    "COLLABORATION_WS_NOT_CONNECTED_READ_ONLY": "true",
                }
            )
            write_private(
                keys / "collaboration", settings["collaboration_key"], uid=args.uid
            )
            environment(
                state / "docs/collaboration.env",
                {
                    "COLLABORATION_BACKEND_BASE_URL": "http://docs:8000",
                    "COLLABORATION_SERVER_ORIGIN": frontend,
                    "COLLABORATION_SERVER_SECRET_FILE": "/run/collaboration",
                    "Y_PROVIDER_API_KEY_FILE": "/run/collaboration",
                    "DOCS_SESSION_COOKIE_NAME": "suite_docs_sessionid",
                    "SUITE_IDENTITY_ENABLED": str(args.activate).lower(),
                },
            )
            environment(
                state / "docs/media.env",
                {
                    "DOCS_API_ENDPOINT": "http://docs:8000",
                    "DOCS_API_HOST": "docs",
                    "DOCS_S3_ENDPOINT": s3["endpoint"],
                    "DOCS_S3_HOST": urlsplit(s3["endpoint"]).netloc,
                    "DOCS_S3_BUCKET": s3["bucket"],
                    "DOCS_UI_ORIGIN": frontend,
                    "NGINX_ENVSUBST_FILTER": "^DOCS_",
                },
            )
        environment(state / app / "backend.env", env)
        environment(
            state / app / "frontend.env",
            {
                "NEXT_PUBLIC_API_ORIGIN": api,
                "DEV_ALLOWED_ORIGINS": args.host,
                "NEXT_PUBLIC_CSRF_COOKIE_NAME": f"suite_{app}_csrftoken",
                "NEXT_TELEMETRY_DISABLED": "1",
                "NEXT_PUBLIC_SW_DEACTIVATED": "true",
            },
        )
    print(f"Persistent LAN configuration prepared in {state}; no services started.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--people", type=Path, required=True)
    parser.add_argument("--docs", type=Path, required=True)
    parser.add_argument("--uid", type=int, default=1000)
    parser.add_argument("--activate", action="store_true")
    os.umask(0o077)
    prepare(parser.parse_args())
