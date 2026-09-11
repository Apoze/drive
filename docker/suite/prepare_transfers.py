"""Prepare a private, persistent Transfers deployment alongside the suite."""

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
from urllib.parse import quote, urlsplit
from urllib.request import urlopen

from prepare_local import environment, write_private
from prepare_mail import update_environment


def prepare_tls(state, host):
    """Create a LAN CA only for this installation; never replace existing keys."""
    tls = state / 'tls'
    tls.mkdir(mode=0o700, exist_ok=True)
    if (tls / 'server.crt').exists() and (tls / 'server.key').exists():
        return
    if any(tls.iterdir()):
        raise ValueError('Incomplete TLS directory; recover it before generating keys')
    commands = [
        ['req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-days', '3650',
         '-subj', '/CN=Apoze Transfers LAN CA', '-keyout', 'ca.key', '-out', 'ca.crt',
         '-addext', 'basicConstraints=critical,CA:TRUE',
         '-addext', 'keyUsage=critical,keyCertSign,cRLSign'],
        ['req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=' + host,
         '-keyout', 'server.key', '-out', 'server.csr'],
        ['x509', '-req', '-in', 'server.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key',
         '-CAcreateserial', '-out', 'server.crt', '-days', '365', '-extfile', 'server.ext'],
    ]
    write_private(tls / 'server.ext',
                  f'subjectAltName=IP:{host}\nextendedKeyUsage=serverAuth\n'
                  'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n')
    for arguments in commands:
        result = subprocess.run(['openssl', *arguments], cwd=tls, capture_output=True)
        if result.returncode:
            raise RuntimeError('TLS generation failed; partial files retained privately')


def prepare(state, suite_path, repo):
    os.umask(0o077)
    state = state.resolve()
    suite = json.loads(suite_path.read_text())
    identity = {name: suite[name] for name in ('host', 'issuer', 'organization_id')}
    path = state / 'settings.json'
    if path.exists():
        config = json.loads(path.read_text())
        if any(config.get(name) != value for name, value in identity.items()):
            raise ValueError('Existing Transfers identity differs; migrate explicitly')
    else:
        config = identity | {name: secrets.token_urlsafe(40) for name in (
            'db_password', 'session_secret', 'client_secret', 'read_key',
            'mutation_key', 'policy_key', 's3_access', 's3_secret')}
        config.update(port=8950, s3_port=8952, client_id='apoze-transfers',
                      policy_service_id='', bucket='transfers')
        config['origin'] = f"https://{config['host']}:{config['port']}"
        write_private(path, json.dumps(config, indent=2) + '\n')
    if 'messages_key' not in config:
        config['messages_key'] = secrets.token_urlsafe(48)
        write_private(path, json.dumps(config, indent=2) + '\n')
    if 'drive_keys' not in config:
        config['drive_keys'] = {purpose: secrets.token_urlsafe(48) for purpose in ('read', 'mutation')}
        write_private(path, json.dumps(config, indent=2) + '\n')
    drive_repo = Path(__file__).resolve().parents[2]
    intake = drive_repo / 'data/transfer-intakes'
    intake.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chown(intake, 1000, 0)
    intake.chmod(0o700)
    drive_env = {'TRANSFERS_PUBLIC_URL': config['origin']}
    for purpose, key in config['drive_keys'].items():
        target = drive_repo / 'data/storage-secrets/transfers-files' / purpose
        write_private(target, key, uid=1000)
        os.chown(target.parent, 1000, 1000)
        write_private(state / 'keys' / ('drive_' + purpose), key, uid=1000)
        drive_env[f'TRANSFERS_FILES_{purpose.upper()}_KEY_FILE'] = f'/run/storage-secrets/transfers-files/{purpose}'
    update_environment(drive_repo / 'env.d/development/common.local', drive_env)
    mail_state = suite_path.parent.parent / 'messages-calendars-local'
    mail_settings = json.loads((mail_state / 'settings.json').read_text())
    if mail_settings.get('transfers_notifications_key') not in (None, config['messages_key']):
        raise ValueError('Messages sender credential conflict')
    mail_settings['transfers_notifications_key'] = config['messages_key']
    mail_settings['transfers_public_url'] = config['origin']
    write_private(mail_state / 'settings.json', json.dumps(mail_settings, indent=2) + '\n')
    write_private(mail_state / 'messages/keys/transfers_notifications', config['messages_key'], uid=1000)
    write_private(state / 'keys/messages_notifications', config['messages_key'], uid=1000)
    update_environment(mail_state / 'messages/backend.env', {
        'TRANSFERS_NOTIFICATIONS_KEY_FILE': '/run/suite/transfers_notifications',
        'TRANSFERS_PUBLIC_URL': config['origin'],
    })
    with urlopen(config['issuer'] + '/.well-known/openid-configuration', timeout=10) as response:
        discovery = json.load(response)
    if discovery.get('issuer') != config['issuer']:
        raise ValueError('OIDC discovery issuer mismatch')
    for name in ('read_key', 'mutation_key', 'policy_key'):
        write_private(state / 'keys' / name, config[name], uid=1000)
    os.chown(state / 'keys', 1000, 1000)
    host = config['host']
    prepare_tls(state, host)
    settings = {
        'DJANGO_CONFIGURATION': 'Suite', 'DJANGO_SECRET_KEY': config['session_secret'],
        'DJANGO_ALLOWED_HOSTS': host + ',localhost,transfers',
        'DJANGO_CSRF_TRUSTED_ORIGINS': config['origin'],
        'DATABASE_URL': 'postgresql://transfers:' + quote(config['db_password'], safe='') + '@suite-postgres:5432/transfers',
        'REDIS_URL': 'redis://suite-redis:6379/12',
        'CELERY_BROKER_URL': 'redis://suite-redis:6379/12',
        'SUITE_IDENTITY_ENABLED': 'true', 'SUITE_APP_ID': 'transfers',
        'SUITE_OIDC_ISSUER': config['issuer'],
        'SUITE_ORGANIZATION_ID': config['organization_id'],
        'SUITE_DIRECTORY_URL': f'http://{host}:8072/api/v1.0/suite-directory/',
        'SUITE_IDENTITY_REQUEST_URL': f'http://{host}:8072/api/v1.0/suite-identity-requests/',
        'SUITE_LOGOUT_URL': f'http://{host}:8072/api/v1.0/suite-revoke-sessions/',
        'SUITE_POLICY_URL': f'http://{host}:8961/api/v1.0/suite-policy/',
        'SUITE_CATALOGUE_URL': f'http://{host}:8961/api/v1.0/suite-catalogue/',
        'SUITE_DIRECTORY_TOKEN_FILE': '/run/suite/read_key',
        'SUITE_LOGOUT_TOKEN_FILE': '/run/suite/mutation_key',
        'SUITE_POLICY_TOKEN_FILE': '/run/suite/policy_key',
        'SUITE_POLICY_SERVICE_ID': config['policy_service_id'],
        'OIDC_RP_CLIENT_ID': config['client_id'],
        'OIDC_RP_CLIENT_SECRET': config['client_secret'],
        'OIDC_RP_SCOPES': 'openid profile email', 'OIDC_CREATE_USER': 'false',
        'OIDC_FALLBACK_TO_EMAIL_FOR_IDENTIFICATION': 'false',
        'LOGIN_REDIRECT_URL': config['origin'],
        'LOGIN_REDIRECT_URL_FAILURE': config['origin'],
        'LOGOUT_REDIRECT_URL': config['origin'],
        'AWS_S3_ENDPOINT_URL': suite['s3']['endpoint'],
        'AWS_S3_DOMAIN_REPLACE': f'https://{host}:{config["s3_port"]}',
        'AWS_S3_ACCESS_KEY_ID': config['s3_access'],
        'AWS_S3_SECRET_ACCESS_KEY': config['s3_secret'],
        'AWS_STORAGE_BUCKET_NAME': config['bucket'],
        'AWS_S3_REGION_NAME': 'us-east-1',
        'TRANSFER_PRESIGNED_URL_EXPIRY': 60,
        'CLAMAV_SCAN_ENABLED': 'true', 'SUITE_CLAMAV_HOST': 'clamav',
        'SCAN_MAX_FILE_SIZE': 60 * 1024 * 1024,
        'DJANGO_EMAIL_FROM': 'transfers@' + mail_settings['mail_domain'],
        'SUITE_MAIL_LAN_DOMAIN': mail_settings['mail_domain'],
        'SUITE_MESSAGES_NOTIFICATIONS_URL': 'http://messages:8000/api/v1.0/internal/transfers/notifications/',
        'SUITE_MESSAGES_NOTIFICATIONS_KEY_FILE': '/run/suite/messages_notifications',
        'SUITE_DRIVE_FILES_URL': f'http://{host}:8071/api/v1.0/internal/transfers/',
        'SUITE_DRIVE_READ_KEY_FILE': '/run/suite/drive_read',
        'SUITE_DRIVE_MUTATION_KEY_FILE': '/run/suite/drive_mutation',
        'DRIVE_BASE_URL': f'http://{host}:3000', 'DRIVE_SDK_URL': '/sdk/transfers',
    }
    for setting, key in {
        'OIDC_OP_AUTHORIZATION_ENDPOINT': 'authorization_endpoint',
        'OIDC_OP_TOKEN_ENDPOINT': 'token_endpoint',
        'OIDC_OP_USER_ENDPOINT': 'userinfo_endpoint',
        'OIDC_OP_JWKS_ENDPOINT': 'jwks_uri',
        'OIDC_OP_LOGOUT_ENDPOINT': 'end_session_endpoint',
    }.items():
        value = discovery.get(key, '')
        if not value and key != 'end_session_endpoint':
            raise ValueError('Incomplete OIDC discovery')
        settings[setting] = value
    environment(state / 'backend.env', settings)
    backend = {
        'image': 'apoze/transfers-backend:suite-local',
        'build': {'context': str(repo.resolve() / 'src/backend'),
                  'target': 'runtime-prod', 'args': {'DOCKER_USER': '1000'}},
        'restart': 'unless-stopped', 'init': True, 'mem_limit': '768m',
        'env_file': [str(state / 'backend.env')],
        'volumes': [f'{state}/keys:/run/suite:ro'],
        'networks': ['suite', 'storage', 'mail', 'default'],
    }
    services = {'transfers': backend}
    for name, command, memory in (
        ('worker', ['celery', '-A', 'transferts.celery_app', 'worker', '-l', 'WARNING', '--concurrency=1'], '768m'),
        ('beat', ['celery', '-A', 'transferts.celery_app', 'beat', '-l', 'WARNING'], '256m'),
    ):
        services[name] = {**backend, 'command': command, 'mem_limit': memory,
                          'healthcheck': {'disable': True}}
    services['frontend'] = {
        'image': 'apoze/transfers-frontend:suite-local',
        'build': {'context': str(repo.resolve() / 'src/frontend'), 'target': 'runtime-prod'},
        'restart': 'unless-stopped', 'mem_limit': '128m',
        'environment': {'TRANSFERTS_FRONTEND_BACKEND_SERVER': 'transfers:8000',
                        'TRANSFERTS_FRONTEND_HSTS': 'max-age=86400',
                        'TRANSFERTS_FRONTEND_S3_ORIGIN': f'https://{host}:{config["s3_port"]}'},
    }
    storage = urlsplit(suite['s3']['endpoint']).netloc
    write_private(state / 'nginx.conf', f'''events {{}}
http {{
 access_log off;
 resolver 127.0.0.11 valid=10s ipv6=off;
 server {{
  listen 8443 ssl;
  ssl_certificate /run/tls/server.crt;
  ssl_certificate_key /run/tls/server.key;
  set $frontend frontend:8080;
  location / {{
   proxy_pass http://$frontend;
   proxy_set_header Host $http_host;
   proxy_set_header X-Forwarded-Proto https;
   proxy_set_header X-Forwarded-For $remote_addr;
  }}
 }}
 server {{
  listen 8444 ssl;
  ssl_certificate /run/tls/server.crt;
  ssl_certificate_key /run/tls/server.key;
  client_max_body_size 26m;
  location /transfers/ {{
   proxy_pass http://{storage};
   proxy_hide_header Access-Control-Expose-Headers;
   add_header Access-Control-Expose-Headers "ETag, Content-Range, Accept-Ranges" always;
   proxy_set_header Host $http_host;
   proxy_request_buffering off;
   proxy_buffering off;
   proxy_read_timeout 300s;
  }}
  location / {{ return 404; }}
 }}
}}
''')
    services['edge'] = {
        'image': 'nginx:1.28.0-alpine', 'restart': 'unless-stopped',
        'mem_limit': '64m', 'ports': [f'{host}:{config["port"]}:8443', f'{host}:{config["s3_port"]}:8444'],
        'volumes': [f'{state}/nginx.conf:/etc/nginx/nginx.conf:ro',
                    f'{state}/tls/server.crt:/run/tls/server.crt:ro',
                    f'{state}/tls/server.key:/run/tls/server.key:ro'],
        'networks': ['default', 'storage'], 'depends_on': ['frontend'],
    }
    write_private(state / 'compose.json', json.dumps({
        'name': 'suite-transfers', 'services': services,
        'networks': {'default': {},
                     'suite': {'external': True, 'name': 'suite-local_default'},
                     'storage': {'external': True, 'name': 'suite-local_docs-storage'},
                     'mail': {'external': True, 'name': 'suite-mail_default'}},
    }, indent=2) + '\n')
    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('data/transfers-local'))
    parser.add_argument('--suite', type=Path, default=Path('data/suite-local/settings.json'))
    parser.add_argument('--repo', type=Path, default=Path('../transfers'))
    args = parser.parse_args()
    prepare(args.state, args.suite, args.repo)
    print('Transfers prepared privately; no services started.')
