# AGENTS.md — Apoze Drive (brownfield)

This repository is a brownfield Drive app (Django backend + Next.js/TS frontend).
Your job: make minimal, safe changes that fit existing patterns.

## Non-negotiable
- **Do not break** existing browse, preview, viewers, routing, permissions, or storage behavior.
- Prefer **small, incremental** changes over refactors.
- Keep **existing UI/UX style** (reuse existing layout/components; no redesign).
- If you need to change behavior, add a **test** (or at least a minimal regression check) and document it.

## Security & privacy (mandatory)
- Enforce **authorization** on any API endpoint touched/added.
- Treat all file contents as sensitive: **never log file contents**.
- **No-leak**: never paste secrets/tokens/cookies/auth headers/signed URLs. If any appear in output, mask with `***`.

## Storage compatibility (S3 + MountProvider)

### Scope clarification (important)
- **S3 (Drive items)** is used **directly** via Django Storage / the S3 client. **S3 is not a MountProvider backend.**
- **MountProvider** is used to connect **filesystem-like** storages (SMB/FS/… future providers).
- Goal: minimize visible divergences between backends via a **capabilities contract** and clear UX messaging.

### Guideline — “MountProvider transparency” (nuanced, non SMB-only)

Principle: on the backend/frontend side, **the experience must not depend on the provider** behind MountProvider.
This transparency is achieved by:
1) **Stable API + UX** (same endpoints, same flows, same errors/messages, same limits/caps).
2) **Capabilities contract** as the only source of truth:
   - Forbidden: branching on “SMB vs other provider”.
   - Features/abilities must consult **only** capabilities resolved by MountProvider + mount flags.
3) **Controlled degradation** when a capability is missing:
   - If a feature requires a missing capability, **disable** cleanly (clear message) or apply a **cap** (size/time/count).
   - Forbidden: dangerous fallbacks “it works anyway” (e.g., unbounded full download into RAM).
4) **Provider-agnostic messaging**:
   - Errors/messages returned for mounts must be **generic** (no “SMB” mention) because MountProvider covers multiple backends.
   - Provider-specific details (e.g., Samba/TrueNAS profile) belong in admin docs, not in user-facing messages.

Reminder: any assumption of a “local path” is forbidden. Use Storage API / provider APIs and capabilities; never use `path()` unless capability `local_path` is explicitly true.

This project uses:
- Primary object storage via S3 (SeaweedFS S3-compatible).
- A MountProvider framework that can expose filesystem-like mounts (e.g., SMB) and other storage backends in the future.

Non-negotiable:
- Any new feature/fix touching files (read/write/preview/convert/archive/extract/search) MUST remain compatible with BOTH:
  1) S3 object storage (no local paths)
  2) MountProvider-backed filesystem storage (local/SMB-like semantics)

Guidelines:

1.a) Do not assume local filesystem paths.
   - Django Storage backends may NOT implement `path()` (object storage often doesn’t). Use the Storage API (`open`, `save`, `exists`, etc.) unless you explicitly detect a local-path capable backend.
   - Also, do not assume `storage.url()` provides a directly usable URL (some backends may not support it or may require signed URLs).
   - Note: Django documents that `Storage.url()` may raise `NotImplementedError` for storages that don’t support access by URL.
   - For the frontend, prefer application endpoints (API/edge) that apply auth + streaming + caps uniformly.

1.b) S3-specific APIs (important)
- Any S3/boto usage (e.g., `default_storage.connection.meta.client`, low-level S3 calls) is **S3-only**.
- Such usage must be **encapsulated** in a dedicated S3 service and must never be required from a codepath intended to work with MountProvider.
- Any “shared” feature must go through: (a) Storage API (Items/S3) or (b) Provider API (MountProvider), driven by capabilities.

2) Capability-based behavior (degrade gracefully)
   - If a feature requires filesystem-only capabilities (e.g., atomic rename, file locking, `path()`, hardlinks/symlinks), it must:
     - either be implemented in a backend-agnostic way, OR
     - be reduced/disabled for storages that don’t support the required capability, with a clear user-facing message.
   - Prefer explicit capability checks over brittle storage-type checks.

      Minimal capability catalog (keep names consistent across the codebase):
   - `io.read_stream` (provider can stream-read file contents)
   - `io.write_stream` (provider can stream-write file contents)
   - `io.range_read` (provider supports HTTP Range / seek-like reads)
   - `io.listdir` (provider can list directories / children)
   - `fs.local_path` (provider exposes a real local filesystem path; rare; never assume)
   - `fs.atomic_rename` (provider supports atomic rename/move semantics)
   - `security.safe_for_archive_extract` (SECURITY-SENSITIVE, fail closed)
   - `wopi.putfile_streaming` (PutFile MUST stream; never buffer full body)


   Capability source of truth:
   - Centralize capability resolution (one resolver/service) and derive all UI-facing abilities from it.
   - Avoid scattered `hasattr()`/duck-typing decisions at call sites once a capability exists.
   
   Current vs target note:
   - Today, mount “capabilities” come from two sources:
     1) mount config flags (e.g., `mount.upload`, `mount.preview`, `mount.wopi`, `mount.share_link`)
     2) provider method support (duck-typing), e.g. `open_read`, `open_write`, `rename`, `remove`, `supports_range_reads`
   - Target state: keep config flags, but progressively replace scattered `hasattr()` checks with a single resolver that emits a normalized capability set for both backend decisions and UI-facing abilities.

3) Security differences between S3 and filesystem mounts
   - On filesystem/mount backends, be extra careful with path traversal and symlink attacks (a common class of issues when extracting archives or writing files).
   - When writing/extracting to a filesystem, never allow `..` / absolute paths, and ensure writes cannot escape the destination even via symlinks (fail closed if safety cannot be guaranteed).
   - On MountProvider filesystem-like backends (SMB today, others later), server-side archive extraction is allowed only when the backend is hardened against symlink/path-escape and `MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT=true` (fail closed).

### MountProvider filesystem-like hardening (required for server-side archive extract)

We support server-side archive extraction to **any MountProvider filesystem-like backend** (SMB today, other providers later) ONLY when the destination backend is hardened against symlink/path traversal.

- For **SMB/Samba/TrueNAS**, the “hardened” profile is defined below.
- For other MountProvider backends, an equivalent hardening guarantee must be documented and enforced (i.e., extraction cannot escape the destination via symlinks/reparse points). If the guarantee cannot be established, extraction MUST remain disabled (fail closed).

Policy:
- Extraction/unzip to MountProvider mounts MUST be **refused explicitly** unless `MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT=true` (env var).
- When refused, return a clear user-facing error: “Mount non hardené pour extraction (hardening requis)”.

Note:
- SMB is the current hardening example (Samba/TrueNAS), but the rule and message are **non SMB-only**.

Why:
- On a filesystem-like backend (SMB or other provider), extraction writes “many paths” and the OS/server may follow links (symlinks/reparse points). If the backend follows these links, extraction can **escape** the destination folder.
- For SMB, path resolution happens on the server; if symlinks/wide links are permitted, extraction can escape the share.

Required SMB server configuration (Samba/TrueNAS “hardened” profile):
- Share options:
  - `follow symlinks = no`
  - `wide links = no`
- Global:
  - `allow insecure wide links = no` (must NOT be enabled)

Notes:
- Samba documents that `wide links` is automatically disabled when UNIX extensions are enabled “for security purposes”, and `allow insecure wide links` exists specifically to bypass that protection. We must not rely on insecure wide links.
- TrueNAS users commonly add `allow insecure wide links = yes` in “Auxiliary Parameters” to restore legacy wide-links behavior; this is explicitly described as a security tradeoff. Do not enable it for mounts intended for extraction.

Additional admin note (SMB example only — not a general MountProvider rule):
- `unix extensions` are primarily useful for UNIX CIFS clients (POSIX metadata, symlinks, etc.) and are typically unnecessary for Windows-first SMB usage.
- Regardless of whether `unix extensions` is enabled or not, we must **NOT** enable `allow insecure wide links`, because it bypasses Samba’s safety coupling around `wide links` and can allow link traversal outside the share.

Operational guideline:
- If you need symlink traversal for a share, that share is NOT eligible for server-side archive extraction in Drive.
- The mount admin is responsible for ensuring the SMB server is configured as above before enabling `MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT=true`.

Implementation guideline (capability gating):
- Treat `MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT` as a global safety gate for any “write many paths” operation to mounts (unzip/extract, archive extraction, bulk restore).
- S3/object storage is unaffected by this env var.

### Error contract (backend code + frontend reference) — MountProvider extract refusal

Goal: the frontend shows a single simple user message, but it must also provide an **admin-useful reference** (stable code + request id).
The backend is the **only** source of truth for the error code.

#### Backend (API)
- Use a **stable error code** (machine-readable) for extraction refusal:
  - `error_code = "MOUNT_ARCHIVE_EXTRACT_UNSAFE"`
- Return a **structured** error format (Problem Details / RFC 7807) and include `error_code` + a request identifier:
  - recommended minimum fields: `status`, `title`, `detail`, `error_code`, `request_id`
- Contract rule:
  - The user-facing `title`/`detail` message shown in UI must remain stable and provider-agnostic (:contentReference[oaicite:6]{index=6}- Provider/server specifics belong in admin docs and (optionally) in logs correlated via `request_id`, not in end-user messages.
- If possible, also expose the code via a contract header (à la “x-ms-error-code”):
  - `X-Error-Code: MOUNT_ARCHIVE_EXTRACT_UNSAFE` (or an equivalent internal header)
- The code and message must remain **provider-agnostic** (no SMB mention). SMB details belong in admin docs.

#### Frontend (UI)
- Show **one** clear user message:
  - “Extraction non autorisée : montage non sécurisé pour extraction.”
- Add a “support/admin” line (copyable) pointing to the exact error:
  - `Référence: MOUNT_ARCHIVE_EXTRACT_UNSAFE — Request-ID: <id>`
- The frontend must **not** invent/map codes: it reads `error_code` (or header) + `request_id` from the backend.
- Correlation (Request-ID / Correlation-ID) is “breadcrumbs” to investigate in logs/admin.

4) Streaming / memory constraints
- **WOPI PutFile**: do not use `request.body` (full buffer). Stream from the input stream in chunks (pattern already in place on Mount WOPI).
  - ⚠️ Django/DRF pitfall: reading the stream (`request.read()`/`request.readline()`) then accessing `request.body` triggers `RawPostDataException`.
  - Therefore: never touch `request.body` in PutFile, do not trigger DRF parsing (`request.data`/`request.POST`), and read the stream only once.
  - Require tests proving: (1) `request.body` is not required, (2) no double-read, (3) DRF parsers not invoked.
- Frontend preview: avoid `response.blob()` to display a file (buffers entire file in browser RAM). Prefer a direct `src` pointing to a streaming URL.
- Archive viewer: forbid or strictly cap any fallback that downloads the whole archive into RAM (ZIP Range required).
- Avoid loading entire files into RAM. Prefer streaming reads/writes.
- Ensure large operations (zip/unzip/conversions) remain server-side and async where needed.

5) Testing requirement
- For file features, add tests (or a documented manual test plan) covering both storage modes when possible:
  - S3 mode (object storage path-less)
  - MountProvider mode (filesystem semantics)

## Dev environment (LAN)
- UI: http://192.168.10.123:3000
- API: http://192.168.10.123:8071
- Edge Nginx: http://192.168.10.123:8083
- SeaweedFS S3: http://192.168.10.123:9000
- Collabora: http://192.168.10.123:9980
- ONLYOFFICE: http://192.168.10.123:9981

Notes:
- `env.d/development/common.local` exists (gitignored) and contains LAN overrides. **Do not paste its contents**.

## Workflow expectations
1) Start by checking services:
   - `docker compose ps`
2) Before coding, locate the **wiring** relevant to the task:
   - For MountProvider: check `browse.entry.abilities.*` (backend) vs UI actions (frontend). Never hardcode abilities to `false` if the feature is actually available.
   - where UI routes to viewers / “preview unavailable”
   - which backend endpoints serve file content / preview
   - how permissions are checked
3) Implement incrementally (each step should be runnable/testable).
4) Finish with:
   - list of files changed
   - how to test (commands + URLs + scenarios)
   - brief risk/impact note

## Git rules (default)
- Create a **local** branch for work.
- By default: **no commit / no push / no PR** unless the user explicitly asks you to handle Git/GitHub.
- When asked to do Git/GitHub: verify current branch/state first and avoid destructive history rewrites unless explicitly requested.

## Project conventions (high level)

### Viewer selection / preview routing
- Prefer **explicit allowlists** for specialized viewers (e.g., archive viewers should trigger only for known archive formats).
- Avoid broad fallbacks like “unknown/binary => archive viewer”. If file type is unknown, default to “Preview unavailable” unless it is explicitly eligible for another viewer (e.g., text).
(Keep behavior consistent with existing project routing rules.)

### Long-running operations
- Use async jobs (Celery) for operations that can be slow/large.
- UI should show a non-blocking status (toast/polling or existing progress UI).

## How to run common checks (use what exists in repo)
- Backend tests (example): `bin/pytest -q`
- Frontend lint (example): `docker compose exec -T frontend-dev sh -lc 'cd /home/frontend && yarn lint'`
(Prefer the project’s existing scripts; do not invent new toolchains.)

## Testing guidelines (repo source of truth)

When a change impacts routing/viewers, preview behavior, auth flows, explorer interactions, uploads/downloads, or background jobs:
- You MUST add/update tests and ensure they run locally in our Docker environment.
- Prefer existing “official” commands/scripts already present in the repo. Do not invent new toolchains.

### Official commands / docs (must follow)
- Makefile targets:
  - `make test`, `make test-back`, `make test-back-parallel`
  - `make run-tests-e2e`, `make run-tests-e2e-from-scratch`, `make clear-db-e2e`

⚠️ Important (E2E):
- `make run-tests-e2e-from-scratch` est réservé aux cas où l’utilisateur le demande explicitement (ou CI), car il reconstruit un environnement “from scratch” et peut être long/destructif (DB/fixtures).
- Par défaut, utiliser `make run-tests-e2e` et cibler les specs concernées.

- Contributing checklist:
  - See `CONTRIBUTING.md` (lint + tests)
- E2E Playwright project:
  - See `src/frontend/apps/e2e/package.json` (playwright scripts)
- CI gates / expected artifacts:
  - See `docs/gates-runner.md` (run-report + gate-results)

Expected results:
- Success means exit code 0 and output indicates tests passed.
- CI gates must produce required artifacts described in `docs/gates-runner.md`.

### E2E Playwright requirement (container)
E2E tests MUST exist for new/changed user-visible behavior in explorer/preview/viewers.

Where tests live:
- Use `src/frontend/apps/e2e/` (existing structure). Keep tests focused and stable.

How to run:
- Prefer Makefile targets first (`make run-tests-e2e`).
- `make run-tests-e2e` runs Playwright in the dedicated Ubuntu-based runner container (`e2e-playwright`) so we don’t depend on Alpine/musl browser support in `frontend-dev`.
- Docs (source of truth): `docs/WorkDone/e2e/playwright-plan.md` and `docs/WorkDone/e2e/local-vs-ci.md`.
- Origins (local vs CI):
  - Use the Makefile targets + E2E docs as the source of truth for which origins are used (LAN vs localhost).
  - In general: local dev may target the L:contentReference[oaicite:13]{index=13}rgets localhost origins to satisfy auth/CORS/redirect allowlists.

Docker environment notes:
- Official Playwright Docker images are Ubuntu-based and include browser deps; the runner image must be pinned to match `@playwright/test`. (Playwright docs)
- Alpine/musl is not officially supported by Playwright browser builds; do not rely on `frontend-dev` (Alpine) for CI E2E runs.

Artifacts (CI evidence):
- HTML report: `src/frontend/apps/e2e/playwright-report/`
- Raw results + traces/videos/screenshots: `src/frontend/apps/e2e/test-results/` (e.g. `**/trace.zip` on failure/retry)

Tracing (required for flake debugging):
- Configure Playwright to record traces **on the first retry** (`trace: 'on-first-retry'`).
- Keep traces in `src/frontend/apps/e2e/test-results/**/trace.zip` for failures/retries.

Selector stability:
- Prefer Playwright locators / best practices to keep tests resilient.
- Prefer stable user-facing attributes (role/text/testid) over brittle CSS/XPath.
