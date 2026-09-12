"""Operate Transfers and restore its completed objects on an isolated network."""

import argparse
import fcntl
import gzip
import json
import os
import secrets
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

from mail_operations import compose, digest, inspect, run, runtime_image
from prepare_local import environment, write_private

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'data/transfers-local'
HELPER = Path(__file__).with_name('transfers_snapshot.py')


def helper(state, action, snapshot, log, compose_path=None):
    script = snapshot / 'snapshot-helper.py' if action != 'status' else HELPER
    mount_mode = '' if action == 'export' else ':ro'
    result = compose(compose_path or state / 'compose.json', 'run', '--rm', '--no-deps', '--user', '0',
                     '-e', 'APOZE_SNAPSHOT_ACTION=' + action,
                     '-v', f'{script}:/snapshot.py:ro', '-v', f'{snapshot}:/backup{mount_mode}',
                     '--entrypoint', 'python', 'transfers', 'manage.py', 'shell', '-c',
                     "exec(compile(open('/snapshot.py','rb').read(),'/snapshot.py','exec'))", log=log)
    return json.loads(result.decode().strip().splitlines()[-1])


def backup(destination):
    if destination.is_relative_to(STATE):
        raise ValueError('The backup must be outside the live state')
    config = json.loads((STATE / 'compose.json').read_text())
    if config['name'] != 'suite-transfers':
        raise ValueError('Unexpected Transfers project')
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    log = destination / 'diagnostic.private.log'
    runtimes = {name: inspect(f'suite-transfers-{name}-1', log) for name in config['services']}
    if any(m['Type'] == 'bind' and (m['Destination'] == '/app' or m['Destination'].startswith('/app/'))
           for runtime in runtimes.values() for m in runtime['Mounts']):
        raise ValueError('Build the exact runtime image before backing up source iteration mounts')
    images = {name: runtime_image(runtime, log) for name, runtime in runtimes.items()}
    for service, container in [('postgres', 'suite-local-suite-postgres-1'),
                               ('storage', 'suite-local-docs-s3-1'), ('redis', 'suite-local-suite-redis-1')]:
        images[service] = runtime_image(inspect(container, log), log)
    shutil.copyfile(HELPER, destination / 'snapshot-helper.py')
    manifest = {'format': 1, 'created_at': datetime.now(timezone.utc).isoformat(), 'images': images}
    with gzip.open(destination / 'images.tar.gz', 'wb', compresslevel=1) as output, log.open('ab') as errors:
        process = subprocess.Popen(['docker', 'image', 'save', *sorted(set(images.values()))],
                                   stdout=subprocess.PIPE, stderr=errors)
        try:
            shutil.copyfileobj(process.stdout, output, 1024**2)
        finally:
            process.stdout.close()
            if process.wait():
                raise RuntimeError('Image backup failed; inspect private diagnostic')
    running = [name for name, runtime in runtimes.items() if runtime['State']['Running']]
    try:
        # Stop the public S3 facade before quiescing database and background writers.
        if 'edge' in running:
            compose(STATE / 'compose.json', 'stop', 'edge', log=log)
        writers = [name for name in running if name != 'edge']
        if writers:
            compose(STATE / 'compose.json', 'stop', '-t', '45', *writers, log=log)
        with (destination / 'transfers.dump').open('wb') as output:
            run(['docker', 'exec', 'suite-local-suite-postgres-1', 'pg_dump', '-U', 'postgres',
                 '-Fc', '--no-owner', '--no-acl', 'transfers'], log, output=output)
        with tarfile.open(destination / 'configuration.tar.gz', 'w:gz') as archive:
            for path in STATE.rglob('*'):
                if path.is_symlink():
                    raise ValueError('Unexpected symlink in Transfers state')
                if path.is_file() and not path.name.endswith(('.log', '.lock', '.pid')):
                    archive.add(path, arcname=str(path.relative_to(STATE)), recursive=False)
        config['services']['transfers']['image'] = images['transfers']
        runtime_config = destination / 'runtime-compose.json'
        write_private(runtime_config, json.dumps(config))
        try:
            manifest['storage'] = helper(STATE, 'export', destination, log, runtime_config)
        finally:
            runtime_config.unlink(missing_ok=True)
        manifest['files'] = {str(path.relative_to(destination)): digest(path)
                             for path in destination.rglob('*') if path.is_file() and path != log}
        write_private(destination / 'manifest.json', json.dumps(manifest, indent=2))
    finally:
        if running:
            compose(STATE / 'compose.json', 'start', *running, log=log)
    return {'backup': str(destination), 'coherent': True, **manifest['storage']}


def isolated(destination):
    config = json.loads((destination / 'compose.json').read_text())
    if (config['name'] != destination.name or not destination.name.startswith('suite-transfers-restore-')
            or set(config['networks']) != {'default'} or not config['networks']['default'].get('internal')
            or any(service.get('ports') for service in config['services'].values())):
        raise ValueError('A private isolated Transfers restore is required')
    return config


def restore(source, destination):
    if destination.is_relative_to(STATE) or destination.is_relative_to(source):
        raise ValueError('Restore outside the live state and source snapshot')
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest['format'] != 1 or not destination.name.startswith('suite-transfers-restore-'):
        raise ValueError('Use a Transfers snapshot and a suite-transfers-restore-* destination')
    for name, expected in manifest['files'].items():
        path = (source / name).resolve()
        if not path.is_relative_to(source) or digest(path) != expected:
            raise ValueError('Backup integrity verification failed')
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    log = destination / 'diagnostic.private.log'
    run(['docker', 'image', 'load', '-i', str(source / 'images.tar.gz')], log)
    private = destination / 'configuration'
    with tarfile.open(source / 'configuration.tar.gz') as archive:
        archive.extractall(private, filter='data')
    values = dict(line.split('=', 1) for line in (private / 'backend.env').read_text().splitlines() if line)
    password = secrets.token_urlsafe(40)
    for key in tuple(values):
        if key.startswith(('SUITE_', 'OIDC_OP_')) and key.endswith(('_URL', '_ENDPOINT')):
            values[key] = 'http://authority-unavailable.invalid/'
    values.update(DATABASE_URL='postgresql://postgres:' + quote(password, safe='') + '@postgres:5432/transfers',
                  DJANGO_SECRET_KEY=secrets.token_urlsafe(48), REDIS_URL='redis://redis:6379/0',
                  CELERY_BROKER_URL='redis://redis:6379/0', OIDC_RP_CLIENT_SECRET=secrets.token_urlsafe(48),
                  AWS_S3_ENDPOINT_URL='http://storage:8333', AWS_S3_DOMAIN_REPLACE='',
                  AWS_S3_ACCESS_KEY_ID=secrets.token_hex(20), AWS_S3_SECRET_ACCESS_KEY=secrets.token_urlsafe(48),
                  SUITE_MESSAGES_NOTIFICATIONS_URL='', CHAT_PUBLIC_URL='', SUITE_CLAMAV_HOST='scanner-unavailable.invalid',
                  DJANGO_ALLOWED_HOSTS='localhost,transfers', LOGIN_REDIRECT_URL='http://transfers:8000')
    for path in (private / 'keys').iterdir():
        if not path.is_file():
            raise ValueError('Unexpected credential entry')
        write_private(destination / 'keys' / path.name, secrets.token_urlsafe(48), uid=1000)
    os.chown(destination / 'keys', 1000, 1000)
    environment(destination / 'backend.env', values)
    images = manifest['images']
    config = {'name': destination.name, 'networks': {'default': {'internal': True}},
              'volumes': {'postgres': {}, 'storage': {}}, 'services': {
        'postgres': {'image': images['postgres'],
                     'environment': {'POSTGRES_PASSWORD': password, 'POSTGRES_DB': 'transfers'},
                     'volumes': ['postgres:/var/lib/postgresql/data'],
                     'healthcheck': {'test': ['CMD-SHELL', 'pg_isready -U postgres'], 'interval': '2s', 'retries': 30}},
        'redis': {'image': images['redis'], 'command': ['redis-server', '--save', '', '--appendonly', 'no']},
        'storage': {'image': images['storage'],
                    'command': ['server', '-s3', '-dir=/data', '-ip=storage', '-volume.max=32', '-master.volumeSizeLimitMB=1024'],
                    'volumes': ['storage:/data'],
                    'healthcheck': {'test': ['CMD', 'wget', '-qO-', 'http://127.0.0.1:9333/cluster/status'], 'interval': '2s', 'retries': 30}},
        'transfers': {'image': images['transfers'], 'env_file': [str(destination / 'backend.env')],
                      'volumes': [f'{destination}/keys:/run/suite:ro'], 'init': True, 'mem_limit': '768m'},
    }}
    target = destination / 'compose.json'
    write_private(target, json.dumps(config, indent=2))
    compose(target, 'up', '-d', '--wait', '--wait-timeout', '90', 'postgres', 'storage', 'redis', log=log)
    with (source / 'transfers.dump').open('rb') as input_file, log.open('ab') as errors:
        result = subprocess.run(['docker', 'exec', '-i', destination.name + '-postgres-1', 'pg_restore',
                                 '-U', 'postgres', '-d', 'transfers', '--no-owner', '--no-acl', '--exit-on-error'],
                                stdin=input_file, stdout=errors, stderr=errors)
        if result.returncode:
            raise RuntimeError('Database restore failed; inspect private diagnostic')
    report = helper(destination, 'import', source, log)
    write_private(destination / 'restored-from.json', json.dumps({'backup': str(source)}))
    compose(target, 'up', '-d', '--no-deps', 'transfers', log=log)
    return {'restore': str(destination), 'network': 'isolated', 'workers': False, **report}


def verify_authorities(destination, transfer=None):
    """Read current People/ST without publishing stale storage usage or opening access."""
    isolated(destination)
    source = Path(json.loads((destination / 'restored-from.json').read_text())['backup'])
    log = destination / 'authorities.private.log'
    live = dict(line.split('=', 1) for line in (STATE / 'backend.env').read_text().splitlines() if line)
    network = destination.name + '_default'
    attached = []
    try:
        for container, alias in [('suite-local-people-1', 'verify-people'), ('st-deploycenter-backend-dev-1', 'verify-st')]:
            run(['docker', 'network', 'connect', '--alias', alias, network, container], log)
            attached.append(container)
        overrides = {
            'APOZE_SNAPSHOT_ACTION': 'authorities',
            'SUITE_DIRECTORY_URL': 'http://verify-people:8000' + urlsplit(live['SUITE_DIRECTORY_URL']).path,
            'SUITE_POLICY_URL': 'http://verify-st:8000' + urlsplit(live['SUITE_POLICY_URL']).path,
            'SUITE_DIRECTORY_TOKEN_FILE': '/run/verify/read', 'SUITE_POLICY_TOKEN_FILE': '/run/verify/policy',
        }
        if transfer:
            overrides['APOZE_RESTORE_TRANSFER_ID'] = str(transfer)
        args = ['run', '--rm', '--no-deps', '--user', '0', '--entrypoint', 'python']
        for key, value in overrides.items():
            args += ['-e', key + '=' + value]
        args += ['-v', f'{STATE}/keys/read_key:/run/verify/read:ro',
                 '-v', f'{STATE}/keys/policy_key:/run/verify/policy:ro',
                 '-v', f'{HELPER}:/snapshot.py:ro',
                 '-v', f'{source}:/backup:ro',
                 'transfers', 'manage.py', 'shell', '-c',
                 "exec(compile(open('/snapshot.py','rb').read(),'/snapshot.py','exec'))"]
        result = compose(destination / 'compose.json', *args, log=log)
        report = json.loads(result.decode().strip().splitlines()[-1])
        write_private(destination / 'authority-verification.json', json.dumps(report, indent=2))
        return report
    finally:
        failed = []
        for container in reversed(attached):
            try:
                run(['docker', 'network', 'disconnect', network, container], log)
            except RuntimeError:
                failed.append(container)
        if failed:
            raise RuntimeError('Authority network cleanup failed; inspect private diagnostic')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status', 'backup', 'restore', 'verify-restore', 'verify-authorities', 'cleanup-restore'])
    parser.add_argument('path', type=Path, nargs='?')
    parser.add_argument('--destination', type=Path)
    from uuid import UUID
    parser.add_argument('--transfer', type=UUID, help='Finalized transfer to read through the isolated API')
    args = parser.parse_args()
    os.umask(0o077)
    with (STATE / 'operations.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        log = STATE / 'operations.private.log'
        path = args.path.resolve() if args.path else None
        if args.action == 'backup' and path:
            report = backup(path)
        elif args.action == 'restore' and path and args.destination:
            report = restore(path, args.destination.resolve())
        elif args.action == 'verify-authorities' and path:
            report = verify_authorities(path, args.transfer)
        elif args.action in ('verify-restore', 'cleanup-restore') and path:
            isolated(path)
            if args.action == 'cleanup-restore':
                compose(path / 'compose.json', 'down', '-v', log=log)
                report = {'removed': path.name, 'private_files_retained': True}
            else:
                source = Path(json.loads((path / 'restored-from.json').read_text())['backup'])
                report = helper(path, 'verify', source, log)
        elif args.action in ('start', 'stop', 'status'):
            arguments = {'start': ('up', '-d', '--no-build', '--wait', '--wait-timeout', '90'), 'stop': ('stop', '-t', '45'),
                         'status': ('ps', '--format', '{{.Name}} {{.State}} {{.Health}}')}[args.action]
            compose(STATE / 'compose.json', *arguments, log=log)
            report = helper(STATE, 'status', STATE, log) if args.action == 'status' else {'action': args.action}
        else:
            parser.error('Path/destination required for this operation')
        print(json.dumps(report))


if __name__ == '__main__':
    main()
