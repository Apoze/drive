"""Prepare Projects without starting or reconfiguring the existing applications."""

import argparse
import json
import os
from pathlib import Path
import secrets
from urllib.parse import quote

from prepare_local import environment, write_private
from prepare_mail import update_environment


def prepare(state, suite_path, repo):
    os.umask(0o077)
    state = state.resolve()
    installation = json.loads(suite_path.read_text())
    identity = {k: installation[k] for k in ('host', 'issuer', 'organization_id')}
    path = state / 'settings.json'
    if path.exists():
        config = json.loads(path.read_text())
        if any(config[k] != v for k, v in identity.items()):
            raise ValueError('Existing Projects identity differs; migrate explicitly')
    else:
        config = identity | {k: secrets.token_urlsafe(40) for k in (
            'db_password', 'session_secret', 'client_secret', 'read_key',
            'mutation_key', 'policy_key', 'recovery_password', 's3_access', 's3_secret')}
        config.update(port=8940, client_id='apoze-projects', policy_service_id='', bucket='projects')
        write_private(path, json.dumps(config, indent=2) + '\n')
    if 'drive_keys' not in config:
        config['drive_keys'] = {purpose: secrets.token_urlsafe(48) for purpose in ('read', 'mutation')}
        write_private(path, json.dumps(config, indent=2) + '\n')
    if 'messages_key' not in config:
        config['messages_key'] = secrets.token_urlsafe(48)
        write_private(path, json.dumps(config, indent=2) + '\n')
    mail_state = suite_path.parent.parent / 'messages-calendars-local'
    if not (mail_state / 'settings.json').exists():
        raise ValueError('Prepare the existing Messages LAN stack first')
    mail_settings = json.loads((mail_state / 'settings.json').read_text())
    if mail_settings.get('projects_notifications_key') not in (None, config['messages_key']):
        raise ValueError('Messages sender credential conflict')
    mail_settings['projects_notifications_key'] = config['messages_key']
    write_private(mail_state / 'settings.json', json.dumps(mail_settings, indent=2) + '\n')
    write_private(mail_state / 'messages/keys/projects_notifications', config['messages_key'], uid=1000)
    write_private(state / 'keys/messages_notifications', config['messages_key'], uid=1000)
    update_environment(mail_state / 'messages/backend.env', {
        'PROJECTS_NOTIFICATIONS_KEY_FILE': '/run/suite/projects_notifications',
        'PROJECTS_PUBLIC_URL': f"http://{config['host']}:{config['port']}"})
    drive_repo = Path(__file__).resolve().parents[2]
    drive_env = {'PROJECTS_PUBLIC_URL': f"http://{config['host']}:{config['port']}"}
    for purpose, key in config['drive_keys'].items():
        drive_key = drive_repo / 'data/storage-secrets/projects-files' / purpose
        write_private(drive_key, key, uid=1000)
        os.chown(drive_key.parent, 1000, 1000)
        write_private(state / 'keys' / ('drive_' + purpose), key, uid=1000)
        drive_env[f'PROJECTS_FILES_{purpose.upper()}_KEY_FILE'] = f'/run/storage-secrets/projects-files/{purpose}'
    update_environment(drive_repo / 'env.d/development/common.local', drive_env)
    host = config['host']
    origin = f"http://{host}:{config['port']}"
    for key in ('read_key', 'mutation_key', 'policy_key'):
        write_private(state / 'keys' / key, config[key], uid=1000)
    os.chown(state / 'keys', 1000, 1000)
    for purpose in ('context', 'status'):
        if config.get('chat_' + purpose + '_key'):
            write_private(state / 'keys' / ('chat_' + purpose), config['chat_' + purpose + '_key'], uid=1000)
    if config.get('chat_bot_key'):
        write_private(state / 'keys/chat_bot', config['chat_bot_key'], uid=1000)
        write_private(state / 'keys/chat_bot_control', config['chat_bot_control_key'], uid=1000)
    environment(state / 'backend.env', {
        'NODE_ENV': 'production', 'BASE_URL': origin,
        'DATABASE_URL': 'postgresql://projects:' + quote(config['db_password'], safe='') + '@suite-postgres:5432/projects',
        'SECRET_KEY': config['session_secret'], 'SUITE_ENABLED': 'true',
        'OIDC_ISSUER': config['issuer'], 'OIDC_CLIENT_ID': config['client_id'],
        'OIDC_CLIENT_SECRET': config['client_secret'],
        'OIDC_IGNORE_ROLES': 'true', 'OIDC_IGNORE_USERNAME': 'true',
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
        'S3_ENDPOINT': installation['s3']['endpoint'],
        'S3_REGION': 'us-east-1', 'S3_FORCE_PATH_STYLE': 'true',
        'S3_BUCKET': config['bucket'], 'S3_ACCESS_KEY_ID': config['s3_access'],
        'S3_SECRET_ACCESS_KEY': config['s3_secret'],
        'SUITE_CLAMAV_HOST': 'clamav', 'SUITE_CLAMAV_PORT': '3310',
        'SUITE_STORAGE_ADMIN_URL': (f"http://{host}:8960/operators/{config['operator_id']}/organizations/{config['organization_id']}?service_id={config['policy_service_id']}" if config.get('operator_id') else ''),
        'SUITE_MESSAGES_NOTIFICATIONS_URL': 'http://messages:8000/api/v1.0/internal/projects/notifications/',
        'SUITE_MESSAGES_NOTIFICATIONS_KEY_FILE': '/run/suite/messages_notifications',
        'SUITE_DRIVE_URL': f'http://{host}:3000',
        'SUITE_CHAT_URL': config.get('chat_origin', ''),
        'SUITE_CHAT_CONTEXT_URL': config.get('chat_context_url', ''),
        'SUITE_CHAT_CONTEXT_KEY_FILE': '/run/suite/chat_context' if config.get('chat_context_key') else '',
        'SUITE_CHAT_STATUS_KEY_FILE': '/run/suite/chat_status' if config.get('chat_status_key') else '',
        'SUITE_CHAT_BOT_URL': config.get('chat_bot_url', ''),
        'SUITE_CHAT_BOT_KEY_FILE': '/run/suite/chat_bot' if config.get('chat_bot_key') else '',
        'SUITE_CHAT_BOT_CONTROL_KEY_FILE': '/run/suite/chat_bot_control' if config.get('chat_bot_key') else '',
        'SUITE_DRIVE_API_URL': f'http://{host}:8071/api/v1.0/internal/projects/files/',
        'SUITE_DRIVE_READ_KEY_FILE': '/run/suite/drive_read',
        'SUITE_DRIVE_MUTATION_KEY_FILE': '/run/suite/drive_mutation',
        'SUITE_STORAGE_POLICY_URL': f'http://{host}:8961/api/v1.0/entitlements/',
        'DEFAULT_LANGUAGE': 'fr-FR', 'SUPPORTED_LANGUAGES': 'fr-FR,en-US',
        'ALLOW_ALL_TO_CREATE_PROJECTS': 'false', 'WEBHOOKS': '[]',
    })
    # Only the LAN interface; ST access remains closed until qualification.
    compose = {
        'name': 'suite-projects',
        'services': {'projects': {
            'image': 'apoze/projects:suite-local', 'build': {'context': str(repo.resolve())},
            'restart': 'unless-stopped', 'init': True, 'mem_limit': '1536m',
            'env_file': [str(state / 'backend.env')],
            'ports': [f"{host}:{config['port']}:1337"],
            'volumes': [f'{state}/keys:/run/suite:ro', 'projects-tmp:/app/.tmp'],
            'networks': ['suite', 'storage', 'mail'],
        }},
        'networks': {
            'suite': {'external': True, 'name': 'suite-local_default'},
            'storage': {'external': True, 'name': 'suite-local_docs-storage'},
            'mail': {'external': True, 'name': 'suite-mail_default'},
        },
        'volumes': {'projects-tmp': {}},
    }
    write_private(state / 'compose.json', json.dumps(compose, indent=2) + '\n')
    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('data/projects-local'))
    parser.add_argument('--suite', type=Path, default=Path('data/suite-local/settings.json'))
    parser.add_argument('--repo', type=Path, default=Path('../projects'))
    args = parser.parse_args()
    prepare(args.state, args.suite, args.repo)
    print('Projects configuration prepared; credentials retained privately; no service started.')
