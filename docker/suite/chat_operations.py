"""Operate Chat alone and restore snapshots without network access to the suite."""

import argparse
import fcntl
import gzip
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from mail_operations import compose, digest, inspect, run, runtime_image
from prepare_local import write_private

ROOT = Path(__file__).resolve().parents[2]
HISTORY_TABLES = ('events', 'rooms', 'local_media_repository', 'e2e_room_keys')


def backup(state, destination):
    source = json.loads((state / 'compose.json').read_text())
    settings = json.loads((state / 'settings.json').read_text())
    if source['name'] not in ('suite-chat', 'suite-chat-qa'):
        raise ValueError('Not a managed Chat installation')
    if destination.is_relative_to(state):
        raise ValueError('The backup must be outside the live state')
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    log = destination / 'diagnostic.private.log'
    runtimes = {name: inspect(f'{source["name"]}-{name}-1', log) for name in source['services']}
    postgres = inspect('suite-local-suite-postgres-1', log)
    manifest = {
        'format': 1, 'server_name': settings['server_name'],
        'created_at': datetime.now(timezone.utc).isoformat(),
        'images': {name: runtime_image(value, log) for name, value in runtimes.items()},
        'postgres_image': runtime_image(postgres, log),
        'databases': [settings['db_name'], settings['mas_db_name']],
    }
    databases = json.loads(run(['docker', 'exec', 'suite-local-suite-postgres-1', 'psql', '-U', 'postgres', '-Atc',
        "SELECT json_agg(json_build_object('name', datname, 'collation', datcollate, 'ctype', datctype)) FROM pg_database"], log))
    manifest['database_locales'] = {row['name']: row for row in databases if row['name'] in manifest['databases']}
    images = sorted(set(manifest['images'].values()) | {manifest['postgres_image']})
    with gzip.open(destination / 'images.tar.gz', 'wb', compresslevel=1) as output, log.open('ab') as errors:
        process = subprocess.Popen(['docker', 'image', 'save', *images], stdout=subprocess.PIPE, stderr=errors)
        try:
            shutil.copyfileobj(process.stdout, output, 1024 * 1024)
        finally:
            process.stdout.close()
            if process.wait():
                raise RuntimeError('Chat image backup failed; inspect private diagnostic')
    running = [name for name, runtime in runtimes.items() if runtime['State']['Running']]
    try:
        if running:
            compose(state / 'compose.json', 'stop', '-t', '45', *running, log=log)
        for index, database in enumerate(manifest['databases']):
            with (destination / f'database-{index}.dump').open('wb') as output:
                run(['docker', 'exec', 'suite-local-suite-postgres-1', 'pg_dump', '-U', 'postgres',
                     '-Fc', '--no-owner', '--no-acl', database], log, output=output)
        manifest['synapse_counts'] = {
            table: int(run(['docker', 'exec', 'suite-local-suite-postgres-1', 'psql', '-U', 'postgres',
                            '-d', settings['db_name'], '-Atc', 'SELECT count(*) FROM ' + table], log))
            for table in HISTORY_TABLES
        }
        # Stopped writers make the SQL projection, media and bot key store consistent.
        with tarfile.open(destination / 'state.tar.gz', 'w:gz', compresslevel=1) as archive:
            for path in state.rglob('*'):
                if path.is_symlink():
                    raise ValueError('Unexpected symlink in Chat state')
                if path.is_file() and not path.name.endswith(('.log', '.lock', '.pid')):
                    archive.add(path, arcname=str(path.relative_to(state)), recursive=False)
        manifest['files'] = {path.name: digest(path) for path in destination.iterdir() if path != log}
        write_private(destination / 'manifest.json', json.dumps(manifest, indent=2))
    finally:
        if running:
            compose(state / 'compose.json', 'start', *running, log=log)
    return {'backup': str(destination), 'server_name': settings['server_name'], 'coherent': True}


def restore(source, destination):
    if destination.is_relative_to(source):
        raise ValueError('Restore outside the source snapshot')
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest['format'] != 1 or not destination.name.startswith('suite-chat-restore-'):
        raise ValueError('Use a Chat snapshot and a new suite-chat-restore-* destination')
    for name, expected in manifest['files'].items():
        path = (source / name).resolve()
        if not path.is_relative_to(source) or digest(path) != expected:
            raise ValueError('Backup integrity verification failed')
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    log = destination / 'diagnostic.private.log'
    run(['docker', 'image', 'load', '-i', str(source / 'images.tar.gz')], log)
    private = destination / 'state'
    with tarfile.open(source / 'state.tar.gz') as archive:
        archive.extractall(private, filter='data')
    settings = json.loads((private / 'settings.json').read_text())
    source_services = json.loads((private / 'compose.json').read_text())['services']
    synapse = yaml.safe_load((private / 'synapse/homeserver.yaml').read_text())
    mas = yaml.safe_load((private / 'mas.yaml').read_text())
    if synapse['server_name'] != manifest['server_name'] or settings['server_name'] != manifest['server_name']:
        raise ValueError('Matrix server identity must not change during restore')
    password = secrets.token_urlsafe(40)
    synapse['database']['args'].update(host='postgres', user='postgres', password=password)
    module = synapse['modules'][0]['config']
    if synapse['modules'][0]['module'] != 'synapse.apoze_suite.Suite':
        raise ValueError('Suite authorization module is required')
    for name in tuple(module):
        if name.endswith('_url') and not name.startswith('mas_'):
            module[name] = 'http://authority-unavailable.invalid/'
    module['push_gateways'] = {}
    module.pop('projects_bot', None)
    synapse['federation_domain_whitelist'] = []
    synapse['email'] = {}
    mas['database']['uri'] = f'postgresql://postgres:{password}@postgres:5432/{settings["mas_db_name"]}'
    mas.pop('email', None)
    # Prevent background jobs from touching a live IdP or the notification bot.
    mas['upstream_oauth2'] = {'providers': []}
    # Rotate both ends of the internal links, independently of live credentials.
    admin_secret = secrets.token_urlsafe(48)
    for client in mas['clients']:
        if client['client_id'] == module['mas_admin_id']:
            client['client_secret'] = admin_secret
    shared_secret = secrets.token_urlsafe(48)
    mas['matrix']['secret'] = shared_secret
    synapse['matrix_authentication_service']['secret'] = shared_secret
    write_private(private / 'synapse/homeserver.yaml', json.dumps(synapse), uid=991)
    write_private(private / 'mas.yaml', json.dumps(mas), uid=991)
    for file in (private / 'keys').iterdir():
        write_private(file, secrets.token_urlsafe(48), uid=991)
    # Keep only the internal MAS/Synapse shared secret; no live authority keys.
    write_private(private / 'keys/mas_guard_key', secrets.token_urlsafe(48), uid=991)
    write_private(private / 'keys/mas_admin_secret', admin_secret, uid=991)
    projection = private / 'synapse/apoze/directory.sqlite'
    with sqlite3.connect(projection) as db:
        db.execute('UPDATE checkpoint SET checked=0')
        db.execute('UPDATE mas_accounts SET allowed=0')
        db.execute('UPDATE media_budget SET checked=0')
        db.execute('DELETE FROM pusher_authority')
    for directory in (private / 'synapse', private / 'media', private / 'keys'):
        for path in [directory, *directory.rglob('*')]:
            os.chown(path, 991, 991)
    config = {'name': destination.name, 'networks': {'default': {'internal': True}},
              'volumes': {'postgres': {}}, 'services': {
        'postgres': {'image': manifest['postgres_image'],
                     'environment': {'POSTGRES_PASSWORD': password},
                     'volumes': ['postgres:/var/lib/postgresql/data'],
                     'healthcheck': {'test': ['CMD-SHELL', 'pg_isready -U postgres'], 'interval': '2s', 'retries': 30}},
        'synapse': {'image': manifest['images']['synapse'], 'user': '991:991',
                    'environment': {'SYNAPSE_CONFIG_PATH': '/data/homeserver.yaml'},
                    'volumes': [f'{private}/synapse:/data', f'{private}/media:/media', f'{private}/keys:/run/chat:ro'],
                    'tmpfs': source_services['synapse'].get('tmpfs', []),
                    'mem_limit': '1200m'},
        'mas': {'image': manifest['images']['mas'], 'user': '991:991',
                'environment': {'MAS_CONFIG': '/run/chat/mas.yaml',
                                'APOZE_AUTHORIZATION_URL': 'http://synapse:8008/_synapse/client/apoze/authorize',
                                'APOZE_AUTHORIZATION_KEY_FILE': '/run/chat/mas_guard_key'},
                'volumes': [f'{private}/mas.yaml:/run/chat/mas.yaml:ro', f'{private}/keys/mas_guard_key:/run/chat/mas_guard_key:ro'],
                'mem_limit': '768m'},
    }}
    target = destination / 'compose.json'
    write_private(target, json.dumps(config, indent=2))
    compose(target, 'up', '-d', '--wait', '--wait-timeout', '90', 'postgres', log=log)
    for index, database in enumerate(manifest['databases']):
        locale = manifest['database_locales'][database]
        run(['docker', 'exec', destination.name + '-postgres-1', 'createdb', '-U', 'postgres',
             '--template=template0', '--encoding=UTF8', '--lc-collate=' + locale['collation'],
             '--lc-ctype=' + locale['ctype'], database], log)
        with (source / f'database-{index}.dump').open('rb') as stream, log.open('ab') as errors:
            result = subprocess.run(['docker', 'exec', '-i', destination.name + '-postgres-1', 'pg_restore',
                                     '-U', 'postgres', '-d', database, '--no-owner', '--no-acl', '--exit-on-error'],
                                    stdin=stream, stdout=errors, stderr=errors)
            if result.returncode:
                raise RuntimeError('Chat database restore failed; inspect private diagnostic')
    # Native MAS session revocation also queues native device synchronization.
    users = run(['docker', 'exec', destination.name + '-postgres-1', 'psql', '-U', 'postgres',
                 '-d', settings['mas_db_name'], '-Atc', 'SELECT username FROM users'], log).decode().splitlines()
    for user in users:
        compose(target, 'run', '--rm', '--no-deps', '--entrypoint', 'mas-cli', 'mas',
                'manage', 'kill-sessions', user, log=log)
    run(['docker', 'exec', destination.name + '-postgres-1', 'psql', '-U', 'postgres',
         '-d', settings['mas_db_name'], '-v', 'ON_ERROR_STOP=1', '-c',
         'BEGIN; UPDATE personal_sessions SET revoked_at=NOW() WHERE revoked_at IS NULL; '
         'UPDATE oauth2_sessions SET finished_at=NOW() WHERE finished_at IS NULL; COMMIT;'], log)
    compose(target, 'up', '-d', '--wait', '--wait-timeout', '90', '--no-deps', 'synapse', 'mas', log=log)
    write_private(destination / 'restored-from.json', json.dumps({'backup': str(source), 'isolated': True}))
    return {'restore': str(destination), 'server_name': manifest['server_name'],
            'network': 'isolated', 'push_mail_federation': 'disabled', 'authorities': 'require fresh validation'}



def verify_restore(destination):
    config = json.loads((destination / 'compose.json').read_text())
    if (not destination.name.startswith('suite-chat-restore-') or config['name'] != destination.name
            or any(service.get('ports') for service in config['services'].values())):
        raise ValueError('An unexposed Chat restore is required')
    log = destination / 'verification.private.log'
    network = json.loads(run(['docker', 'network', 'inspect', destination.name + '_default'], log))[0]
    if not network['Internal'] or set(config['services']) != {'postgres', 'mas', 'synapse'}:
        raise ValueError('Restore isolation failed')
    source = Path(json.loads((destination / 'restored-from.json').read_text())['backup'])
    manifest = json.loads((source / 'manifest.json').read_text())
    def sql(database, query):
        return run(['docker', 'exec', destination.name + '-postgres-1', 'psql', '-U', 'postgres',
                    '-d', database, '-Atc', query], log).decode().strip()
    counts = {table: int(sql(manifest['databases'][0], 'SELECT count(*) FROM ' + table)) for table in HISTORY_TABLES}
    if counts != manifest['synapse_counts']:
        raise ValueError('Restored history counts differ from the snapshot')
    for table, column in [('oauth2_sessions', 'finished_at'), ('user_sessions', 'finished_at'),
                          ('compat_sessions', 'finished_at'), ('personal_sessions', 'revoked_at')]:
        if sql(manifest['databases'][1], f'SELECT count(*) FROM {table} WHERE {column} IS NULL') != '0':
            raise ValueError('A pre-restore session is still active')
    unchanged = 0
    with tarfile.open(source / 'state.tar.gz') as archive:
        for member in archive:
            if not member.isfile() or not (member.name.startswith(('media/', 'bot/runtime/'))
                    or member.name in ('bot/store_key', 'synapse/homeserver.signing.key')):
                continue
            target = (destination / 'state' / member.name).resolve()
            if not target.is_relative_to(destination / 'state'):
                raise ValueError('Invalid snapshot path')
            with archive.extractfile(member) as stream:
                expected = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest(target) != expected:
                raise ValueError('Restored media or encryption store differs from snapshot')
            unchanged += 1
    compose(destination / 'compose.json', 'exec', '-T', 'synapse', 'python', '-c',
            "from urllib.request import urlopen; "
            "assert urlopen('http://127.0.0.1:8008/health', timeout=5).status == 200; "
            "assert urlopen('http://mas:8081/health', timeout=5).status == 200", log=log)
    report = {'isolated': True, 'history': counts, 'identical_media_and_key_files': unchanged,
              'sessions_revoked': True, 'synapse_mas_health': True}
    write_private(destination / 'validation.json', json.dumps(report, indent=2))
    return report


AUTHORITIES = '''
import json,sys
from pathlib import Path
from synapse.apoze_suite.directory import Directory,DirectoryError
from synapse.apoze_suite.mas import Accounts
overrides=json.load(sys.stdin)
config=json.loads(Path('/data/homeserver.yaml').read_text())['modules'][0]['config']
directory=Directory(config | overrides)
try:
 directory.synchronize()
 accounts=Accounts(directory)
 accounts.synchronize()
 with directory.connect() as db:
  principals=[row[0] for row in db.execute('SELECT principal FROM mas_accounts WHERE allowed=1')]
 for principal in principals:
  directory.require(principal)
 print(json.dumps({'current_accounts':len(principals),'mas_reconciled':True,'storage_usage_published':False}))
finally:
 with directory.connect() as db:
  db.execute('UPDATE checkpoint SET checked=0')
  db.execute('UPDATE mas_accounts SET allowed=0')
  db.execute('UPDATE media_budget SET checked=0')
'''


def verify_authorities(state, destination):
    # Reuse the full integrity/isolation check before temporarily attaching peers.
    verify_restore(destination)
    log = destination / 'authorities.private.log'
    private = destination / 'state/synapse/verify-authorities'
    private.mkdir(mode=0o700, exist_ok=False)
    os.chown(private, 991, 991)
    live = yaml.safe_load((state / 'synapse/homeserver.yaml').read_text())['modules'][0]['config']
    network = destination.name + '_default'
    attached = []
    try:
        overrides = {}
        for name, alias, key in [('directory', 'verify-people', 'read_key'), ('policy', 'verify-st', 'policy_key')]:
            overrides[name + '_url'] = 'http://' + alias + ':8000' + urlsplit(live[name + '_url']).path
            overrides[name + '_key_file'] = '/data/verify-authorities/' + key
            write_private(private / key, (state / 'keys' / key).read_text(), uid=991)
        for container, alias in [('suite-local-people-1', 'verify-people'), ('st-deploycenter-backend-dev-1', 'verify-st')]:
            run(['docker', 'network', 'connect', '--alias', alias, network, container], log)
            attached.append(container)
        result = compose(destination / 'compose.json', 'exec', '-T', 'synapse', 'python', '-c', AUTHORITIES,
                         data=json.dumps(overrides).encode(), log=log)
        report = json.loads(result)
        write_private(destination / 'authority-verification.json', json.dumps(report, indent=2))
        return report
    finally:
        shutil.rmtree(private)
        failures = []
        # The one-off MAS administration login is not a session to retain.
        settings = json.loads((destination / 'state/settings.json').read_text())
        try:
            run(['docker', 'exec', destination.name + '-postgres-1', 'psql', '-U', 'postgres',
                 '-d', settings['mas_db_name'], '-v', 'ON_ERROR_STOP=1', '-c',
                 'UPDATE oauth2_sessions SET finished_at=NOW() WHERE finished_at IS NULL AND user_id IS NULL'], log)
        except RuntimeError:
            failures.append('temporary_mas_session')
        for container in reversed(attached):
            try:
                run(['docker', 'network', 'disconnect', network, container], log)
            except RuntimeError:
                failures.append(container)
        if failures:
            raise RuntimeError('Chat authority cleanup failed; inspect private diagnostic')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status', 'backup', 'restore', 'verify-restore', 'verify-authorities', 'cleanup-restore'])
    parser.add_argument('path', type=Path, nargs='?')
    parser.add_argument('--state', type=Path, default=ROOT / 'data/chat-local')
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    state = args.state.resolve()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state / 'operations.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        log = state / 'operations.private.log'
        if args.action == 'backup' and args.path:
            result = backup(state, args.path.resolve())
        elif args.action == 'restore' and args.path and args.destination:
            result = restore(args.path.resolve(), args.destination.resolve())
        elif args.action == 'verify-restore' and args.path:
            result = verify_restore(args.path.resolve())
        elif args.action == 'verify-authorities' and args.path:
            result = verify_authorities(state, args.path.resolve())
        elif args.action == 'cleanup-restore' and args.path:
            path = args.path.resolve()
            config = json.loads((path / 'compose.json').read_text())
            if (not path.name.startswith('suite-chat-restore-') or config['name'] != path.name
                    or config['networks'] != {'default': {'internal': True}}
                    or any(service.get('ports') for service in config['services'].values())):
                raise ValueError('Not an isolated Chat restore')
            compose(path / 'compose.json', 'down', '-v', log=log)
            result = {'cleanup': str(path), 'private_files': 'retained'}
        elif args.action in ('start', 'stop', 'status'):
            command = {'start': ('up', '-d', '--no-build'), 'stop': ('stop', '-t', '45'),
                       'status': ('ps', '--format', '{{.Name}} {{.State}} {{.Health}}')}[args.action]
            result = compose(state / 'compose.json', *command, log=log).decode().strip()
        else:
            parser.error('This operation requires a path and, for restore, a destination')
        print(json.dumps(result))


if __name__ == '__main__':
    main()
