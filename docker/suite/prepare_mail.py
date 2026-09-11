"""Prepare the Messages/Calendars LAN project without changing the running suite."""

import argparse
import base64
import ipaddress
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit
from urllib.request import urlopen

from prepare_local import environment, write_private
from prepare_documents import update_environment


def oidc_discovery(issuer):
    parsed = urlsplit(issuer)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('An explicit HTTP(S) OIDC issuer is required')
    with urlopen(issuer.rstrip('/') + '/.well-known/openid-configuration', timeout=5) as response:
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError('OIDC discovery exceeds 1 MiB')
    discovery = json.loads(data)
    if discovery.get('issuer') != issuer:
        raise ValueError('OIDC discovery issuer mismatch')
    return discovery


def prepare(state, suite_path, repo_parent):
    """Keep persistent credentials stable and generate one explicit Compose project."""
    os.umask(0o077)
    state = state.resolve()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    installation = json.loads(suite_path.read_text())
    identity = {key: installation[key] for key in ("host", "issuer", "organization_id")}
    ipaddress.ip_address(identity["host"])
    path = state / "settings.json"
    if path.exists():
        config = json.loads(path.read_text())
        if any(config.get(key) != value for key, value in identity.items()):
            raise ValueError("Existing identity differs; use an explicit migration")
    else:
        config = identity | {
            "mail_domain": "mail.apoze.test",
            "caldav_db_password": secrets.token_urlsafe(40),
            "mda_key": secrets.token_urlsafe(40),
            "caldav_inbound_key": secrets.token_urlsafe(40),
            "caldav_outbound_key": secrets.token_urlsafe(40),
            "caldav_internal_key": secrets.token_urlsafe(40),
            "blob_key": base64.b64encode(secrets.token_bytes(32)).decode(),
            "s3": {key: secrets.token_urlsafe(40) for key in ("access_key", "secret_key")},
            "apps": {},
        }
        for app, port in (("messages", 8900), ("calendars", 8930)):
            config["apps"][app] = {
                key: secrets.token_urlsafe(40)
                for key in ("db_password", "django_secret", "client_secret",
                            "read_key", "mutation_key", "policy_key", "recovery_password")
            } | {"port": port, "client_id": "apoze-" + app, "policy_service_id": ""}
        write_private(path, json.dumps(config, indent=2))
    issuers = {app: values.get('issuer', config['issuer']) for app, values in config['apps'].items()}
    discoveries = {issuer: oidc_discovery(issuer) for issuer in set(issuers.values())}
    if "messages_calendar_key" not in config:
        config["messages_calendar_key"] = "msgk_" + secrets.token_urlsafe(32)
        write_private(path, json.dumps(config, indent=2))
    host = config["host"]
    if "drive_files_keys" not in config:
        config["drive_files_keys"] = {purpose: secrets.token_urlsafe(48) for purpose in ("read", "mutation")}
        write_private(path, json.dumps(config, indent=2))
    drive_env = {"MESSAGES_PUBLIC_URL": f"http://{host}:8900",
                 "SUITE_DELEGATION_PEER_ISSUERS": issuers['messages']}
    for purpose, value in config["drive_files_keys"].items():
        drive_key = repo_parent / "drive/data/storage-secrets/messages-files" / purpose
        write_private(drive_key, value, uid=1000)
        os.chown(drive_key.parent, 1000, 1000)
        write_private(state / "messages/keys" / ("drive_" + purpose), value, uid=1000)
        drive_env[f"MESSAGES_FILES_{purpose.upper()}_KEY_FILE"] = f"/run/storage-secrets/messages-files/{purpose}"
    update_environment(repo_parent / "drive/env.d/development/common.local", drive_env)
    docs_env = suite_path.parent / 'docs/backend.env'
    if docs_env.is_file():
        update_environment(docs_env, {'SUITE_DELEGATION_PEER_ISSUERS': issuers['messages']})
    if "calendar_messages_token" not in config:
        config["calendar_messages_token"] = secrets.token_urlsafe(32)
        write_private(path, json.dumps(config, indent=2))
    services = {
        "redis": {
            "image": "redis:7.4-alpine", "restart": "unless-stopped",
            "command": ["redis-server", "--appendonly", "yes", "--maxmemory", "256mb",
                        "--maxmemory-policy", "noeviction"],
            "volumes": ["mail-redis:/data"], "networks": ["default"],
            "healthcheck": {"test": ["CMD", "redis-cli", "ping"], "interval": "5s"},
        },
        "opensearch": {
            "image": "opensearchproject/opensearch:2.19.2@sha256:69588c664014fa3d3260ed5dd337f8538fec94790dad00bfbe92301eaaaac240",
            "restart": "unless-stopped", "mem_limit": "1536m",
            "environment": {"discovery.type": "single-node", "OPENSEARCH_JAVA_OPTS": "-Xms512m -Xmx512m",
                            "DISABLE_INSTALL_DEMO_CONFIG": "true", "DISABLE_SECURITY_PLUGIN": "true"},
            "volumes": ["mail-search:/usr/share/opensearch/data"], "networks": ["default"],
        },
        "mail-s3": {
            "image": "chrislusf/seaweedfs:4.46", "restart": "unless-stopped",
            "command": ["server", "-dir=/data", "-s3", "-s3.config=/etc/seaweedfs/s3.json",
                        "-volume.max=32", "-master.volumeSizeLimitMB=1024", "-ip=mail-s3"],
            "volumes": ["mail-s3:/data", f"{state}/s3.json:/etc/seaweedfs/s3.json:ro"],
            "networks": ["default"],
            "healthcheck": {"test": ["CMD", "nc", "-z", "mail-s3", "8333"],
                            "interval": "3s", "timeout": "2s", "retries": 30},
        },
    }
    rspamd = state / "rspamd"
    rspamd.mkdir(exist_ok=True)
    rspamd.chmod(0o755)
    for module in ("spf", "dkim", "dmarc", "rbl", "surbl", "fuzzy_check", "reputation", "asn", "url_redirector", "external_services", "ratelimit", "greylist"):
        file = rspamd / (module + ".conf")
        file.write_text("enabled = false;\n")
        file.chmod(0o644)
    for name, content in {
        "redis.conf": 'servers = "redis:6379"; db = "7";\n',
        "worker-controller.inc": 'enabled = false;\n',
        "worker-proxy.inc": 'enabled = false;\n',
        "worker-normal.inc": 'count = 1; allow_file_and_shm_inputs = false;\n',
        "logging.inc": 'level = "warning"; log_re_cache = false;\n',
    }.items():
        file = rspamd / name
        file.write_text(content)
        file.chmod(0o644)
    services["rspamd"] = {
        "image": "rspamd/rspamd:4.1.5@sha256:c307774c4c83bc445f0ae6696fd1798c92b0b89355ae1d87c9c39694c875e51e",
        "restart": "unless-stopped", "mem_limit": "768m", "networks": ["default"],
        "environment": {"RSPAMD_PORT_CONTROLLER": "11333"},
        "volumes": [f"{rspamd}:/etc/rspamd/local.d:ro", "mail-rspamd:/var/lib/rspamd"],
    }
    services["clamav"] = {
        "image": "clamav/clamav@sha256:1fdfd24c6f0a0fb60788481487459a6d4eda8a9b448641594e04db8410d34422",
        "restart": "unless-stopped", "mem_limit": "3g", "networks": ["default"],
        "volumes": ["mail-clamav:/var/lib/clamav"],
        "environment": {"CLAMAV_NO_MILTERD": "true", "FRESHCLAM_CHECKS": "12",
                        "CLAMD_CONF_StreamMaxLength": "64M",
                        "CLAMD_CONF_MaxFileSize": "64M", "CLAMD_CONF_MaxScanSize": "128M",
                        "CLAMD_CONF_AlertExceedsMax": "yes", "CLAMD_CONF_MaxThreads": "2"},
    }
    write_private(state / "s3.json", json.dumps({"identities": [{
        "name": "messages", "credentials": [{"accessKey": config["s3"]["access_key"],
                                                 "secretKey": config["s3"]["secret_key"]}],
        "actions": ["Admin", "Read", "Write", "List", "Tagging"],
    }]}), uid=1000)
    for index, (app, values) in enumerate(config["apps"].items()):
        discovery = discoveries[issuers[app]]
        if "encryption_salt" not in values:
            values["encryption_salt"] = secrets.token_urlsafe(40)
            write_private(path, json.dumps(config, indent=2))
        repo = repo_parent / app
        origin = f"http://{host}:{values['port']}"
        private = state / app
        private.mkdir(exist_ok=True)
        for key in ("read_key", "mutation_key", "policy_key", "recovery_password"):
            write_private(private / "keys" / key, values[key], uid=1000)
        os.chown(private / "keys", 1000, 1000)
        env = {
            "DJANGO_SETTINGS_MODULE": f"{app}.settings", "DJANGO_CONFIGURATION": "Suite",
            "DJANGO_SECRET_KEY": values["django_secret"],
            "SALT_KEY": values["encryption_salt"],
            "DJANGO_ALLOWED_HOSTS": f"{host},127.0.0.1,localhost,{app},suite-mail-{app}-1",
            "DJANGO_CSRF_TRUSTED_ORIGINS": origin,
            "DB_HOST": "suite-postgres", "DB_NAME": app, "DB_USER": app,
            "DB_PASSWORD": values["db_password"],
            "REDIS_URL": f"redis://redis:6379/{index + 2}",
            "CELERY_BROKER_URL": "redis://redis:6379/0",
            "OIDC_RP_CLIENT_ID": values["client_id"], "OIDC_RP_CLIENT_SECRET": values["client_secret"],
            "OIDC_RP_SCOPES": "openid email profile", "OIDC_AUTH_REQUEST_EXTRA_PARAMS": '{"max_age":900}',
            "OIDC_REDIRECT_ALLOWED_HOSTS": f"{host}:{values['port']}",
            "LOGIN_REDIRECT_URL": origin, "LOGIN_REDIRECT_URL_FAILURE": origin,
            "LOGOUT_REDIRECT_URL": origin, "APP_URL": origin,
            "SUITE_OIDC_ISSUER": issuers[app], "SUITE_ORGANIZATION_ID": config["organization_id"],
            "SUITE_DELEGATION_PEER_ISSUERS": ','.join(sorted(set(issuers.values()) | {installation['issuer']})),
            "SUITE_DIRECTORY_URL": f"http://{host}:8072/api/v1.0/suite-directory/",
            "SUITE_DIRECTORY_TOKEN_FILE": "/run/suite/read_key",
            "SUITE_POLICY_URL": f"http://{host}:8961/api/v1.0/suite-policy/",
            "SUITE_POLICY_TOKEN_FILE": "/run/suite/policy_key",
            "SUITE_POLICY_SERVICE_ID": values["policy_service_id"],
            "SUITE_CATALOGUE_URL": f"http://{host}:8961/api/v1.0/suite-catalogue/",
            "SUITE_LOGOUT_URL": f"http://{host}:8072/api/v1.0/suite-revoke-sessions/",
            "SUITE_LOGOUT_TOKEN_FILE": "/run/suite/mutation_key",
            "SUITE_IDENTITY_REQUEST_URL": f"http://{host}:8072/api/v1.0/suite-identity-requests/",
            "EMAIL_HOST": "mta-in", "EMAIL_PORT": "25",
            "DEFAULT_FROM_EMAIL": "notifications@" + config["mail_domain"],
        }
        for setting, field in {"AUTHORIZATION": "authorization_endpoint", "TOKEN": "token_endpoint",
                               "USER": "userinfo_endpoint", "JWKS": "jwks_uri",
                               "LOGOUT": "end_session_endpoint"}.items():
            env["OIDC_OP_" + setting + "_ENDPOINT"] = discovery.get(field, "")
        if app == "messages":
            env |= {"MDA_API_SECRET": config["mda_key"], "MTA_OUT_MODE": "relay",
                    "MTA_OUT_RELAY_HOST": "mta-in:25", "MTA_OUT_SMTP_TLS_SECURITY_LEVEL": "none",
                    "AWS_S3_DOMAIN_REPLACE": f"http://{host}:8900",
                    "OPENSEARCH_URL": "http://opensearch:9200", "MESSAGES_TECHNICAL_DOMAIN": config["mail_domain"],
                    "MESSAGES_BLOBS_ENCRYPT_KEYS": json.dumps({"1": {"algo": "aes-gcm", "secret": config["blob_key"], "active": True}}),
                    "CALDAV_DEFAULT_WEB_URL": f"http://{host}:8930", "SUITE_MAIL_LAN_DOMAIN": config["mail_domain"],
                    "FEATURE_AI_SUMMARY": "false", "FEATURE_AI_AUTOLABELS": "false"}
            if config.get("projects_notifications_key"):
                write_private(private / "keys/projects_notifications", config["projects_notifications_key"], uid=1000)
                env |= {"PROJECTS_NOTIFICATIONS_KEY_FILE": "/run/suite/projects_notifications",
                        "PROJECTS_PUBLIC_URL": f"http://{host}:8940"}
            if config.get("calendar_messages_credentials"):
                env |= {"CALDAV_DEFAULT_URL": "http://calendars:8000/caldav/",
                        "CALDAV_DEFAULT_PASSWORD": config["calendar_messages_credentials"]}
            if config.get("transfers_notifications_key"):
                write_private(private / "keys/transfers_notifications", config["transfers_notifications_key"], uid=1000)
                env |= {"TRANSFERS_NOTIFICATIONS_KEY_FILE": "/run/suite/transfers_notifications",
                        "TRANSFERS_PUBLIC_URL": config["transfers_public_url"]}
            for storage, bucket in (("IMPORTS", "messages-imports"), ("BLOBS", "messages-blobs")):
                prefix = "STORAGE_MESSAGE_" + storage
                env |= {prefix + "_ENDPOINT_URL": "http://mail-s3:8333", prefix + "_BUCKET_NAME": bucket,
                        prefix + "_ACCESS_KEY": config["s3"]["access_key"], prefix + "_SECRET_KEY": config["s3"]["secret_key"]}
            env |= {"SUITE_AV_HOST": "clamav",
                    "SPAM_CONFIG": json.dumps({"rspamd_url": "http://rspamd:11333"}),
                    "DRIVE_BASE_URL": f"http://{host}:3000", "DRIVE_FILES_API_URL": f"http://{host}:8071",
                    "DRIVE_FILES_READ_KEY_FILE": "/run/suite/drive_read",
                    "DRIVE_FILES_MUTATION_KEY_FILE": "/run/suite/drive_mutation"}
        else:
            if config.get("chat_context_key"):
                write_private(private / "keys/chat_context", config["chat_context_key"], uid=1000)
                write_private(private / "keys/chat_status", config["chat_status_key"], uid=1000)
                env |= {"SUITE_CHAT_CONTEXT_URL": config["chat_context_url"],
                        "SUITE_CHAT_CONTEXT_KEY_FILE": "/run/suite/chat_context",
                        "SUITE_CHAT_STATUS_KEY_FILE": "/run/suite/chat_status"}
            env |= {"CALDAV_URL": "http://caldav", "CALDAV_INBOUND_API_KEY": config["caldav_inbound_key"],
                    "CALDAV_OUTBOUND_API_KEY": config["caldav_outbound_key"], "CALDAV_INTERNAL_API_KEY": config["caldav_internal_key"],
                    "ORG_DEFAULT_SHARING_LEVEL": "none", "FRONTEND_MEET_BASE_URL": f"https://{host}:8443",
                    "TRANSLATIONS_JSON_PATH": "/data/i18n/translations.json", "CALENDAR_ITIP_ENABLED": "true"}
            if config.get("messages_calendar_channel_id"):
                env |= {"FEATURE_MESSAGES_INTEGRATION": "true", "MESSAGES_API_URL": "http://messages:8000",
                        "MESSAGES_CHANNEL_ID": config["messages_calendar_channel_id"],
                        "MESSAGES_API_KEY": config["messages_calendar_key"]}
        environment(private / "backend.env", env)
        base = {
            "image": f"apoze/{app}:suite-dev", "restart": "unless-stopped", "user": "1000:1000",
            "working_dir": "/app", "env_file": [str(private / "backend.env")],
            "volumes": [f"{repo}/src/backend:/app", f"{private}/keys:/run/suite:ro"],
            "networks": ["default", "suite"], "mem_limit": "1g",
        }
        if app == "calendars":
            base["volumes"] += [f"{repo}/src/frontend/src/features/i18n:/data/i18n:ro"]
        services[app] = base | {"command": ["gunicorn", f"{app}.wsgi:application", "--bind", "0.0.0.0:8000",
                                           "--workers", "2", "--threads", "2", "--timeout", "60"]}
        services[app + "-worker"] = base | {"command": ["python", "worker.py", "--concurrency=2"]}
        if app == "calendars":
            services[app + "-reconcile"] = base | {
                "command": ["python", "manage.py", "suite_reconcile"], "mem_limit": "256m"}
        services[app + "-frontend"] = {
            "image": f"apoze/{app}:suite-frontend", "restart": "unless-stopped",
            "ports": [f"{host}:{values['port']}:8080"],
            "environment": {"PORT": "8080", "MESSAGES_IMPORTS_BUCKET": "messages-imports",
                            "MESSAGES_IMPORTS_S3_SERVER": "mail-s3:8333", "MESSAGES_FRONTEND_BACKEND_SERVER": "messages:8000",
                            "MESSAGES_FRONTEND_TRUSTED_PROXIES": "127.0.0.1/32", "MESSAGES_FRONTEND_SCHEME": "http",
                            "CALENDARS_BACKEND_SERVER": "calendars:8000"}, "networks": ["default"],
        }
    environment(state / "caldav.env", {
        "PGHOST": "suite-postgres", "PGDATABASE": "caldav", "PGUSER": "caldav", "PGPASSWORD": config["caldav_db_password"],
        "CALDAV_OUTBOUND_API_KEY": config["caldav_outbound_key"], "CALDAV_INTERNAL_API_KEY": config["caldav_internal_key"],
        "CALDAV_INBOUND_API_KEY": config["caldav_inbound_key"], "CALDAV_CALLBACK_BASE_URL": "http://calendars:8000",
        "CALDAV_BASE_URI": "/caldav/", "SUITE_IDENTITY_ENABLED": "true",
    })
    services["caldav"] = {"image": "apoze/calendars:suite-dav", "restart": "unless-stopped",
                           "env_file": [str(state / "caldav.env")], "networks": ["default", "suite"], "mem_limit": "512m"}
    services["caldav"]["volumes"] = [
        f"{repo_parent}/calendars/src/caldav/src:/var/www/sabredav/src:ro",
        f"{repo_parent}/calendars/src/caldav/sql:/var/www/sabredav/sql:ro",
        f"{repo_parent}/calendars/src/caldav/init-database.sh:/usr/local/bin/init-database.sh:ro",
    ]
    services["caldav"]["command"] = ["sh", "-ec", "init-database.sh && exec apache2-foreground"]
    environment(state / "mta.env", {
        "MYHOSTNAME": "mx." + config["mail_domain"], "MYDOMAIN": config["mail_domain"],
        "MYORIGIN": config["mail_domain"], "MDA_API_BASE_URL": "http://messages:8000/api/v1.0/",
        "MDA_API_SECRET": config["mda_key"], "MAX_INCOMING_EMAIL_SIZE": "26214400",
    })
    services["mta-in"] = {"image": "apoze/messages:suite-mta", "restart": "unless-stopped",
                           "env_file": [str(state / "mta.env")], "networks": ["default"], "mem_limit": "512m"}
    compose = {"name": "suite-mail", "services": services,
               "networks": {"default": {}, "suite": {"external": True, "name": "suite-local_default"}},
               "volumes": {name: {} for name in ("mail-redis", "mail-search", "mail-s3", "mail-rspamd", "mail-clamav")}}
    write_private(state / "compose.json", json.dumps(compose, indent=2))
    return config


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--suite-settings", type=Path, required=True)
    parser.add_argument("--repos", type=Path, default=Path("/root/Apoze"))
    args = parser.parse_args()
    prepare(args.state, args.suite_settings, args.repos)
    print("Mail LAN configuration prepared; no service was started.")
