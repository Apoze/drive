# Docker-first backup / restore runbook

This runbook targets the **Docker Compose baseline** (DB + S3-compatible object
storage + optional dev fixtures).

It is written to be **deterministic** and **no-leak**:

- do not paste secrets (credentials, tokens) into terminals, docs, or artifacts,
- prefer `--env-file` over inline env vars (avoid shell history leaks),
- do not log or export signed URLs or SigV4 headers.

## What you must back up (in scope)

1. **Database (PostgreSQL)**: Drive metadata (items, permissions, shares, etc.).
2. **Every configured S3 destination**: all keys, prefixes, versions and
   publication metadata, including retained transfer sources and previews.
3. **Every native namespace**: files and private recovery entries, with a
   consistent filesystem/server snapshot when stable file identities matter.
4. **Private configuration**: the storage vault master key, external secret
   references, private CA bundles and deployment configuration. Back up the
   vault key separately from the encrypted database and restrict both.
5. **ST and identity provider state**: matching quota policies, service
   configuration and user identities, plus any fixtures actually in use.

Inventory connections by namespace: two NAS accounts exposing the same data
are views of one physical namespace, not two independent backups. Conversely,
backing up the default S3 bucket does not cover additional S3 connections.

## What you do not need to back up (out of scope)

- Redis / caches
- Mailcatcher
- ephemeral worker state

## Backup procedure

### 0) Quiesce writes (recommended)

For a consistent backup, close editor sessions, stop new admissions, reconcile
uncertain publications, and stop every Drive worker and scheduler that can
write. Record the remaining retained-source journals with the backup. Coordinate
direct NAS clients with the NAS snapshot; stopping Drive does not stop them.

For the development Compose baseline, stop app components:

- `docker compose stop frontend-dev app-dev celery-dev celery-beat-dev`

If you cannot stop traffic (production), use your DB/S3 provider’s snapshotting
tools instead (provider-specific).

### 1) Backup the PostgreSQL database

Create a local folder for artifacts:

- `mkdir -p backups/`

Dump the DB inside the Postgres container to avoid secrets on the command line:

- `docker compose exec -T postgresql sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --file=/tmp/drive-db.dump'`
- `docker compose cp postgresql:/tmp/drive-db.dump backups/drive-db.dump`

Optional integrity check:

- `docker compose exec -T postgresql sh -lc 'pg_restore --list /tmp/drive-db.dump >/dev/null'`

### 2) Backup object storage (S3 bucket)

Repeat this procedure for **each S3 connection**. A complete recovery must
preserve the configured bucket identity and **all object keys**.
If you exclude prefixes, previews/WOPI/media may break silently.

For a portable copy of current contents, mirror the bucket via the S3 API using
`mc`. This is not a substitute for a full storage snapshot when version IDs or
pending recovery journals must survive:

1. Create a file `backups/s3.env` containing your S3 credentials and endpoint
   (restricted permissions, never commit it).
2. Mirror the bucket to disk:
   - `docker run --rm --env-file backups/s3.env -v "$PWD/backups:/backup" minio/mc sh -lc 'mc alias set drive "$AWS_S3_ENDPOINT_URL" "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" && mc mirror --overwrite drive/drive-media-storage /backup/drive-media-storage'`

Notes:

- If **bucket versioning** is required for your deployment (WOPI), ensure the
  destination bucket has versioning enabled *before* restoring objects.
- Mirroring copies the latest state; preserving full version history is
  provider-specific and may require snapshots/replication.
- Re-uploading an old version usually creates a new version ID. Never resume
  cleanup or editor sessions against rewritten version identities. Keep the
  deployment in maintenance until the retained journals are reviewed.
- Native file copies can change inode/SMB identities. Use a native snapshot
  preserving those identities for transparent recovery of references and
  retained-file journals. An ordinary file mirror is not proof of identity.
- Store the exact Drive/ST image versions, configuration generation and
  database dump alongside the physical snapshot inventory.

### 3) Optional: Keycloak dev fixture

The development compose file does not persist Keycloak’s DB by default (no
volume is configured for `kc_postgresql`). If you added persistence, back up its
Postgres data similarly to the main DB, and keep your realm/config files (e.g.
`docker/auth/realm.json`) under version control.

## Restore procedure

### 0) Safety

- Restore into a **clean** environment when possible (empty DB + empty bucket).
- Keep the DB restore and bucket restore **paired** (same backup point in time).
- Restore all connections and the vault before enabling writers. Use separate
  Docker networks and volumes; restored workers must not contact live storage.
- Do not downgrade to an image that only understands the default S3 bucket
  after unified storage has accepted writes on other connections.

### 1) Restore the PostgreSQL database

Copy the dump into the container:

- `docker compose cp backups/drive-db.dump postgresql:/tmp/drive-db.dump`

Restore (drops/recreates objects in-place):

- `docker compose exec -T postgresql sh -lc 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB" /tmp/drive-db.dump'`

### 2) Restore object storage (S3 bucket)

Prerequisites (must be true before restoring objects):

- the bucket exists (e.g. `drive-media-storage`)
- **bucket versioning is enabled** if your deployment requires WOPI

Mirror back from disk:

- `docker run --rm --env-file backups/s3.env -v "$PWD/backups:/backup" minio/mc sh -lc 'mc alias set drive "$AWS_S3_ENDPOINT_URL" "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" && mc mirror --overwrite /backup/drive-media-storage drive/drive-media-storage'`

### 3) Verify before opening services

Restore the separate vault key and private CA bundles. With admissions still
closed, run the unified storage check and accounting audit, verify each
connection, then read a known file from each S3/native destination. Compare
hashes with the backup inventory, verify quota scopes and the ST policy
revision, and inspect retained publications before enabling scheduled cleanup.

Test one governed write and restore, one quota refusal, one historical share
and one editor save in the isolated environment. Reconnect users after losing
Redis; restore durable jobs from PostgreSQL instead of replaying old tokens.

### 4) Start services

- `docker compose up -d`

## Post-restore smoke checklist (deterministic)

Perform these checks in order; each check must have a clear PASS/FAIL outcome.

1. **Login**
   - Action: log in via your configured OIDC IdP.
   - PASS: you land in Drive with the Explorer visible (no infinite loading).
2. **Browse**
   - Action: open a known workspace/folder.
   - PASS: file list renders; navigation works.
3. **Preview**
   - Action: open preview for a known previewable file.
   - PASS: preview renders, or shows a clear actionable error (no hang).
4. **Upload**
   - Action: upload a small test file.
   - PASS: upload completes and the file appears in the expected folder.
5. **`/media` flow**
   - Action: download/open an existing file that uses the `/media` path.
   - PASS: the file loads; failures are actionable and do not leak secrets.
6. **Public share link (if enabled)**
   - Action: open an existing share link in a private window.
   - PASS: share opens, or shows a clear actionable state (no hang).
