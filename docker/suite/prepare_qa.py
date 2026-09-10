"""Prepare one isolated Compose qualification; never read local production secrets."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import secrets
import copy
import uuid
from urllib.request import urlopen


def prepare(host, people, docs, st, enable_identity=False, idp="keycloak"):
    """Create persistent synthetic configuration without starting any container."""
    ipaddress.ip_address(host)
    root = Path(__file__).resolve().parents[2]
    target = root / "data/suite-identity-qa"
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target, 0o700)
    secret_path = target / "secrets.json"
    if secret_path.exists():
        secret = json.loads(secret_path.read_text())
    else:
        secret = {
            key: secrets.token_urlsafe(32)
            for key in (
                "postgres",
                "drive",
                "st",
                "people",
                "docs",
                "keycloak",
                "s3_key",
                "s3_secret",
                "oidc_drive",
                "oidc_st",
                "oidc_people",
                "oidc_docs",
                "admin",
                "alice",
                "bob",
                "outsider",
                "django_drive",
                "django_st",
                "django_people",
                "django_docs",
                "directory_drive",
                "directory_st",
                "directory_docs",
                "directory_people",
                "collaboration",
            )
        }
        secret_path.write_text(json.dumps(secret, indent=2))
        secret_path.chmod(0o600)
    for app in ("drive", "st", "people", "docs"):
        secret.setdefault("policy_" + app, secrets.token_urlsafe(32))
        secret.setdefault("logout_" + app, secrets.token_urlsafe(32))
    secret_path.write_text(json.dumps(secret, indent=2))
    init = target / "postgres-init"
    init.mkdir(exist_ok=True)
    sql = []
    for app in ("drive", "st", "people", "docs", "keycloak"):
        sql += [
            f"CREATE USER {app} WITH PASSWORD '{secret[app]}';",
            f"CREATE DATABASE {app} OWNER {app};",
        ]
    (init / "00-databases.sql").write_text("\n".join(sql))
    os.chown(init, 999, 999)
    os.chown(init / "00-databases.sql", 999, 999)
    issuer = f"http://{host}:19180/realms/suite-qa"
    users = [
        {
            "username": name,
            "email": f"{name}@suite-qa.invalid",
            "emailVerified": True,
            "enabled": True,
            "firstName": name.title(),
            "lastName": "Qualification",
            "credentials": [
                {"type": "password", "value": secret[name], "temporary": False}
            ],
        }
        for name in ("alice", "bob", "outsider")
    ]
    realm = {
        "realm": "suite-qa",
        "enabled": True,
        "registrationAllowed": False,
        "users": users,
        "clients": [],
    }
    ports = {"drive": 19101, "st": 19102, "people": 19103, "docs": 19104}
    for app, port in ports.items():
        realm["clients"].append(
            {
                "clientId": f"suite-{app}",
                "secret": secret[f"oidc_{app}"],
                "protocol": "openid-connect",
                "publicClient": False,
                "standardFlowEnabled": True,
                "redirectUris": [f"http://{host}:{port}/api/v1.0/callback/"],
                "webOrigins": [f"http://{host}:{port}"],
                "attributes": {
                    "pkce.code.challenge.method": "S256",
                    "post.logout.redirect.uris": f"http://{host}:{port}/api/v1.0/logout-callback/",
                },
            }
        )
    (target / "realm.json").write_text(json.dumps(realm, indent=2))
    (target / "s3.json").write_text(
        json.dumps(
            {
                "identities": [
                    {
                        "name": "qualification",
                        "credentials": [
                            {
                                "accessKey": secret["s3_key"],
                                "secretKey": secret["s3_secret"],
                            }
                        ],
                        "actions": ["Admin", "Read", "List", "Tagging", "Write"],
                    }
                ]
            }
        )
    )
    services = {
        "postgres": {
            "image": "postgres:16",
            "environment": {"POSTGRES_PASSWORD": secret["postgres"]},
            "volumes": [
                "postgres:/var/lib/postgresql/data",
                f"{init}:/docker-entrypoint-initdb.d:ro",
            ],
            "healthcheck": {
                "test": ["CMD-SHELL", "pg_isready -U postgres"],
                "interval": "2s",
                "timeout": "3s",
                "retries": 30,
            },
        },
        "redis": {"image": "redis:5"},
        "keycloak": {
            "image": "quay.io/keycloak/keycloak:26.3.2",
            "command": ["start-dev", "--import-realm"],
            "ports": [f"{host}:19180:8080"],
            "environment": {
                "KC_DB": "postgres",
                "KC_DB_URL": "jdbc:postgresql://postgres:5432/keycloak",
                "KC_DB_USERNAME": "keycloak",
                "KC_DB_PASSWORD": secret["keycloak"],
                "KC_HOSTNAME": f"http://{host}:19180",
                "KC_BOOTSTRAP_ADMIN_USERNAME": "qa-admin",
                "KC_BOOTSTRAP_ADMIN_PASSWORD": secret["admin"],
            },
            "volumes": [f"{target}/realm.json:/opt/keycloak/data/import/realm.json:ro"],
            "depends_on": {"postgres": {"condition": "service_healthy"}},
        },
        "s3": {
            "image": "chrislusf/seaweedfs:latest",
            "command": [
                "server",
                "-s3",
                "-ip=s3",
                "-dir=/data",
                "-s3.config=/etc/s3.json",
            ],
            "ports": [f"{host}:19100:8333"],
            "volumes": ["s3:/data", f"{target}/s3.json:/etc/s3.json:ro"],
        },
    }
    repos = {
        "drive": root,
        "st": Path(st).resolve(),
        "people": Path(people).resolve(),
        "docs": Path(docs).resolve(),
    }
    images = {
        "drive": "drive:backend-development",
        "st": "st-deploycenter-backend-dev",
        "people": "apoze/people:identity-dev",
        "docs": "apoze/docs:identity-dev",
    }
    defaults = {
        "drive": "common",
        "st": "backend.defaults",
        "people": "common.dist",
        "docs": "common",
    }
    package = root / "src/packages/suite-identity"
    volumes = {"postgres": {}, "s3": {}}
    projects = {
        "drive": "drive",
        "st": "deploycenter",
        "people": "people",
        "docs": "impress",
    }
    for index, (app, repo) in enumerate(repos.items()):
        port = ports[app]
        origin = f"http://{host}:{port}"
        frontend_origin = f"http://{host}:{port + 10}"
        token_path = target / f"directory-{app}.key"
        token_path.write_text(secret[f"directory_{app}"])
        policy_path = target / f"policy-{app}.key"
        policy_path.write_text(secret[f"policy_{app}"])
        logout_path = target / f"logout-{app}.key"
        logout_path.write_text(secret[f"logout_{app}"])
        env = {
            "DJANGO_CONFIGURATION": "DevelopmentMinimal"
            if app == "st"
            else "Development",
            "DJANGO_SECRET_KEY": secret[f"django_{app}"],
            "DB_HOST": "postgres",
            "DB_PORT": "5432",
            "DB_NAME": app,
            "DB_USER": app,
            "DB_PASSWORD": secret[app],
            "REDIS_URL": f"redis://redis:6379/{index}",
            "DJANGO_ALLOWED_HOSTS": f"{host},localhost,127.0.0.1,{app}",
            "DJANGO_CSRF_TRUSTED_ORIGINS": origin + "," + frontend_origin,
            "CSRF_TRUSTED_ORIGINS": origin + "," + frontend_origin,
            "CORS_ALLOWED_ORIGINS": origin + "," + frontend_origin,
            "SESSION_COOKIE_NAME": f"suite_qa_{app}_session",
            "CSRF_COOKIE_NAME": f"suite_qa_{app}_csrf",
            "CELERY_BROKER_URL": f"redis://redis:6379/{index + 4}",
            "DJANGO_CELERY_BROKER_URL": f"redis://redis:6379/{index + 4}",
            "PYTHONPATH": "/suite:/code",
            "OIDC_RP_CLIENT_ID": f"suite-{app}",
            "OIDC_RP_CLIENT_SECRET": secret[f"oidc_{app}"],
            "OIDC_OP_AUTHORIZATION_ENDPOINT": issuer + "/protocol/openid-connect/auth",
            "OIDC_OP_TOKEN_ENDPOINT": issuer + "/protocol/openid-connect/token",
            "OIDC_OP_USER_ENDPOINT": issuer + "/protocol/openid-connect/userinfo",
            "OIDC_OP_JWKS_ENDPOINT": issuer + "/protocol/openid-connect/certs",
            "OIDC_OP_LOGOUT_ENDPOINT": issuer + "/protocol/openid-connect/logout",
            "OIDC_RP_SCOPES": "openid email profile",
            "OIDC_USE_PKCE": "true",
            "OIDC_AUTH_REQUEST_EXTRA_PARAMS": '{"max_age":900}',
            "OIDC_FALLBACK_TO_EMAIL_FOR_IDENTIFICATION": "false",
            "OIDC_RESOURCE_SERVER_ENABLED": "false",
            "OIDC_CREATE_USER": "false",
            "OIDC_TIMEOUT": "5",
            "OIDC_USERINFO_FULLNAME_FIELDS": "given_name,family_name",
            "USER_OIDC_ESSENTIAL_CLAIMS": "",
            "LOGIN_REDIRECT_URL": frontend_origin,
            "LOGIN_REDIRECT_URL_FAILURE": frontend_origin,
            "LOGOUT_REDIRECT_URL": frontend_origin,
            "SUITE_IDENTITY_ENABLED": str(enable_identity).lower(),
            "SUITE_APP_ID": app,
            "SUITE_OIDC_ISSUER": issuer,
            "SUITE_DIRECTORY_URL": "http://people:8000/api/v1.0/suite-directory/",
            "SUITE_DIRECTORY_TOKEN_FILE": "/run/directory.key",
            "SUITE_ORGANIZATION_ID": str(
                uuid.uuid5(uuid.NAMESPACE_URL, "apoze-suite-qa-organization")
            ),
            "SUITE_POLICY_URL": "http://st:8000/api/v1.0/suite-policy/",
            "SUITE_POLICY_SERVICE_ID": str(index + 5001),
            "SUITE_POLICY_TOKEN_FILE": "/run/policy.key",
            "SUITE_CATALOGUE_URL": "http://st:8000/api/v1.0/suite-catalogue/",
            "SUITE_LOGOUT_URL": "http://people:8000/api/v1.0/suite-revoke-sessions/",
            "SUITE_LOGOUT_TOKEN_FILE": "/run/logout.key",
            "SUITE_IDENTITY_REQUEST_URL": "http://people:8000/api/v1.0/suite-identity-requests/",
            "AWS_S3_ENDPOINT_URL": "http://s3:8333",
            "AWS_S3_ACCESS_KEY_ID": secret["s3_key"],
            "AWS_S3_SECRET_ACCESS_KEY": secret["s3_secret"],
            "AWS_STORAGE_BUCKET_NAME": app,
            "AWS_S3_REGION_NAME": "us-east-1",
            "DJANGO_EMAIL_HOST": "",
            "STORAGE_GOVERNANCE_ENABLED": "false",
            "AWS_S3_DOMAIN_REPLACE": f"http://{host}:19100",
            "STORAGE_UNIFIED_SPACES_ENABLED": "false",
            "ENTITLEMENTS_BACKEND": "core.entitlements.backends.local.LocalEntitlementsBackend",
            "AI_FEATURE_ENABLED": "false",
            "SIGNUP_NEW_USER_TO_MARKETING_EMAIL": "false",
        }
        if idp == "authentik":
            # Only the isolated qualification IdP is addressed by this helper.
            discovery_url = f"http://{host}:19190/application/o/suite-qa-{app}/.well-known/openid-configuration"
            with urlopen(discovery_url, timeout=5) as response:
                discovery = json.loads(response.read(1048576))
            expected_issuer = f"http://{host}:19190/application/o/suite-qa-{app}/"
            if discovery.get("issuer") != expected_issuer:
                raise ValueError("Unexpected qualification issuer")
            env["SUITE_OIDC_ISSUER"] = expected_issuer
            for setting, field in {
                "OIDC_OP_AUTHORIZATION_ENDPOINT": "authorization_endpoint",
                "OIDC_OP_TOKEN_ENDPOINT": "token_endpoint",
                "OIDC_OP_USER_ENDPOINT": "userinfo_endpoint",
                "OIDC_OP_JWKS_ENDPOINT": "jwks_uri",
                "OIDC_OP_LOGOUT_ENDPOINT": "end_session_endpoint",
                "OIDC_OP_INTROSPECTION_ENDPOINT": "introspection_endpoint",
            }.items():
                endpoint = discovery[field]
                if not endpoint.startswith(f"http://{host}:19190/"):
                    raise ValueError("Unexpected qualification endpoint")
                env[setting] = endpoint
        secret_mounts = []
        if app == "drive":
            for field in (
                "OIDC_RP_CLIENT_SECRET",
                "AWS_S3_ACCESS_KEY_ID",
                "AWS_S3_SECRET_ACCESS_KEY",
            ):
                secret_file = target / f"drive-{field}.key"
                secret_file.write_text(env.pop(field))
                env[field + "_FILE"] = f"/run/{field}.key"
                secret_mounts.append(f"{secret_file}:/run/{field}.key:ro")
        services[app] = {
            "image": images[app],
            "user": "0:0",
            "working_dir": "/code",
            "entrypoint": ["python"],
            "command": ["manage.py", "runserver", "0.0.0.0:8000", "--noreload"],
            "ports": [f"{host}:{port}:8000"],
            "environment": env,
            "env_file": [str(repo / "env.d/development" / defaults[app])],
            "volumes": [
                f"{repo}/src/backend:/code",
                f"{package}:/suite:ro",
                f"{token_path}:/run/directory.key:ro",
                f"{policy_path}:/run/policy.key:ro",
                f"{logout_path}:/run/logout.key:ro",
                *secret_mounts,
            ],
            "depends_on": {
                "postgres": {"condition": "service_healthy"},
                "redis": {"condition": "service_started"},
            },
        }
        worker = copy.deepcopy(services[app])
        worker.pop("ports")
        worker["command"] = [
            "-m",
            "celery",
            "-A",
            projects[app] + ".celery_app",
            "worker",
            "-B",
            "--concurrency=1",
            "--loglevel=WARNING",
            "--schedule=/tmp/suite-celerybeat",
        ]
        services[app + "-sync"] = worker
        frontend_app = {"drive": "drive", "people": "desk", "docs": "impress"}.get(app)
        modules = app + "-frontend-modules"
        volumes[modules] = {}
        frontend_volumes = [
            f"{repo}/src/frontend:/home/frontend",
            f"{modules}:/home/frontend/node_modules",
        ]
        if frontend_app:
            app_modules = app + "-frontend-app-modules"
            volumes[app_modules] = {}
            frontend_volumes.append(
                f"{app_modules}:/home/frontend/apps/{frontend_app}/node_modules"
            )
        frontend_image = {
            "drive": "drive:frontend-development",
            "st": "st-deploycenter-frontend-dev:latest",
        }.get(app, f"apoze/{app}:identity-frontend-dev")
        services[app + "-frontend"] = {
            "image": frontend_image,
            "user": "0:0",
            "command": ["yarn", "dev"],
            "ports": [f"{host}:{port + 10}:3000"],
            "environment": {
                "NEXT_PUBLIC_API_ORIGIN": origin,
                "DEV_ALLOWED_ORIGINS": host,
                "NEXT_PUBLIC_CSRF_COOKIE_NAME": f"suite_qa_{app}_csrf",
                "NEXT_TELEMETRY_DISABLED": "1",
                "NEXT_PUBLIC_SW_DEACTIVATED": "true",
            },
            "volumes": frontend_volumes,
        }
    collaboration_key = target / "collaboration.key"
    collaboration_key.write_text(secret["collaboration"])
    for name in ("docs", "docs-sync"):
        services[name]["environment"].update(
            {
                "MEDIA_BASE_URL": f"http://{host}:19124",
                "COLLABORATION_API_URL": "http://docs-collaboration:4444/collaboration/api/",
                "COLLABORATION_WS_URL": f"ws://{host}:19144/collaboration/ws/",
                "COLLABORATION_SERVER_SECRET_FILE": "/run/collaboration.key",
                "Y_PROVIDER_API_KEY_FILE": "/run/collaboration.key",
                "Y_PROVIDER_API_BASE_URL": "http://docs-collaboration:4444",
                "COLLABORATION_WS_NOT_CONNECTED_READ_ONLY": "true",
            }
        )
        services[name]["volumes"].append(
            f"{collaboration_key}:/run/collaboration.key:ro"
        )
    volumes.update({"collaboration-modules": {}, "collaboration-app-modules": {}})
    services["docs-media"] = {
        "image": "nginx:1.30.4-alpine",
        "ports": [f"{host}:19124:8083"],
        "environment": {
            "DOCS_API_ENDPOINT": "http://docs:8000",
            "DOCS_API_HOST": "docs",
            "DOCS_S3_ENDPOINT": "http://s3:8333",
            "DOCS_S3_HOST": "s3:8333",
            "DOCS_S3_BUCKET": "docs",
            "DOCS_UI_ORIGIN": f"http://{host}:19114",
            "NGINX_ENVSUBST_FILTER": "^DOCS_",
        },
        "volumes": [
            f"{Path(docs).resolve()}/docker/suite/media.nginx.conf.template:/etc/nginx/templates/default.conf.template:ro"
        ],
        "depends_on": ["docs", "s3"],
    }
    services["docs-collaboration"] = {
        "image": "apoze/docs:identity-collaboration-dev",
        "user": "0:0",
        "ports": [f"{host}:19144:4444"],
        "environment": {
            "COLLABORATION_BACKEND_BASE_URL": "http://docs:8000",
            "COLLABORATION_SERVER_ORIGIN": f"http://{host}:19114",
            "COLLABORATION_SERVER_SECRET_FILE": "/run/collaboration.key",
            "Y_PROVIDER_API_KEY_FILE": "/run/collaboration.key",
            "DOCS_SESSION_COOKIE_NAME": "suite_qa_docs_session",
            "SUITE_IDENTITY_ENABLED": str(enable_identity).lower(),
        },
        "volumes": [
            f"{Path(docs).resolve()}/src/frontend:/home/frontend",
            "collaboration-modules:/home/frontend/node_modules",
            "collaboration-app-modules:/home/frontend/servers/y-provider/node_modules",
            f"{collaboration_key}:/run/collaboration.key:ro",
        ],
    }
    compose = {"name": "suite-identity-qa", "services": services, "volumes": volumes}
    (target / "compose.json").write_text(json.dumps(compose, indent=2))
    for file in target.iterdir():
        if file.is_file():
            file.chmod(0o600)
    # Container processes are unprivileged; the host parent stays private to root.
    for filename in ("realm.json", "s3.json"):
        os.chown(target / filename, 1000, 1000)
    return target / "compose.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--people", default="/root/Apoze/people")
    parser.add_argument("--docs", default="/root/Apoze/docs")
    parser.add_argument(
        "--st", default="/root/Apoze/st-deploycenter-worktrees/suite-identity-access"
    )
    parser.add_argument(
        "--enable-identity",
        action="store_true",
        help="Activate after explicit identity associations and initial synchronization",
    )
    parser.add_argument("--idp", choices=("keycloak", "authentik"), default="keycloak")
    args = parser.parse_args()
    os.umask(0o077)
    location = prepare(
        args.host, args.people, args.docs, args.st, args.enable_identity, args.idp
    )
    parser.exit(message=f"Private qualification configuration prepared: {location}\n")
