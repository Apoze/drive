"""Run inside the pinned Transfers image through Django's management shell."""

import hashlib
import json
import os
import shutil
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone
from boto3.s3.transfer import TransferConfig
from suite_identity.models import Account, DirectoryState, IdentityBinding

from core.models import StoragePolicy, Transfer, TransferFile, TransferRecipient
from core.services.s3 import get_s3_client

root = Path('/backup')
action = os.environ['APOZE_SNAPSHOT_ACTION']
client = get_s3_client()
bucket = settings.AWS_STORAGE_BUCKET_NAME
config = TransferConfig(max_concurrency=1, multipart_chunksize=25 * 1024**2)


def rows():
    with (root / 'objects.jsonl').open() as stream:
        for line in stream:
            yield json.loads(line)


def file_path(row):
    name = row['file']
    if len(name) != 12 or not name.isascii() or not name.isdigit():
        raise ValueError('Invalid snapshot object path')
    return root / 'objects' / name


def invalidate():
    Session.objects.all().delete()
    Account.objects.all().update(active=False, checked_at=None, policy_allowed=False,
                                 policy_checked_at=None, policy_observed_at=None)
    IdentityBinding.objects.all().update(enabled=False)
    # The projection was changed above: its revision cache is no longer valid.
    DirectoryState.objects.all().delete()
    StoragePolicy.objects.all().delete()
    # Uploaded parts are not completed S3 objects. Never reuse their old upload IDs.
    Transfer.objects.all().update(notification_actor={})
    # Browser approvals and native verifiers must not survive a restore.
    TransferFile.objects.exclude(mobile_intake={}).update(mobile_intake={})
    # Keep the claim: clearing its hash would reopen an already consumed link.
    Transfer.objects.exclude(download_session_hash='').update(download_session_expires_at=timezone.now())
    incomplete = TransferFile.objects.filter(upload_completed_at__isnull=True).update(
        upload_id='', deletion_pending=True, import_failed_at=timezone.now(), source_actor={}, import_parts=[])
    TransferRecipient.objects.filter(email_sent_at__isnull=True).update(delivery_state='cancelled')
    return {'sessions': Session.objects.count(), 'active_accounts': Account.objects.filter(active=True).count(),
            'incomplete_uploads_discarded': incomplete, 'mail_replay': False}


if action == 'export':
    os.umask(0o077)
    (root / 'objects').mkdir(exist_ok=False)
    count, size = 0, 0
    with (root / 'objects.jsonl').open('x') as index:
        for page in client.get_paginator('list_objects_v2').paginate(Bucket=bucket):
            for entry in page.get('Contents', []):
                name = f'{count:012d}'
                obj = client.get_object(Bucket=bucket, Key=entry['Key'], IfMatch=entry['ETag'])
                digest = hashlib.sha256()
                actual = 0
                try:
                    with (root / 'objects' / name).open('xb') as output:
                        for chunk in obj['Body'].iter_chunks(chunk_size=1024**2):
                            output.write(chunk)
                            digest.update(chunk)
                            actual += len(chunk)
                finally:
                    obj['Body'].close()
                if actual != entry['Size']:
                    raise ValueError('Object changed while backing up')
                index.write(json.dumps({'key': entry['Key'], 'file': name, 'size': actual,
                                        'sha256': digest.hexdigest(), 'metadata': obj.get('Metadata', {}),
                                        'content_type': obj.get('ContentType', 'application/octet-stream')}) + '\n')
                count += 1
                size += actual
    report = {'objects': count, 'bytes': size}
elif action == 'import':
    client.create_bucket(Bucket=bucket)
    count = 0
    for row in rows():
        path = file_path(row)
        with path.open('rb') as stream:
            if path.stat().st_size != row['size'] or hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                raise ValueError('Snapshot object integrity failed')
        client.upload_file(str(path), bucket, row['key'], Config=config,
                           ExtraArgs={'ContentType': row['content_type'], 'Metadata': row['metadata']})
        count += 1
    report = {'objects_imported': count, **invalidate()}
elif action == 'verify':
    count, size = 0, 0
    for row in rows():
        obj = client.get_object(Bucket=bucket, Key=row['key'])
        digest = hashlib.sha256()
        actual = 0
        try:
            for chunk in obj['Body'].iter_chunks(chunk_size=1024**2):
                digest.update(chunk)
                actual += len(chunk)
        finally:
            obj['Body'].close()
        if actual != row['size'] or digest.hexdigest() != row['sha256']:
            raise ValueError('Restored object differs from snapshot')
        count += 1
        size += actual
    if (Session.objects.exists() or Account.objects.filter(active=True).exists()
            or TransferFile.objects.exclude(mobile_intake={}).exists()):
        raise ValueError('A restored credential was not invalidated')
    report = {'objects_verified': count, 'bytes': size, 'sessions_invalidated': True}
elif action == 'authorities':
    from suite_identity.directory import synchronize
    from suite_identity.policy import synchronize_policy

    transfer_id = os.environ.get('APOZE_RESTORE_TRANSFER_ID')
    transfer = Transfer.objects.get(pk=transfer_id) if transfer_id else None
    def request_json(path):
        request = Request('http://transfers:8000' + path, headers={'X-Forwarded-Proto': 'https'})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def require_denied(path):
        try:
            request_json(path)
        except HTTPError as exc:
            if exc.code in (401, 403, 503):
                return
            raise ValueError('Unexpected restored access response') from None
        raise ValueError('Unreconciled restore served a protected transfer')

    path = f'/api/{settings.API_VERSION}/downloads/{transfer.public_token}/' if transfer else None
    if path:
        require_denied(path)
    try:
        synchronize()
        synchronize_policy()
        if Session.objects.exists():
            raise ValueError('Old sessions survived restoration')
        report = {'current_accounts': Account.objects.filter(active=True, policy_allowed=True).count(),
                  'old_sessions': 0, 'storage_usage_published': False}
        if path:
            request_json(path)
            item = transfer.files.filter(upload_completed_at__isnull=False).order_by('size').first()
            if not item:
                raise ValueError('The transfer has no completed file')
            link = request_json(path + f'files/{item.pk}/download/?as=json')['url']
            if urlsplit(link).netloc != 'storage:8333' or urlsplit(link).scheme != 'http':
                raise ValueError('The restored file must use isolated storage')
            expected = next(row for row in rows() if row['key'] == item.s3_key)
            with urlopen(link, timeout=30) as response:
                digest = hashlib.file_digest(response, 'sha256').hexdigest()
            if digest != expected['sha256']:
                raise ValueError('API download differs from the snapshot')
            report['api_download_verified'] = True
    finally:
        # Qualification is not promotion: never leave a live authorization lease.
        invalidate()
    if path:
        require_denied(path)
        report['access_closed_after_check'] = True
elif action == 'status':
    client.head_bucket(Bucket=bucket)
    state = DirectoryState.objects.order_by('checked_at').first()
    report = {'database': True, 'storage': True,
              'temporary_free_bytes': shutil.disk_usage('/tmp').free,
              'directory_age_seconds': None if not state or not state.checked_at else round((timezone.now()-state.checked_at).total_seconds()),
              'incomplete_uploads': TransferFile.objects.filter(upload_completed_at__isnull=True, deletion_pending=False).count()}
else:
    raise ValueError('Unknown snapshot operation')
print(json.dumps(report))
