"""Prepare Apoze APNs/FCM credentials locally; never use upstream application keys."""

import argparse
import json
import os
from pathlib import Path
import re

from prepare_local import write_private

SYGNAL_IMAGE = 'matrixdotorg/sygnal:v0.17.0@sha256:141f5e72fdf99a28e29ca87f3a46c19ed1cf21d5074aa3ef9df7c067e0c1c46a'


def prepare(state, *, fcm=None, apns=None, team=None, key_id=None):
    state = state.resolve()
    settings_path = state / 'settings.json'
    config = json.loads(settings_path.read_text())
    apps = dict(config.get('push_apps', {}))
    if fcm:
        with fcm.open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('FCM credential file is too large')
        account = json.loads(raw)
        if account.get('type') != 'service_account' or not re.fullmatch(r'[a-z][a-z0-9-]{4,62}', account.get('project_id', '')):
            raise ValueError('A native FCM v1 service account is required')
        if not isinstance(account.get('private_key'), str) or not account['private_key'].startswith('-----BEGIN PRIVATE KEY-----'):
            raise ValueError('FCM private key is missing')
        write_private(state / 'push/credentials/fcm.json', raw.decode(), uid=991)
        for suffix in ('', '.debug', '.nightly'):
            apps['ovh.zohenhl.chat.android' + suffix] = {
                'type': 'gcm', 'api_version': 'v1', 'project_id': account['project_id'],
                'service_account_file': '/sygnal/credentials/fcm.json',
                'send_badge_counts': False, 'max_connections': 4, 'inflight_request_limit': 32,
            }
    if apns:
        if not all(isinstance(value, str) and re.fullmatch(r'[A-Z0-9]{10}', value) for value in (team, key_id)):
            raise ValueError('APNs team and key identifiers must contain ten uppercase letters/digits')
        with apns.open("rb") as stream:
            raw = stream.read(16385)
        if len(raw) > 16384 or not raw.startswith(b'-----BEGIN PRIVATE KEY-----'):
            raise ValueError('An APNs p8 private key is required')
        write_private(state / 'push/credentials/apns.p8', raw.decode(), uid=991)
        for suffix, platform in [('dev', 'sandbox'), ('prod', 'production')]:
            apps['ovh.zohenhl.chat.ios.' + suffix] = {
                'type': 'apns', 'keyfile': '/sygnal/credentials/apns.p8', 'key_id': key_id,
                'team_id': team, 'topic': 'ovh.zohenhl.chat.ios', 'platform': platform,
                'send_badge_counts': False, 'inflight_request_limit': 32,
            }
    if not apps:
        return {'configured': False, 'reason': 'Apoze APNs/FCM credentials have not been provided'}
    allowed = {'ovh.zohenhl.chat.android' + suffix for suffix in ('', '.debug', '.nightly')}
    allowed |= {'ovh.zohenhl.chat.ios.' + suffix for suffix in ('dev', 'prod')}
    if set(apps) - allowed:
        raise ValueError('Unexpected mobile application identity')
    config['push_apps'] = apps
    config['push_gateways'] = {app: config['origin'] + '/_matrix/push/v1/notify' for app in apps}
    write_private(settings_path, json.dumps(config, indent=2) + '\n')
    payload = {'http': {'bind_addresses': ['0.0.0.0'], 'port': 5000}, 'apps': apps,
               'log': {'setup': {'version': 1, 'disable_existing_loggers': False,
                                'handlers': {'null': {'class': 'logging.NullHandler'}},
                                'root': {'handlers': ['null'], 'level': 'WARNING'}}},
               'metrics': {'prometheus': {'enabled': False}, 'opentracing': {'enabled': False}, 'sentry': {'enabled': False}}}
    write_private(state / 'push/sygnal.yaml', json.dumps(payload, indent=2), uid=991)
    for path in (state / 'push', state / 'push/credentials'):
        os.chown(path, 991, 991)
    return {'configured': True, 'applications': sorted(apps), 'delivery': 'requires real device validation'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('data/chat-local'))
    parser.add_argument('--fcm-service-account', type=Path)
    parser.add_argument('--apns-key', type=Path)
    parser.add_argument('--apns-team-id')
    parser.add_argument('--apns-key-id')
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(prepare(args.state, fcm=args.fcm_service_account, apns=args.apns_key,
                             team=args.apns_team_id, key_id=args.apns_key_id)))
