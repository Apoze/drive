"""Operate only suite-mail; restore backups into an isolated, non-serving project."""

import argparse
import copy
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data/messages-calendars-local"
DATABASES = ("messages", "calendars", "caldav")
WRITERS = ("messages-frontend", "calendars-frontend", "mta-in", "messages-worker",
           "calendars-worker", "calendars-reconcile", "messages", "calendars", "caldav", "mail-s3")


def run(command, log, *, data=None, output=None):
    """Diagnostics can contain sensitive data: retain them only in private state."""
    result = subprocess.run(command, input=data, stdout=output or subprocess.PIPE,
                            stderr=subprocess.PIPE)
    with log.open("ab") as stream:
        stream.write(result.stderr)
    if result.returncode:
        raise RuntimeError(f"Operation failed; private diagnostic: {log}")
    return result.stdout


def compose(path, *arguments, log, data=None, output=None):
    return run(["docker", "compose", "-f", str(path), *arguments], log, data=data, output=output)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect(name, log):
    return json.loads(run(["docker", "inspect", name], log))[0]


def runtime_image(runtime, log):
    """Resolve a removed OCI index only when its running platform is identical."""
    previous = runtime["Image"]
    if subprocess.run(["docker", "image", "inspect", previous], capture_output=True).returncode == 0:
        return previous
    descriptor = runtime.get("ImageManifestDescriptor", {})
    platform = descriptor.get("platform", {})
    if not descriptor.get("digest") or not platform.get("os") or not platform.get("architecture"):
        raise ValueError("Running image unavailable; no platform digest can prove equivalence")
    name = "/".join(platform[key] for key in ("os", "architecture", "variant") if platform.get(key))
    index = json.loads(run(["docker", "image", "inspect", runtime["Config"]["Image"]], log))[0]
    candidate = json.loads(run(["docker", "image", "inspect", "--platform", name, index["Id"]], log))[0]
    if candidate.get("Descriptor", {}).get("digest") != descriptor["digest"]:
        raise ValueError("Current image tag differs from the running platform; backup refused")
    return index["Id"]


def backup(destination):
    destination = destination.resolve()
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    log = destination / "diagnostic.private.log"
    path = STATE / "compose.json"
    config = json.loads(path.read_text())
    if config["name"] != "suite-mail":
        raise ValueError("Unexpected source project")
    runtimes = {name: inspect(f"suite-mail-{name}-1", log) for name in config["services"]}
    running = [name for name in WRITERS if runtimes[name]["State"]["Running"]]
    postgres = inspect("suite-local-suite-postgres-1", log)
    pg_env = dict(value.split("=", 1) for value in postgres["Config"]["Env"])
    manifest = {"format": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "images": {name: runtime_image(value, log) for name, value in runtimes.items()},
                "postgres_image": runtime_image(postgres, log), "repositories": {}, "files": {}}
    images = sorted(set(manifest["images"].values()) | {manifest["postgres_image"]})
    for image in images:
        run(["docker", "image", "inspect", image], log)
    # Keep exact runtime images, including local builds with no published registry tag.
    # Saving once per distinct image lets Docker deduplicate their shared layers.
    with log.open("ab") as errors, gzip.open(destination / "images.tar.gz", "wb", compresslevel=1) as archive:
        process = subprocess.Popen(["docker", "image", "save", *images], stdout=subprocess.PIPE, stderr=errors)
        try:
            shutil.copyfileobj(process.stdout, archive, 1024 * 1024)
        finally:
            process.stdout.close()
            if process.wait():
                raise RuntimeError(f"Image backup failed; private diagnostic: {log}")
    # Source binds are part of the running LAN revision, including uncommitted work.
    for app in ("messages", "calendars"):
        repo = ROOT.parent / app
        names = run(["git", "-C", str(repo), "ls-files", "-z", "--cached", "--others", "--exclude-standard"], log)
        with tarfile.open(destination / f"{app}-source.tar.gz", "w:gz") as archive:
            for name in sorted(set(names.decode().split("\0")) - {""}):
                source = repo / name
                if source.exists() or source.is_symlink():
                    archive.add(source, arcname=name, recursive=False)
        manifest["repositories"][app] = run(["git", "-C", str(repo), "rev-parse", "HEAD"], log).decode().strip()
    with tarfile.open(destination / "configuration.tar.gz", "w:gz") as archive:
        for file in STATE.rglob("*"):
            if file.is_file() and not file.name.endswith(".log"):
                archive.add(file, arcname=str(file.relative_to(STATE)))
    try:
        # No mail/calendar writer remains while the three databases and blobs are copied.
        compose(path, "stop", "-t", "45", *running, log=log)
        for app in DATABASES:
            with (destination / f"{app}.dump").open("wb") as output:
                run(["docker", "exec", "suite-local-suite-postgres-1", "pg_dump",
                     "-U", pg_env.get("POSTGRES_USER", "postgres"), "-Fc", "--no-owner",
                     "--no-acl", app], log, output=output)
        volume = next(m["Name"] for m in runtimes["mail-s3"]["Mounts"] if m["Destination"] == "/data")
        with (destination / "blobs.tar").open("wb") as output:
            run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "tar",
                 "-v", volume + ":/snapshot:ro", manifest["images"]["mail-s3"],
                 "-C", "/snapshot", "-cf", "-", "."], log, output=output)
        for file in destination.iterdir():
            if file.name != log.name:
                manifest["files"][file.name] = digest(file)
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2))
    finally:
        # Even a failed backup restores exactly the previously running services.
        if running:
            compose(path, "start", *running, log=log)
    print(json.dumps({"backup": str(destination), "databases": 3, "blobs": True}))


INVALIDATE = '''
import json, sys
from django.apps import apps
from django.test.utils import override_settings
from encrypted_fields.fields import EncryptedFieldMixin
from django.contrib.sessions.models import Session
from django.db import transaction
from suite_identity.models import Account, DirectoryState, IdentityBinding
from core.models import Channel
from django.conf import settings
from django.utils import timezone
payload=json.load(sys.stdin)
with transaction.atomic():
 # Rotate signing/session keys without losing encrypted channel metadata or DKIM keys.
 # Old keys exist only in this offline process, never in a serving Signer fallback.
 with override_settings(SECRET_KEY_FALLBACKS=[payload['old_secret']]):
  for model in apps.get_models():
   fields=[field for field in model._meta.fields if isinstance(field, EncryptedFieldMixin)]
   if not fields: continue
   for field in fields:
    field.__dict__.pop('f',None); field.__dict__.pop('keys',None)
   for row in model.objects.only('pk',*[field.name for field in fields]).iterator(chunk_size=100):
    model.objects.filter(pk=row.pk).update(**{field.name:getattr(row,field.name) for field in fields})
   for field in fields:
    field.__dict__.pop('f',None); field.__dict__.pop('keys',None)
 Session.objects.all().delete()
 Channel.objects.all().update(is_active=False)
 Account.objects.all().update(active=False, checked_at=None, policy_allowed=False,
                             policy_checked_at=None, policy_observed_at=None)
 IdentityBinding.objects.all().update(enabled=False)
 DirectoryState.objects.all().update(checked_at=None, last_error='restoration_requires_reconcile')
 if settings.SUITE_APP_ID == 'messages':
  from core.models import InboundMessage, MessageRecipient
  from core.enums import MessageDeliveryStatusChoices
  InboundMessage.objects.filter(abandoned_at__isnull=True).update(
   abandoned_at=timezone.now(), error_message='restored_do_not_replay')
  MessageRecipient.objects.filter(delivered_at__isnull=True, message__is_sender=True, message__is_draft=False).update(
   delivery_status=MessageDeliveryStatusChoices.CANCELLED, retry_at=None, delivery_message='restored_do_not_replay')
assert not Session.objects.exists()
assert not Channel.objects.filter(is_active=True).exists()
assert not Account.objects.filter(active=True).exists()
print('RESULT credentials_disabled')
'''

HEALTH = '''
import json, smtplib, time
import requests
from django.conf import settings
from django.utils import timezone
from django.db.models import Min
from suite_identity.models import DirectoryState
report = {'app': settings.SUITE_APP_ID}
def age(value):
 return None if value is None else max(0, round((timezone.now()-value).total_seconds()))
def probe(name, operation):
 started=time.monotonic()
 try:
  operation()
  report[name]={'ok': True, 'ms': round((time.monotonic()-started)*1000)}
 except Exception as error:
  report[name]={'ok': False, 'error': type(error).__name__}
def http(url):
 response=requests.get(url, timeout=5, allow_redirects=False)
 response.raise_for_status()
report['directory_age_seconds']=age(DirectoryState.objects.aggregate(oldest=Min('checked_at'))['oldest'])
probe('api', lambda: http('http://localhost:8000/api/v1.0/config/'))
if settings.SUITE_APP_ID == 'messages':
 from core.models import InboundMessage, MessageRecipient, StorageBudget
 from core.services.antivirus import scan_bytes
 from django.core.files.storage import storages
 from core.enums import MessageDeliveryStatusChoices
 from core.utils import get_redis_client
 from core.services.search.coalescer import PENDING_REINDEX_KEY
 from messages.celery_app import app
 report['search_pending_threads']=get_redis_client().scard(PENDING_REINDEX_KEY)
 report['periodic_tasks']=len(app.conf.beat_schedule)
 pending=InboundMessage.objects.filter(abandoned_at__isnull=True)
 report['inbound']={'pending': pending.count(), 'oldest_age_seconds': age(pending.aggregate(oldest=Min('created_at'))['oldest']),
                    'quarantined': InboundMessage.objects.filter(abandoned_at__isnull=False).count()}
 report['outbound_failed']=MessageRecipient.objects.filter(delivery_status=MessageDeliveryStatusChoices.FAILED).count()
 report['storage_policy_age_seconds']=age(StorageBudget.objects.exclude(kind='domain').aggregate(oldest=Min('checked_at'))['oldest'])
 probe('redis', lambda: get_redis_client().ping())
 probe('antivirus', lambda: scan_bytes(b'Suite mail health probe'))
 probe('antispam', lambda: http('http://rspamd:11333/ping'))
 probe('search', lambda: http('http://opensearch:9200/_cluster/health'))
 def s3():
  for name in ('message-blobs','message-imports'):
   storage=storages[name]
   storage.connection.meta.client.head_bucket(Bucket=storage.bucket_name)
 probe('s3', s3)
 def smtp():
  with smtplib.SMTP('mta-in', 25, timeout=15) as client:
   if client.ehlo()[0] != 250: raise RuntimeError('SMTP greeting failed')
 probe('smtp', smtp)
else:
 from core.suite.scheduling import outbox_request
 # A dedicated read-only operation returns queue counts, never invitation bytes.
 probe('dav', lambda: report.update(scheduling=outbox_request({'operation':'status'})))
print('RESULT '+json.dumps(report))
'''

RESTORE_READ = '''
import hashlib, json
from email.parser import BytesParser
from email import policy
from django.core.files.storage import storages
from django.test import Client
from core.models import Message, Blob, Channel, ArchiveReservation
from core.enums import BlobStorageLocationChoices
result={'mail':0,'attachments':0,'s3_blobs':0,'s3_archives':0}
mail=Message.objects.filter(has_attachments=True, blob__size__lte=32*1024*1024).select_related('blob').order_by('created_at').first()
if mail:
 raw=mail.blob.get_content()
 assert hashlib.sha256(raw).digest()==bytes(mail.blob.sha256)
 parsed=BytesParser(policy=policy.default).parsebytes(raw)
 result['attachments']=sum(1 for part in parsed.walk() if part.get_filename() and part.get_payload(decode=True) is not None)
 assert result['attachments']>0
 result['mail']=1
for blob in Blob.objects.filter(storage_location=BlobStorageLocationChoices.OBJECT_STORAGE, size__lte=32*1024*1024)[:1]:
 assert hashlib.sha256(blob.get_content()).digest()==bytes(blob.sha256)
 result['s3_blobs']+=1
storage=storages['message-imports']
for archive in ArchiveReservation.objects.filter(size_bytes__lte=32*1024*1024).order_by('created_at'):
 if not storage.exists(archive.file_key): continue
 total=0
 with storage.open(archive.file_key,'rb') as stream:
  while chunk:=stream.read(1024*1024): total+=len(chunk)
 assert total==archive.size_bytes
 result['s3_archives']+=1
 break
assert not Channel.objects.filter(is_active=True).exists()
for channel in Channel.objects.only('encrypted_settings').iterator(chunk_size=100):
 assert isinstance(channel.encrypted_settings,dict)
assert Client(HTTP_HOST='localhost').get('/api/v1.0/mailboxes/').status_code in (401,403)
result['anonymous_access_denied']=True
print('RESULT '+json.dumps(result))
'''

RESTORE_EVENT = r'''
require '/var/www/sabredav/vendor/autoload.php';
$pdo=new PDO('pgsql:host=suite-postgres;dbname=caldav',getenv('PGUSER'),getenv('PGPASSWORD'),[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$row=$pdo->query('SELECT co.calendarid,co.uri,ci.id FROM calendarobjects co JOIN calendarinstances ci ON ci.calendarid=co.calendarid AND ci.access=1 ORDER BY co.id LIMIT 1')->fetch(PDO::FETCH_ASSOC);
$count=0;
if($row){
 $backend=new \Calendars\SabreDav\AuditCalDAVBackend($pdo);
 $object=$backend->getCalendarObject([(int)$row['calendarid'],(int)$row['id']],$row['uri']);
 $event=\Sabre\VObject\Reader::read($object['calendardata']);
 if(!$event->VEVENT || !(string)$event->VEVENT->UID) throw new RuntimeException('Restored event unreadable');
 $count=1;
}
echo json_encode(['calendar_event'=>$count]);
'''


def verify_restore(state, log):
    path = state / "compose.json"
    output = compose(path, "exec", "-T", "messages", "python", "manage.py", "shell", "-c", RESTORE_READ, log=log).decode()
    result = json.loads(next(line[7:] for line in output.splitlines() if line.startswith("RESULT ")))
    result.update(json.loads(compose(path, "exec", "-T", "caldav", "php", "-r", RESTORE_EVENT, log=log)))
    (state / "verification.json").write_text(json.dumps(result, indent=2))
    return result


def restore_isolated(source):
    """No API, worker, SMTP process, external network, host port or old Redis state."""
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest["format"] != 1:
        raise ValueError("Unsupported backup")
    for name, expected in manifest["files"].items():
        if Path(name).name != name or digest(source / name) != expected:
            raise ValueError("Backup integrity failure")
    if "images.tar.gz" not in manifest["files"]:
        raise ValueError("Backup lacks its exact runtime images")
    name = "suite-mail-restore-" + secrets.token_hex(5)
    state = ROOT / "data/messages-calendars-restore" / name
    state.mkdir(mode=0o700, parents=True, exist_ok=False)
    log = state / "diagnostic.private.log"
    images = set(manifest["images"].values()) | {manifest["postgres_image"]}
    if any(subprocess.run(["docker", "image", "inspect", image], capture_output=True).returncode for image in images):
        run(["docker", "image", "load", "-i", str(source / "images.tar.gz")], log)
    for archive_name, target in (("configuration", "config"), ("messages-source", "messages"),
                                 ("calendars-source", "calendars")):
        with tarfile.open(source / (archive_name + ".tar.gz")) as archive:
            archive.extractall(state / target, filter="data")
        if target != "config":
            for directory in (state / target).rglob("*"):
                if directory.is_dir():
                    directory.chmod(0o755)
    for app in ("messages", "calendars"):
        keys = state / "config" / app / "keys"
        for file in [keys, *keys.rglob("*")]:
            os.chown(file, 1000, 1000)
    os.chown(state / "config/s3.json", 1000, 1000)
    original = json.loads((state / "config/compose.json").read_text())
    password = secrets.token_urlsafe(40)
    pg_env = state / "postgres.env"
    pg_env.write_text("POSTGRES_PASSWORD=" + password + "\n")
    services = {"suite-postgres": {"image": manifest["postgres_image"], "env_file": [str(pg_env)],
                 "volumes": ["postgres:/var/lib/postgresql/data"],
                 "healthcheck": {"test": ["CMD", "pg_isready", "-U", "postgres"],
                                 "interval": "2s", "timeout": "2s", "retries": 30}}}
    for app in ("mail-s3", "messages", "calendars", "caldav"):
        service = copy.deepcopy(original["services"][app])
        service.pop("networks", None)
        service.pop("restart", None)
        service.pop("ports", None)
        service["image"] = manifest["images"][app]
        if app == "mail-s3":
            service["volumes"] = ["blobs:/data", f"{state}/config/s3.json:/etc/seaweedfs/s3.json:ro"]
            service["healthcheck"] = {"test": ["CMD", "nc", "-z", "mail-s3", "8333"],
                                      "interval": "3s", "timeout": "2s", "retries": 30}
        else:
            env = dict(line.split("=", 1) for line in (state / "config" / (
                "caldav.env" if app == "caldav" else app + "/backend.env")).read_text().splitlines() if "=" in line)
            if app == "caldav":
                env.update(PGHOST="suite-postgres", PGUSER="postgres", PGPASSWORD=password)
                service["volumes"] = [f"{state}/calendars/src/caldav/src:/var/www/sabredav/src:ro"]
                service["entrypoint"] = ["sh", "-c", "exec sleep infinity"]
            else:
                env.update(DB_HOST="suite-postgres", DB_USER="postgres", DB_PASSWORD=password,
                           DJANGO_SECRET_KEY=secrets.token_urlsafe(48), SUITE_DIRECTORY_URL="http://unavailable.invalid/",
                           SUITE_POLICY_URL="http://unavailable.invalid/", SUITE_CATALOGUE_URL="http://unavailable.invalid/",
                           EMAIL_HOST="unavailable.invalid", MTA_OUT_RELAY_HOST="unavailable.invalid:25")
                service["volumes"] = [f"{state}/{app}/src/backend:/app:ro",
                                       f"{state}/config/{app}/keys:/run/suite:ro"]
                service["entrypoint"] = ["python", "-c", "import time; time.sleep(2147483647)"]
            service["command"] = []
            private_env = state / (app + ".env")
            private_env.write_text("\n".join(key + "=" + value for key, value in env.items()) + "\n")
            service["env_file"] = [str(private_env)]
        services[app] = service
    config = {"name": name, "services": services, "networks": {"default": {"internal": True}},
              "volumes": {"postgres": {}, "blobs": {}}}
    path = state / "compose.json"
    path.write_text(json.dumps(config, indent=2))
    compose(path, "create", log=log)
    # Only the new project's empty volume is writable; the source backup is read-only.
    run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "tar",
         "-v", name + "_blobs:/snapshot", "-v", str(source) + ":/backup:ro",
         manifest["images"]["mail-s3"], "-C", "/snapshot", "-xf", "/backup/blobs.tar"], log)
    compose(path, "up", "-d", "--wait", "suite-postgres", "mail-s3", log=log)
    for app in DATABASES:
        compose(path, "exec", "-T", "suite-postgres", "createdb", "-U", "postgres", app, log=log)
        # pg_restore streams from the host; do not load database archives into RAM.
        with (source / (app + ".dump")).open("rb") as stream, log.open("ab") as errors:
            result = subprocess.run(["docker", "compose", "-f", str(path), "exec", "-T", "suite-postgres",
                                     "pg_restore", "-U", "postgres", "--no-owner", "--no-acl", "--exit-on-error",
                                     "-d", app], stdin=stream, stdout=errors, stderr=errors)
        if result.returncode:
            raise RuntimeError(f"Database restore failed; private diagnostic: {log}")
    compose(path, "start", "messages", "calendars", "caldav", log=log)
    for app in ("messages", "calendars"):
        old = dict(line.split("=", 1) for line in (state / f"config/{app}/backend.env").read_text().splitlines() if "=" in line)
        compose(path, "exec", "-T", app, "python", "manage.py", "shell", "-c", INVALIDATE, log=log,
                data=json.dumps({"old_secret": old["DJANGO_SECRET_KEY"]}).encode())
    compose(path, "exec", "-T", "suite-postgres", "psql", "-X", "-U", "postgres", "-d", "caldav",
            "-v", "ON_ERROR_STOP=1", "-c", "UPDATE suite_scheduling_outbox SET failed=TRUE, "
            "error_code='restored_do_not_replay' WHERE delivered_at IS NULL; "
            "UPDATE calendarinstances SET authorization_until=0 WHERE is_sync_managed=TRUE; "
            "UPDATE suite_calendar_group_members SET authorization_until=0;", log=log)
    (state / "source.json").write_text(json.dumps({"backup": str(source), "sha256": digest(source / "manifest.json")}))
    result = verify_restore(state, log)
    print(json.dumps({"restored": str(state), "serving": False, "external_network": False,
                      "old_credentials": "disabled", "old_outbox": "blocked", "readback": result}))


AUTHORITIES = '''
import json
from django.conf import settings
from django.test.utils import override_settings
from django.contrib.sessions.models import Session
from suite_identity.directory import synchronize
from suite_identity.policy import synchronize_policy
from suite_identity.models import Account
from core.models import Channel
before={}
if settings.SUITE_APP_ID=='messages':
 from core.models import MailboxAccess
 before=dict(MailboxAccess.objects.values_list('pk','role'))
with override_settings(SUITE_DIRECTORY_URL='http://people:8000/api/v1.0/suite-directory/',
                       SUITE_POLICY_URL='http://st:8000/api/v1.0/suite-policy/'):
 synchronize();synchronize_policy()
 if settings.SUITE_APP_ID=='messages':
  from core.suite.storage import synchronize_storage
  synchronize_storage()
 else:
  from core.suite.calendar_groups import synchronize_calendar_groups
  synchronize_calendar_groups()
assert not Session.objects.exists()
assert not Channel.objects.filter(is_active=True).exists()
result={'app':settings.SUITE_APP_ID,'current_accounts':Account.objects.filter(active=True,policy_allowed=True).count(),
        'old_sessions':0,'active_old_channels':0}
if settings.SUITE_APP_ID=='messages':
 after=dict(MailboxAccess.objects.values_list('pk','role'))
 result['downgraded_mailbox_grants']=sum(after.get(key,0)<role for key,role in before.items())
print('RESULT '+json.dumps(result))
'''


def verify_authorities(state):
    """Reconcile against the live authorities without giving the restore an egress route."""
    state = state.resolve()
    if state.parent != (ROOT / 'data/messages-calendars-restore').resolve():
        raise ValueError('An isolated restore directory is required')
    path = state / 'compose.json'
    config = json.loads(path.read_text())
    if (config['name'] != state.name or not state.name.startswith('suite-mail-restore-')
            or not config['networks']['default'].get('internal')
            or any(service.get('ports') for service in config['services'].values())):
        raise ValueError('Restore isolation does not match the qualification contract')
    log = state / 'authorities.private.log'
    network = state.name + '_default'
    attached = []
    reports = []
    try:
        # Attach only the two existing authorities to the INTERNAL restore network.
        # Restored containers keep no external route; no MTA or worker is started.
        for container, alias in (('suite-local-people-1', 'people'), ('st-deploycenter-backend-dev-1', 'st')):
            run(['docker', 'network', 'connect', '--alias', alias, network, container], log)
            attached.append(container)
        compose(path, 'exec', '-T', '-d', 'caldav', 'apache2-foreground', log=log)
        compose(path, 'exec', '-T', 'caldav', 'php', '-r',
                'for($i=0;$i<50;$i++){ $s=@fsockopen("127.0.0.1",80,$e,$m,0.2); if($s){fclose($s);exit(0);} usleep(100000);} exit(1);', log=log)
        for app in ('messages', 'calendars'):
            output = compose(path, 'exec', '-T', app, 'python', 'manage.py', 'shell', '-c', AUTHORITIES, log=log).decode()
            reports.append(json.loads(next(line[7:] for line in output.splitlines() if line.startswith('RESULT '))))
        (state / 'authority-verification.json').write_text(json.dumps(reports, indent=2))
        print(json.dumps({'current_authorities': reports, 'external_network': False, 'smtp_started': False}))
    finally:
        failures = []
        try:
            compose(path, 'exec', '-T', 'caldav', 'apachectl', '-k', 'stop', log=log)
        except RuntimeError:
            failures.append('dav')
        for container in reversed(attached):
            try:
                run(['docker', 'network', 'disconnect', network, container], log)
            except RuntimeError:
                failures.append(container)
        if failures:
            raise RuntimeError('Restore isolation cleanup failed; see private diagnostic')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "status", "backup", "restore-isolated", "verify-authorities", "remove-restore"))
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()
    with (STATE / "operations.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        log = STATE / "operations.private.log"
        path = STATE / "compose.json"
        if args.action == "backup":
            backup(args.path or ROOT / "data/messages-calendars-backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        elif args.action == "restore-isolated":
            if args.path is None:
                parser.error("--path must identify a complete backup")
            restore_isolated(args.path)
        elif args.action == 'verify-authorities':
            if args.path is None:
                parser.error('--path must identify an isolated restore directory')
            verify_authorities(args.path)
        elif args.action == "remove-restore":
            if args.path is None or args.path.resolve().parent != (ROOT / "data/messages-calendars-restore").resolve():
                parser.error("--path must identify an isolated restore directory")
            config = json.loads((args.path / "compose.json").read_text())
            if config["name"] != args.path.name or not config["name"].startswith("suite-mail-restore-"):
                raise ValueError("Invalid restore project")
            compose(args.path / "compose.json", "down", "--volumes", log=log)
            shutil.rmtree(args.path)
            print("Isolated restore removed; LAN data unchanged.")
        elif args.action == "status":
            degraded = False
            print(compose(path, "ps", "--format", "{{.Service}} {{.State}} {{.Health}}", log=log).decode())
            for app in ("messages", "calendars"):
                output = compose(path, "exec", "-T", app, "python", "manage.py", "shell", "-c", HEALTH, log=log).decode()
                report = json.loads(next(line[7:] for line in output.splitlines() if line.startswith("RESULT ")))
                print(json.dumps(report))
                degraded |= any(isinstance(value, dict) and value.get('ok') is False for value in report.values())
                degraded |= report['directory_age_seconds'] is None or report['directory_age_seconds'] > 90
                if app == 'messages':
                    degraded |= report['storage_policy_age_seconds'] is None or report['storage_policy_age_seconds'] > 90
            print(json.dumps({"host_free_bytes": shutil.disk_usage(ROOT).free}))
            if degraded:
                raise SystemExit(1)
        else:
            compose(path, *( ["up", "-d"] if args.action == "start" else ["stop", "-t", "45"]), log=log)
            print("suite-mail " + args.action + " complete; other projects unchanged.")


if __name__ == "__main__":
    main()
