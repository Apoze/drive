"""Operate Projects alone; restore into isolated databases and private object storage."""

import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

from mail_operations import compose, digest, inspect, run, runtime_image
from prepare_local import environment, write_private

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'data/projects-local'


def backup(destination):
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    log = destination / 'diagnostic.private.log'
    runtime = inspect('suite-projects-projects-1', log)
    if runtime['State'].get('Health', {}).get('Status') != 'healthy':
        raise ValueError('Projects must be healthy before a backup')
    if any(m['Destination'].startswith('/app/') and m['Type'] == 'bind' for m in runtime['Mounts']):
        raise ValueError('Remove source iteration mounts and build the exact Projects image first')
    postgres = inspect('suite-local-suite-postgres-1', log)
    storage = inspect('suite-local-docs-s3-1', log)
    manifest = {'format': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                'images': {name: runtime_image(value, log) for name, value in
                           [('projects', runtime), ('postgres', postgres), ('storage', storage)]},
                'revision': run(['git', '-C', str(ROOT.parent / 'projects'), 'rev-parse', 'HEAD'], log).decode().strip()}
    with gzip.open(destination / 'images.tar.gz', 'wb', compresslevel=1) as archive, log.open('ab') as errors:
        process = subprocess.Popen(['docker', 'image', 'save', *sorted(set(manifest['images'].values()))],
                                   stdout=subprocess.PIPE, stderr=errors)
        try:
            shutil.copyfileobj(process.stdout, archive, 1024 * 1024)
        finally:
            process.stdout.close()
            if process.wait():
                raise RuntimeError('Image backup failed; inspect private diagnostic')
    with tarfile.open(destination / 'configuration.tar.gz', 'w:gz') as archive:
        for file in [STATE / 'settings.json', STATE / 'backend.env', STATE / 'compose.json', *(STATE / 'keys').iterdir()]:
            archive.add(file, arcname=str(file.relative_to(STATE)), recursive=False)
    was_running = runtime['State']['Running']
    try:
        if was_running:
            compose(STATE / 'compose.json', 'stop', '-t', '45', 'projects', log=log)
        with (destination / 'projects.dump').open('wb') as stream:
            run(['docker', 'exec', 'suite-local-suite-postgres-1', 'pg_dump', '-U', 'postgres',
                 '-Fc', '--no-owner', '--no-acl', 'projects'], log, output=stream)
        run(['docker', 'run', '--rm', '--user', '0', '--network', 'suite-local_docs-storage',
             '--env-file', str(STATE / 'backend.env'), '-v', f'{destination}:/backup',
             '--entrypoint', 'node', manifest['images']['projects'], 'db/suite-objects.js', 'export', '/backup'], log)
        manifest['files'] = {str(file.relative_to(destination)): digest(file)
                             for file in destination.rglob('*') if file.is_file() and file != log}
        write_private(destination / 'manifest.json', json.dumps(manifest, indent=2))
    finally:
        if was_running:
            compose(STATE / 'compose.json', 'start', 'projects', log=log)
    print(json.dumps({'backup': str(destination), 'coherent': True}))


def restore(source, destination):
    source, destination = source.resolve(), destination.resolve()
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest['format'] != 1 or manifest.get('usable') is False:
        raise ValueError('Unsupported backup')
    for name, expected in manifest['files'].items():
        file = (source / name).resolve()
        if not file.is_relative_to(source) or digest(file) != expected:
            raise ValueError('Backup integrity verification failed')
    if not destination.name.startswith('suite-projects-restore-'):
        raise ValueError('Use a dedicated suite-projects-restore-* directory')
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    log = destination / 'diagnostic.private.log'
    # Docker can consume the compressed archive directly; no plaintext image duplicate.
    run(['docker', 'image', 'load', '-i', str(source / 'images.tar.gz')], log)
    private = destination / 'configuration'
    with tarfile.open(source / 'configuration.tar.gz') as archive:
        archive.extractall(private, filter='data')
    values = dict(line.split('=', 1) for line in (private / 'backend.env').read_text().splitlines() if line)
    password = secrets.token_urlsafe(40)
    values.update(DATABASE_URL='postgresql://postgres:' + quote(password, safe='') + '@postgres:5432/projects',
                  SECRET_KEY=secrets.token_urlsafe(48), S3_ENDPOINT='http://storage:8333',
                  S3_ACCESS_KEY_ID=secrets.token_hex(20), S3_SECRET_ACCESS_KEY=secrets.token_urlsafe(40),
                  SUITE_RESTORE_ISOLATED='true', SUITE_MESSAGES_NOTIFICATIONS_URL='', WEBHOOKS='[]',
                  SUITE_DIRECTORY_URL='http://authority-unavailable.invalid/',
                  SUITE_POLICY_URL='http://authority-unavailable.invalid/',
                  SUITE_LOGOUT_URL='', SUITE_IDENTITY_REQUEST_URL='',
                  SUITE_STORAGE_POLICY_URL='', SUITE_CLAMAV_HOST='')
    # No old machine credential is mounted into the isolated application.
    for name in ('read_key', 'mutation_key', 'policy_key', 'drive_read', 'drive_mutation', 'messages_notifications'):
        write_private(destination / 'keys' / name, secrets.token_urlsafe(48), uid=1000)
    os.chown(destination / 'keys', 1000, 1000)
    environment(destination / 'backend.env', values)
    config = {'name': destination.name, 'networks': {'default': {'internal': True}},
              'volumes': {'postgres': {}, 'storage': {}, 'tmp': {}}, 'services': {
        'postgres': {'image': manifest['images']['postgres'],
                     'environment': {'POSTGRES_PASSWORD': password, 'POSTGRES_DB': 'projects'},
                     'volumes': ['postgres:/var/lib/postgresql/data'],
                     'healthcheck': {'test': ['CMD-SHELL', 'pg_isready -U postgres'], 'interval': '2s', 'retries': 30}},
        'storage': {'image': manifest['images']['storage'],
                    'command': ['server', '-s3', '-dir=/data', '-ip=storage', '-volume.max=32', '-master.volumeSizeLimitMB=1024'],
                    'volumes': ['storage:/data'],
                    'healthcheck': {'test': ['CMD', 'wget', '-qO-', 'http://127.0.0.1:9333/cluster/status'], 'interval': '2s', 'retries': 30}},
        'projects': {'image': manifest['images']['projects'], 'env_file': [str(destination / 'backend.env')],
                     'volumes': [f'{destination}/keys:/run/suite:ro', 'tmp:/app/.tmp'], 'init': True, 'mem_limit': '1536m'},
    }}
    target = destination / 'compose.json'
    write_private(target, json.dumps(config, indent=2))
    compose(target, 'up', '-d', '--wait', '--wait-timeout', '90', 'postgres', 'storage', log=log)
    with (source / 'projects.dump').open('rb') as stream, log.open('ab') as errors:
        result = subprocess.run(['docker', 'exec', '-i', destination.name + '-postgres-1', 'pg_restore',
                                 '-U', 'postgres', '-d', 'projects', '--no-owner', '--no-acl', '--exit-on-error'],
                                stdin=stream, stdout=errors, stderr=errors)
        if result.returncode:
            raise RuntimeError('Isolated database restore failed')
    run(['docker', 'exec', '-i', destination.name + '-postgres-1', 'psql', '-U', 'postgres', '-d', 'projects', '-v', 'ON_ERROR_STOP=1'], log,
        data=b"BEGIN; DELETE FROM session; DELETE FROM suite_oidc_transaction; UPDATE suite_account SET active=false,policy_allowed=false,checked_at=NULL,policy_until=NULL; DELETE FROM suite_state; DELETE FROM suite_storage_policy; UPDATE notification SET suite_delivery_state='cancelled' WHERE suite_delivery_state NOT IN ('sent','skipped'); COMMIT;")
    run(['docker', 'run', '--rm', '--user', '0', '--network', destination.name + '_default',
         '--env-file', str(destination / 'backend.env'), '-v', f'{source}:/backup:ro', '--entrypoint', 'node',
         manifest['images']['projects'], 'db/suite-objects.js', 'import', '/backup'], log)
    compose(target, 'up', '-d', '--no-deps', 'projects', log=log)
    write_private(destination / 'restored-from.json', json.dumps({'backup': str(source), 'isolated': True}))
    print(json.dumps({'restore': str(destination), 'network': 'isolated', 'sessions': 'invalidated', 'mail': 'disabled'}))


def verify_authorities(destination):
    """Refresh an unexposed restore with read-only live authority credentials."""
    destination = destination.resolve()
    target = destination / 'compose.json'
    config = json.loads(target.read_text())
    if (config['name'] != destination.name or not destination.name.startswith('suite-projects-restore-')
            or set(config['networks']) != {'default'} or not config['networks']['default'].get('internal')
            or any(service.get('ports') for service in config['services'].values())):
        raise ValueError('An unexposed, isolated Projects restore is required')
    log = destination / 'authorities.private.log'
    live = dict(line.split('=', 1) for line in (STATE / 'backend.env').read_text().splitlines() if line)
    attached = []
    network = destination.name + '_default'
    try:
        for container, alias in [('suite-local-people-1', 'verify-people'), ('st-deploycenter-backend-dev-1', 'verify-st')]:
            run(['docker', 'network', 'connect', '--alias', alias, network, container], log)
            attached.append(container)
        overrides = {
            'SUITE_DIRECTORY_URL': 'http://verify-people:8000' + urlsplit(live['SUITE_DIRECTORY_URL']).path,
            'SUITE_POLICY_URL': 'http://verify-st:8000' + urlsplit(live['SUITE_POLICY_URL']).path,
            'SUITE_DIRECTORY_TOKEN_FILE': '/run/verify/read', 'SUITE_POLICY_TOKEN_FILE': '/run/verify/policy',
            'SUITE_APPROVED_ISSUERS': live.get('SUITE_APPROVED_ISSUERS', live['OIDC_ISSUER']),
            'SUITE_DIRECTORY_APP_ID': live.get('SUITE_DIRECTORY_APP_ID', 'projects'),
        }
        args = ['run', '--rm', '--no-deps', '--entrypoint', 'node']
        for key, value in overrides.items():
            args += ['-e', key + '=' + value]
        args += ['-v', str(STATE / 'keys/read_key') + ':/run/verify/read:ro',
                 '-v', str(STATE / 'keys/policy_key') + ':/run/verify/policy:ro',
                 'projects', 'db/suite-authorities.js']
        result = compose(target, *args, log=log)
        report = json.loads(result.decode().strip())
        write_private(destination / 'authority-verification.json', json.dumps(report, indent=2))
        print(json.dumps(report))
    finally:
        for container in reversed(attached):
            run(['docker', 'network', 'disconnect', network, container], log)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status', 'backup', 'restore', 'verify-authorities', 'cleanup-restore'])
    parser.add_argument('path', type=Path, nargs='?')
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE / 'operations.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        log = STATE / 'operations.private.log'
        if args.action == 'backup' and args.path:
            backup(args.path)
        elif args.action == 'restore' and args.path and args.destination:
            restore(args.path, args.destination)
        elif args.action == 'verify-authorities' and args.path:
            verify_authorities(args.path)
        elif args.action == 'cleanup-restore' and args.path:
            config = json.loads((args.path / 'compose.json').read_text())
            if config['name'] != args.path.name or not args.path.name.startswith('suite-projects-restore-'):
                raise ValueError('Not an isolated Projects restore')
            compose(args.path / 'compose.json', 'down', '-v', log=log)
            print('Isolated restore containers and volumes removed; files retained privately.')
        elif args.action in ('start', 'stop', 'status'):
            command = {'start': ('up', '-d', '--wait', '--wait-timeout', '90', '--no-deps', 'projects'), 'stop': ('stop', 'projects'),
                       'status': ('ps', '--format', '{{.Name}} {{.State}} {{.Health}}')}[args.action]
            result = compose(STATE / 'compose.json', *command, log=log)
            print(result.decode().strip() or ('Projects ' + args.action + ' complete.'))
            if args.action == 'status':
                result = compose(STATE / 'compose.json', 'exec', '-T', 'projects', 'node', 'db/suite-status.js', log=log)
                print(result.decode().strip())
        else:
            parser.error('Path/destination required for this operation')


if __name__ == '__main__':
    main()
