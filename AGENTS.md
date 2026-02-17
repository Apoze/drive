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

This project uses:
- Primary object storage via S3 (SeaweedFS S3-compatible). :contentReference[oaicite:1]{index=1}
- A MountProvider framework that can expose filesystem-like mounts (e.g., SMB) and other storage backends in the future.

Non-negotiable:
- Any new feature/fix touching files (read/write/preview/convert/archive/extract/search) MUST remain compatible with BOTH:
  1) S3 object storage (no local paths)
  2) MountProvider-backed filesystem storage (local/SMB-like semantics)

Guidelines:
1) Do not assume local filesystem paths.
   - Django Storage backends may NOT implement `path()` (object storage often doesn’t). Use the Storage API (`open`, `save`, `exists`, etc.) unless you explicitly detect a local-path capable backend.

2) Capability-based behavior (degrade gracefully):
   - If a feature requires filesystem-only capabilities (e.g., atomic rename, file locking, `path()`, hardlinks/symlinks), it must:
     - either be implemented in a backend-agnostic way, OR
     - be reduced/disabled for storages that don’t support the required capability, with a clear user-facing message.
   - Prefer explicit capability checks over brittle storage-type checks.

3) Security differences between S3 and filesystem mounts:
   - On filesystem/mount backends, be extra careful with path traversal and symlink attacks (a common class of issues when extracting archives or writing files).
   - When writing/extracting to a filesystem, never allow `..` / absolute paths, and ensure writes cannot escape the destination even via symlinks (fail closed if safety cannot be guaranteed).
   - On SMB mounts, archive extraction is allowed only with SMB hardening + MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT=true

### SMB / Mount hardening (required for server-side archive extract)

We support server-side archive extraction to MountProvider-backed SMB mounts ONLY when the SMB server is hardened against symlink traversal.

Policy:
- Extraction/unzip to MountProvider mounts MUST be **refused explicitly** unless `MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT=true` (env var).
- When refused, return a clear user-facing error: “Mount non hardené pour extraction (SMB hardening requis)”.

Why:
- On SMB, path resolution happens on the server. If the server follows symlinks (or wide links), archive extraction can escape the destination folder even if the Drive permission model allows the write.

Required SMB server configuration (Samba/TrueNAS “hardened” profile):
- Share options:
  - `follow symlinks = no`
  - `wide links = no`
- Global:
  - `allow insecure wide links = no` (must NOT be enabled)
Notes:
- Samba documents that `wide links` is automatically disabled when UNIX extensions are enabled “for security purposes”, and `allow insecure wide links` exists specifically to bypass that protection. We must not rely on insecure wide links.
- TrueNAS users commonly add `allow insecure wide links = yes` in “Auxiliary Parameters” to restore legacy wide-links behavior; this is explicitly described as a security tradeoff. Do not enable it for mounts intended for extraction.

Operational guideline:
- If you need symlink traversal for a share, that share is NOT eligible for server-side archive extraction in Drive.
- The mount admin is responsible for ensuring the SMB server is configured as above before enabling `MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT=true`.

Implementation guideline (capability gating):
- Treat `MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT` as a global safety gate for any “write many paths” operation to mounts (unzip/extract, archive extraction, bulk restore).
- S3/object storage is unaffected by this env var.


4) Streaming / memory constraints:
   - Avoid loading entire files into RAM. Prefer streaming reads/writes.
   - Ensure large operations (zip/unzip/conversions) remain server-side and async where needed.

5) Testing requirement:
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
 - Default E2E origins target the LAN dev stack (`http://192.168.10.123:*`). CI uses `make run-tests-e2e-from-scratch` which forces `http://localhost:*` origins.

Docker environment notes:
- Official Playwright Docker images are Ubuntu-based and include browser deps; the runner image must be pinned to match `@playwright/test`. (Playwright docs)
- Alpine/musl is not officially supported by Playwright browser builds; do not rely on `frontend-dev` (Alpine) for CI E2E runs.

Artifacts (CI evidence):
- HTML report: `src/frontend/apps/e2e/playwright-report/`
- Raw results + traces/videos/screenshots: `src/frontend/apps/e2e/test-results/` (e.g. `**/trace.zip` on failure/retry)

Selector stability:
- Prefer Playwright locators / best practices to keep tests resilient.
- Prefer stable user-facing attributes (role/text/testid) over brittle CSS/XPath.
