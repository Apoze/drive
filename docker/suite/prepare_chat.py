"""Prepare isolated Matrix/Synapse/MAS services without changing the Drive stack."""

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
from urllib.parse import quote
from urllib.request import urlopen

import yaml

from prepare_local import write_private
from prepare_mail import update_environment
from prepare_transfers import prepare_tls

MAS_IMAGE = 'ghcr.io/element-hq/matrix-authentication-service:1.24.0@sha256:52c18ffcc940220a3b6aa5985b7e09d24ac27f5ed10a4d660c312e48f73ff105'


def ulid():
    value = secrets.randbits(128)
    alphabet = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
    return ''.join(alphabet[(value >> shift) & 31] for shift in range(125, -1, -5))


def prepare(state, suite_path, repos, *, server_name, qa=False):
    os.umask(0o077)
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?', server_name) or '.' not in server_name:
        raise ValueError('A stable Matrix DNS name is required')
    if not qa and server_name.endswith(('.test', '.invalid', '.localhost')):
        raise ValueError('A disposable name requires --qa; never use it for durable accounts')
    state, repos = state.resolve(), repos.resolve()
    suite = json.loads(suite_path.read_text())
    identity = {'organization_id': suite['organization_id']}
    identity.update(server_name=server_name, qa=qa)
    path = state / 'settings.json'
    if path.exists():
        config = json.loads(path.read_text())
        if any(config.get(key) != value for key, value in identity.items()):
            raise ValueError('Matrix identity differs; this state must not be renamed or reused')
    else:
        config = identity | {'host': suite['host'], 'issuer': suite['issuer']} | {key: secrets.token_urlsafe(40) for key in (
            'db_password', 'mas_db_password', 'client_secret', 'read_key', 'mutation_key',
            'policy_key', 'mas_admin_secret', 'mas_synapse_secret', 'mas_guard_key')}
        config.update(provider_id=ulid(), mas_admin_id=ulid(), policy_service_id='',
                      client_id='apoze-chat-qa' if qa else 'apoze-chat', port=8954, auth_port=8955,
                      db_name='chat_qa' if qa else 'chat', mas_db_name='mas_qa' if qa else 'mas')
        config['origin'] = f"https://{config['host']}:{config['port']}"
        config['auth_origin'] = f"https://{config['host']}:{config['auth_port']}"
        write_private(path, json.dumps(config, indent=2) + '\n')
    if 'element_client_id' not in config:
        config['element_client_id'] = ulid()
        write_private(path, json.dumps(config, indent=2) + '\n')
    if 'meet_context_key' not in config:
        config['meet_context_key'] = secrets.token_urlsafe(40)
        write_private(path, json.dumps(config, indent=2) + '\n')
    if 'meet_status_key' not in config:
        config['meet_status_key'] = secrets.token_urlsafe(40)
        write_private(path, json.dumps(config, indent=2) + '\n')
    write_private(state / 'keys' / 'meet_context_key', config['meet_context_key'], uid=991)
    write_private(state / 'keys' / 'meet_status_key', config['meet_status_key'], uid=991)
    for key in ('calendars_context_key', 'calendars_status_key'):
        if key not in config:
            config[key] = secrets.token_urlsafe(40)
            write_private(path, json.dumps(config, indent=2) + '\n')
        write_private(state / 'keys' / key, config[key], uid=991)
    for key in ('read_key', 'mutation_key', 'policy_key', 'mas_guard_key', 'mas_admin_secret'):
        write_private(state / 'keys' / key, config[key], uid=991)
    os.chown(state / 'keys', 991, 991)
    for name in ('synapse', 'media'):
        directory = state / name
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chown(directory, 991, 991)
    prepare_tls(state, config['host'])
    seed = state / 'mas-secrets.yaml'
    if not seed.exists():
        result = subprocess.run(['docker', 'run', '--rm', MAS_IMAGE, 'config', 'generate'], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('MAS secret generation failed')
        write_private(seed, result.stdout)
    mas = yaml.safe_load(seed.read_text())
    mas['http'].update(public_base=config['auth_origin'] + '/', issuer=config['auth_origin'] + '/')
    mas['http']['listeners'] = [
        {'name': 'web', 'resources': [{'name': n} for n in ('discovery', 'human', 'oauth', 'compat', 'graphql', 'assets')], 'binds': [{'address': '0.0.0.0:8080'}]},
        {'name': 'internal', 'resources': [{'name': n} for n in ('health', 'adminapi')], 'binds': [{'address': '0.0.0.0:8081'}]},
    ]
    mas['database'] = {'uri': f"postgresql://{config['mas_db_name']}:{quote(config['mas_db_password'], safe='')}@suite-postgres:5432/{config['mas_db_name']}", 'max_connections': 5}
    mas['matrix'] = {'homeserver': server_name, 'endpoint': 'http://synapse:8008/', 'secret': config['mas_synapse_secret']}
    mas['passwords']['enabled'] = False
    mas['clients'] = [{'client_id': config['mas_admin_id'], 'client_auth_method': 'client_secret_basic', 'client_secret': config['mas_admin_secret']}]
    mas['clients'].append({'client_id': config['element_client_id'], 'client_auth_method': 'none', 'redirect_uris': [config['origin'] + '/?no_universal_links=true'], 'post_logout_redirect_uris': [config['origin'] + '/'], 'client_name': 'Apoze Chat Web', 'client_uri': config['origin']})
    mas['policy'] = {'data': {'admin_clients': [config['mas_admin_id']], 'registration': {'banned_usernames': {'regexes': ['.*']}}}}
    mas['upstream_oauth2'] = {'providers': [{
        'id': config['provider_id'], 'issuer': config['issuer'], 'human_name': 'Identité de la suite',
        'client_id': config['client_id'], 'client_secret': config['client_secret'],
        'token_endpoint_auth_method': 'client_secret_basic', 'scope': 'openid profile email', 'pkce_method': 'always',
        'fetch_userinfo': True, 'additional_authorization_parameters': {'max_age': '900'},
        'claims_imports': {'localpart': {'action': 'ignore'}, 'email': {'action': 'ignore'}, 'displayname': {'action': 'ignore'}},
    }]}
    # Native MAS provider declarations can be changed without changing MXIDs.
    # Additional issuers must first be approved in the People consumer UI.
    if 'oidc_providers' in config:
        mas['upstream_oauth2']['providers'] = config['oidc_providers']
    providers = mas['upstream_oauth2']['providers']
    if not isinstance(providers, list) or not 1 <= len(providers) <= 10:
        raise ValueError('Configure one to ten native OIDC providers')
    if len({p['id'] for p in providers}) != len(providers):
        raise ValueError('OIDC provider identifiers must be unique')
    for provider in providers:
        provider['pkce_method'] = 'always'
        provider.setdefault('additional_authorization_parameters', {})['max_age'] = '900'
        provider['fetch_userinfo'] = True
        if provider['issuer'].startswith('http://'):
            # Preserve LAN issuers without disabling signature/issuer checks.
            with urlopen(provider['issuer'].rstrip('/') + '/.well-known/openid-configuration', timeout=10) as response:
                raw = response.read(2 * 1024**2 + 1)
                if len(raw) > 2 * 1024**2:
                    raise ValueError('OIDC discovery exceeds its size limit')
                discovery = json.loads(raw)
            if discovery.get('issuer') != provider['issuer']:
                raise ValueError('OIDC discovery issuer mismatch')
            provider['discovery_mode'] = 'disabled'
            provider.update({key: discovery[key] for key in ('authorization_endpoint', 'token_endpoint', 'userinfo_endpoint', 'jwks_uri')})
    write_private(state / 'mas.yaml', json.dumps(mas, indent=2) + '\n', uid=991)
    host = config['host']
    meet_path = suite_path.parent.parent / 'meet-local/settings.json'
    if meet_path.exists():
        meet = json.loads(meet_path.read_text())
        if meet.get('chat_origin') not in (None, '', config['origin']):
            raise ValueError('Meet is already registered to another Chat origin')
        meet.update(chat_origin=config['origin'], chat_context_key=config['meet_context_key'],
                    chat_status_key=config['meet_status_key'],
                    chat_context_url=f"http://suite-chat{'-qa' if qa else ''}-synapse-1:8008/_synapse/client/apoze/room-context")
        write_private(meet_path, json.dumps(meet, indent=2) + '\n')
    mail_path = suite_path.parent.parent / 'messages-calendars-local/settings.json'
    if mail_path.exists():
        mail = json.loads(mail_path.read_text())
        if mail.get('chat_origin') not in (None, '', config['origin']):
            raise ValueError('Calendars is already registered to another Chat origin')
        mail.update(chat_origin=config['origin'], chat_context_key=config['calendars_context_key'],
                    chat_status_key=config['calendars_status_key'],
                    chat_context_url=f"http://suite-chat{'-qa' if qa else ''}-synapse-1:8008/_synapse/client/apoze/room-context")
        write_private(mail_path, json.dumps(mail, indent=2) + '\n')
    transfers_path = suite_path.parent.parent / 'transfers-local/settings.json'
    transfers_origin = ''
    if transfers_path.exists():
        transfers = json.loads(transfers_path.read_text())
        if transfers.get('chat_public_url') not in (None, '', config['origin']):
            raise ValueError('Transfers is already registered to a different Chat origin')
        transfers['chat_public_url'] = config['origin']
        write_private(transfers_path, json.dumps(transfers, indent=2) + '\n')
        transfers_origin = transfers['origin']
    update_environment(Path(__file__).resolve().parents[2] / 'env.d/development/common.local',
                       {'CHAT_PUBLIC_URL': config['origin']})
    module = {
        'room_context_key_files': {'meet': '/run/chat/meet_context_key', 'calendars': '/run/chat/calendars_context_key'},
        'calendars_status_url': 'http://suite-mail-calendars-1:8000/internal/chat-event-state/',
        'calendars_status_key_file': '/run/chat/calendars_status_key',
        'meet_status_url': 'http://meet-local-backend-1:8000/internal/meet/chat-state/',
        'meet_status_key_file': '/run/chat/meet_status_key',
        'organization_id': config['organization_id'], 'database': '/data/apoze/directory.sqlite',
        'push_gateways': config.get('push_gateways', {}),
        'directory_url': f'http://{host}:8072/api/v1.0/suite-directory/', 'directory_key_file': '/run/chat/read_key',
        'policy_url': f'http://{host}:8961/api/v1.0/suite-policy/', 'policy_key_file': '/run/chat/policy_key',
        'catalogue_url': f'http://{host}:8961/api/v1.0/suite-catalogue/',
        'identity_request_url': f'http://{host}:8072/api/v1.0/suite-identity-requests/', 'mutation_key_file': '/run/chat/mutation_key',
        'service_id': config['policy_service_id'], 'mas_key_file': '/run/chat/mas_guard_key',
        'mas_admin_url': 'http://mas:8081', 'mas_token_url': 'http://mas:8080/oauth2/token',
        'mas_admin_id': config['mas_admin_id'], 'mas_admin_key_file': '/run/chat/mas_admin_secret',
    }
    synapse = {
        'server_name': server_name, 'public_baseurl': config['origin'] + '/', 'report_stats': False,
        'pid_file': '/data/homeserver.pid', 'signing_key_path': '/data/homeserver.signing.key',
        'media_store_path': '/media', 'log_config': '/data/log.config',
        'listeners': [{'port': 8008, 'type': 'http', 'tls': False, 'bind_addresses': ['0.0.0.0'], 'x_forwarded': True, 'resources': [{'names': ['client'], 'compress': False}]}],
        'database': {'name': 'psycopg2', 'args': {'host': 'suite-postgres', 'port': 5432, 'database': config['db_name'], 'user': config['db_name'], 'password': config['db_password'], 'cp_min': 1, 'cp_max': 5}},
        'matrix_authentication_service': {'enabled': True, 'endpoint': 'http://mas:8080/', 'secret': config['mas_synapse_secret']},
        'default_room_version': '11', 'enable_registration': False, 'allow_guest_access': False, 'enable_3pid_lookup': False,
        'user_directory': {'search_all_users': True, 'show_locked_users': False},
        'enable_set_displayname': False,
        'federation_domain_whitelist': [], 'allow_public_rooms_without_auth': False,
        'allow_public_rooms_over_federation': False, 'require_auth_for_profile_requests': True,
        'enable_authenticated_media': True, 'max_upload_size': '100M', 'max_image_pixels': '16M',
        'dynamic_thumbnails': False,
        'url_preview_enabled': False, 'trusted_key_servers': [], 'suppress_key_server_warning': True,
        'modules': [{'module': 'synapse.apoze_suite.Suite', 'config': module}],
    }
    write_private(state / 'synapse/homeserver.yaml', json.dumps(synapse, indent=2) + '\n', uid=991)
    write_private(state / 'synapse/log.config', json.dumps({'version': 1, 'handlers': {'console': {'class': 'logging.StreamHandler'}}, 'root': {'level': 'WARNING', 'handlers': ['console']}, 'disable_existing_loggers': False}) + '\n', uid=991)
    write_private(state / 'element-config.json', json.dumps({
        'oidc_static_clients': {config['auth_origin'] + '/': {'client_id': config['element_client_id']}},
        'apoze_suite': True, 'apoze_catalogue': True, 'brand': 'Apoze Chat',
        'apoze_drive_url': f'http://{host}:3000/',
        'apoze_transfers_url': transfers_origin,
        'apoze_meet_url': f'https://{host}:8443',
        'apoze_calendars_url': f'http://{host}:8930',
        'default_federate': False,
        'setting_defaults': {name: False for name in (
            'UIFeature.registration', 'UIFeature.passwordReset', 'UIFeature.deactivate',
            'UIFeature.allowCreatingPublicRooms', 'UIFeature.allowCreatingPublicSpaces',
            'UIFeature.voip', 'UIFeature.identityServer', 'UIFeature.thirdPartyId',
            'UIFeature.roomHistorySettings',
            'UIFeature.urlPreviews',
        )}, 'default_server_config': {'m.homeserver': {'base_url': config['origin'], 'server_name': server_name}},
        'disable_custom_urls': True, 'disable_guests': True, 'disable_login_language_selector': False,
        'show_labs_settings': False, 'default_theme': 'light', 'room_directory': {'servers': []},
        'integrations_ui_url': '', 'integrations_rest_url': '', 'integrations_widgets_urls': [],
        'jitsi': {'preferred_domain': ''}, 'embedded_pages': {'home_url': ''},
    }, indent=2) + '\n')
    # This is browser-visible configuration, readable by the native nginx user.
    (state / 'element-config.json').chmod(0o644)
    services = {
        'synapse': {'image': 'apoze/synapse:suite-local', 'build': {'context': str(repos / 'synapse'), 'dockerfile': 'docker/Dockerfile.apoze'},
                    'restart': 'unless-stopped', 'mem_limit': '1200m', 'environment': {'SYNAPSE_CONFIG_PATH': '/data/homeserver.yaml', 'UID': '991', 'GID': '991'},
                    'volumes': [f'{state}/synapse:/data', f'{state}/media:/media', f'{state}/keys:/run/chat:ro'], 'tmpfs': ['/tmp:rw,nosuid,nodev,noexec,size=402653184,mode=1777'], 'networks': ['default', 'suite']},
        'mas': {'image': 'apoze/mas:suite-local', 'user': '991:991', 'build': {'context': str(repos / 'matrix-authentication-service'), 'dockerfile': 'Dockerfile.apoze'},
                'restart': 'unless-stopped', 'mem_limit': '768m', 'environment': {'MAS_CONFIG': '/run/chat/mas.yaml', 'APOZE_AUTHORIZATION_URL': 'http://synapse:8008/_synapse/client/apoze/authorize', 'APOZE_AUTHORIZATION_KEY_FILE': '/run/chat/mas_guard_key'},
                'volumes': [f'{state}/mas.yaml:/run/chat/mas.yaml:ro', f'{state}/keys/mas_guard_key:/run/chat/mas_guard_key:ro'], 'networks': ['default', 'suite']},
        'element': {'image': 'apoze/element-web:suite-local', 'build': {'context': str(repos / 'element-web'), 'dockerfile': 'apps/web/Dockerfile', 'target': 'element_web'}, 'restart': 'unless-stopped', 'mem_limit': '128m',
                    'volumes': [f'{state}/element-config.json:/app/config.json:ro']},
        'edge': {'image': 'nginx:1.28.0-alpine@sha256:30f1c0d78e0ad60901648be663a710bdadf19e4c10ac6782c235200619158284', 'restart': 'unless-stopped', 'mem_limit': '64m',
                 'ports': [f'{host}:{config["port"]}:8443', f'{host}:{config["auth_port"]}:8444'],
                 'volumes': [f'{state}/nginx.conf:/etc/nginx/nginx.conf:ro', f'{state}/tls/server.crt:/run/tls/server.crt:ro', f'{state}/tls/server.key:/run/tls/server.key:ro']},
    }
    write_private(state / 'nginx.conf', f'''events {{}}
http {{
 access_log off;
 limit_conn_zone $server_name zone=chat_uploads:10m;
 resolver 127.0.0.11 valid=10s ipv6=off;
 server {{
  listen 8443 ssl;
  ssl_certificate /run/tls/server.crt;
  ssl_certificate_key /run/tls/server.key;
  client_max_body_size 8m;
  set $synapse synapse:8008;
  set $mas mas:8080;
  set $element element:80;
  location ~ ^/_matrix/client/(r0|v3|unstable)/(login|logout|refresh)(/|$) {{ proxy_pass http://$mas; proxy_set_header Host $http_host; proxy_set_header X-Forwarded-Proto https; }}
  location /_matrix/client/ {{ proxy_pass http://$synapse; proxy_set_header Host $http_host; proxy_read_timeout 65s; }}
  location ~ ^/_matrix/media/(r0|v1|v3)/(upload|create|config)(/|$) {{ client_max_body_size 100m; client_body_timeout 30s; limit_conn chat_uploads 2; limit_conn_status 429; proxy_pass http://$synapse; proxy_set_header Host $http_host; proxy_request_buffering off; }}
  location /_matrix/media/ {{ return 404; }}
  location ~ ^/_synapse/client/apoze/(storage|catalogue|meeting|calendar-event|media/(delete|manage)|rooms/access|admin/rooms)$ {{ proxy_pass http://$synapse; proxy_set_header Host $http_host; }}
  location /_synapse/ {{ return 404; }}
  location /.well-known/matrix/client {{ default_type application/json; add_header Access-Control-Allow-Origin *; return 200 '{json.dumps({'m.homeserver': {'base_url': config['origin']}, 'org.matrix.msc2965.authentication': {'issuer': config['auth_origin'] + '/', 'account': config['auth_origin'] + '/account/'}})}'; }}
  location / {{ proxy_pass http://$element; proxy_set_header Host $http_host; }}
 }}
 server {{
  listen 8444 ssl;
  ssl_certificate /run/tls/server.crt;
  ssl_certificate_key /run/tls/server.key;
  set $mas mas:8080;
  location /api/admin/ {{ return 404; }}
  location / {{ proxy_pass http://$mas; proxy_set_header Host $http_host; proxy_set_header X-Forwarded-Proto https; }}
 }}
}}
''')
    write_private(state / 'compose.json', json.dumps({'name': 'suite-chat-qa' if qa else 'suite-chat', 'services': services, 'networks': {'default': {}, 'suite': {'external': True, 'name': 'suite-local_default'}}}, indent=2) + '\n')
    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('data/chat-local'))
    parser.add_argument('--suite', type=Path, default=Path('data/suite-local/settings.json'))
    parser.add_argument('--repos', type=Path, default=Path('..'))
    parser.add_argument('--server-name', required=True)
    parser.add_argument('--qa', action='store_true', help='Disposable Matrix identity, never a production migration')
    args = parser.parse_args()
    prepare(args.state, args.suite, args.repos, server_name=args.server_name, qa=args.qa)
    print('Chat prepared privately; no services started.')
