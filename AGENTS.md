# AGENTS.md - Apoze Drive

This repository is a brownfield Drive fork: Django/DRF backend, Next.js/TS
frontend, S3-compatible object storage for regular Drive items, and
MountProvider for filesystem-like mounts.

Keep this file short. Codex discovers `AGENTS.md` before work and the default
project instruction budget is 32 KiB; long contracts live in linked docs.

## Read First

Always start with this file. Then read only the docs relevant to the task:

- Product/repo context: `README.md`, `docs/architecture.md`
- Storage, mounts, streaming, WOPI, archive extraction:
  `docs/agent-storage-contract.md`
- Local env and E2E execution:
  `docs/env_freeze_report.md`
  and `docs/WorkDone/e2e/test-execution-contract.md`
- Mount preview parity reference:
  `docs/mounts-preview-correction-plan.md`
- Upstream catch-up:
  `PLANS_catchup_commits.md`
  and `docs/catchup-behind-orchestration.md`
- Browser QA / human-vision testing:
  `docs/qa-browser-testing-contract.md`
- Code-structure architecture review:
  `docs/code-structure-review-lots.md`
  and `docs/code-structure-review-findings.md`
- Code-structure commit and validation plan:
  `docs/code-structure-commit-plan.md`
- Thread-to-thread coordination:
  `docs/agent-thread-coordination-protocol.md`

Priority rule: if another repo doc is less specific or older than this file,
follow this file.

## Non-Negotiable

- Do not break browse, preview, viewers, routing, permissions, storage, WOPI,
  Collabora, or ONLYOFFICE behavior.
- Prefer small, incremental changes that match existing code patterns.
- Keep current UI/UX style; no redesign unless explicitly asked.
- Enforce authorization on any API endpoint touched or added.
- Treat file contents as sensitive. Never log file contents.
- Never paste secrets, tokens, cookies, auth headers, signed URLs, or local
  secret file contents. Mask accidental sensitive output with `***`.
- If behavior changes, add a focused test or document a minimal regression
  check.

## Storage And Mount Rules

Read `docs/agent-storage-contract.md` before touching file read/write,
preview, conversion, archive, extraction, search, upload, download, or WOPI
code.

Core invariants:

- S3 for regular Drive items is direct Django Storage/S3 access; it is not a
  MountProvider backend.
- MountProvider is for filesystem-like providers such as SMB/local/future
  providers.
- Do not assume local filesystem paths. Avoid `storage.path()` unless an
  explicit `fs.local_path` capability says it is available.
- Shared behavior must use Storage API for regular items or Provider API for
  mounts, driven by capabilities.
- Do not branch on provider brand such as SMB. Use the capability contract.
- Keep operations streaming or bounded. Do not load whole files into memory.
- WOPI PutFile must stream the request body once; never use `request.body`,
  `request.data`, or `request.POST` in PutFile paths.
- Mount archive extraction must fail closed unless the documented hardening gate
  allows it. Error code is `MOUNT_ARCHIVE_EXTRACT_UNSAFE`.
- Frontend preview must prefer streaming URLs/direct `src`; avoid
  `response.blob()` for displaying files.

## Frontend And Viewer Rules

- Keep the canonical explorer shell in:
  - `src/frontend/apps/drive/src/features/explorer/components/app-view/AppExplorer.tsx`
  - `src/frontend/apps/drive/src/features/explorer/components/app-view/AppExplorerInner.tsx`
- Keep backend-specific differences in adapters, handlers, and capabilities,
  not in duplicate top-level explorer shells.
- Specialized viewers must use explicit allowlists. Unknown/binary files should
  default to "Preview unavailable".
- Text viewer eligibility comes from the backend `/items/<id>/text/` endpoint.
  The frontend must not spam `/text/`; request it only for selected/explicit
  preview attempts.
- Long-running operations must be async where appropriate and surfaced through
  existing non-blocking UI patterns.

## Workflow

1. Check services first:
   `docker compose ps`
2. Before coding, locate the wiring relevant to the task:
   - `browse.entry.abilities.*` backend vs frontend UI actions
   - viewer/preview routing
   - file-serving endpoints
   - permission checks
3. Work incrementally. Each step should be runnable or inspectable.
4. Finish with files changed, validation performed, test instructions, and
   risk/impact.

Use `rg`/`rg --files` for search. Do not use destructive Git commands unless
the user explicitly asks for them.

## Git Rules

- Create a local branch for work by default.
- No commit, push, PR, or publish unless explicitly requested.
- Respect dirty worktrees. Never revert user changes unless explicitly asked.
- `upstream` is fetch-only. Never push, PR, merge, or publish to upstream.
- Publication to GitHub requires the local CI/git checklist in this file and
  any stricter task-specific docs.
- Any report about remotes, fetches, pushes, PRs, publication, or branch bases
  must name repositories explicitly. Do not write only `origin`, `upstream`,
  `main`, or a PR number. Include the full repo identity/URL and role, for
  example:
  - `origin`: `https://github.com/Apoze/drive.git` (fetch/push)
  - `upstream`: `https://github.com/suitenumerique/drive.git` (fetch-only,
    push disabled)
  - PR base: `Apoze/drive` `main`
  - PR head: `Apoze/drive` `<branch>`
  - PR URL: full `https://github.com/Apoze/drive/pull/<number>` URL

## Validation

Choose validation by touched area:

- Backend API/jobs/storage/WOPI: `make lint` and `make test-back`
- Frontend UI/components/hooks/viewers: `make frontend-lint` and
  `cd src/frontend/apps/drive && yarn test`
- Explorer, preview, routing, upload/download, mounts, or user flows:
  Playwright E2E per `docs/WorkDone/e2e/test-execution-contract.md`
- User-visible change: update `CHANGELOG.md` unless the PR is explicitly
  `noChangeLog`

Prefer targeted unit/integration tests during iteration. Reserve full
from-scratch E2E for pre-PR confidence or explicit end-to-end checks.
For catch-up batches, full three-browser L3 is a checkpoint, not a default
per-lot loop. If L3 fails outside the current batch, use focused reruns and let
the orchestrator schedule the next full checkpoint.

## Environment

Official modes are documented in `docs/env_freeze_report.md`:

- LAN dev: `ENV_OVERRIDE=local`
  - UI: `http://192.168.10.123:3000`
  - API: `http://192.168.10.123:8071`
  - Edge: `http://192.168.10.123:8083`
  - S3: `http://192.168.10.123:9000`
- CI-like local E2E: `ENV_OVERRIDE=e2e`
  - UI: `http://127.0.0.1:3000`
  - API: `http://127.0.0.1:8071`
  - Edge: `http://127.0.0.1:8083`
  - S3: `http://127.0.0.1:9000`

Local E2E requires `DRIVE_E2E_S2S_TOKEN`, preferably from the gitignored file
`env.d/development/e2e.tokens.local`. Never print that file's contents.

## Upstream Catch-Up

For catch-up-behind work, follow `PLANS_catchup_commits.md` and
`docs/catchup-behind-orchestration.md`.

Current dedicated threads:

- catch-up dev agent:
  `codex://threads/019f32a2-7ba5-7492-8446-abb1b058d929`
- catch-up orchestrator agent:
  `codex://threads/019f329f-a5db-7003-b9cf-0d4ccdfc1589`
- browser QA agent:
  `codex://threads/019f32af-aa7d-74e0-953c-0d980ae1e348`
- code-structure review agent:
  `codex://threads/019f40a2-5797-7f31-a875-1ce3331461ad`

Default catch-up mode is PREP ONLY: refresh remotes, audit current Git state,
regenerate missing lists/meta, propose lots, and stop. No cherry-pick, commit,
push, or PR until the user gives explicit `GO` for execution.

Manual/fork-aware ports do not reduce GitHub's ancestry-based `behind` count by
themselves. Catch-up completion requires ledger coverage and an audited
upstream target recorded as an ancestor; see `docs/catchup-behind-orchestration.md`.

Orchestrated catch-up uses one complete prompt at a time in `PROMPT.md`.
The orchestrator writes the prompt, the dev thread executes it, and the
orchestrator reviews the dev return before the next prompt.

Use the browser QA agent for deeper visual/browser checks with the Codex app
integrated browser, DevTools, and screenshots. QA availability is best effort:
if the Mac-local QA thread is unavailable, record the QA task as pending and
retry later; do not block orchestrator or dev progress on QA reachability.
Before LAN browser QA after E2E, run `make qa-lan-ready` and include the
sanitized LAN auth preflight in the QA request.
For authenticated LAN browser QA, run `make qa-lan-authenticated-ready` too;
include the fixed bootstrap URL and sanitized fixture URLs, never cookies or
tokens.

Agents should communicate directly through Codex threads using
`docs/agent-thread-coordination-protocol.md` until a real user decision is
needed. Escalate to the user only for explicit `GO`, publication, security or
product tradeoffs, destructive Git/history changes, or ambiguous decisions.
Do not ask the user to copy/paste prompts between agents. The orchestrator,
dev, QA, and code-structure review threads must contact each other directly
through Codex thread tools.

Delegation is a handoff point. After an agent sends a work request to another
agent thread, the sender must stop active polling and wait for either an
`AGENT_MSG` return, a new user instruction, or an explicitly documented retry
condition. Do not keep looping on another thread just because work is running.

Completion is also a routing point. Dev, QA, and code-structure review agents
must always send their final status to orchestrator before stopping; they must
not only document locally and stay idle. Dev reports go to orchestrator. QA
reports go to orchestrator, and to dev too when the failure is concrete and in
scope. Code-structure review reports go to orchestrator after every lot and
then wait for the next lot. Only orchestrator may stop without sending another
agent prompt, and only when a user decision is required or all approved work is
fully complete. Do not leave work only as a local/final answer in one thread if
orchestrator must decide the next step.

## CI / Publication Gates

Before any push, PR, ready-for-review, or merge:

- Fetch `origin` and determine the base branch; report the full repository URL
  and branch, not only the remote alias.
- Reject `fixup!` commits in the PR range.
- Reject tracked backend `print(`:
  `git grep -n "print(" -- src/backend`
- Ensure `CHANGELOG.md` policy is satisfied and lines are under 80 chars except
  link-only lines.
- Run gitlint locally on the PR range:
  `gitlint --commits origin/<base>..HEAD`
- If `gitlint` is missing, install it under `tmp/gitlint_venv/`; do not pollute
  the system Python.
- Before reporting success, restate the complete remote/PR identities:
  `origin` URL, `upstream` URL and fetch-only status, pushed repo/branch, PR
  base repo/branch, PR head repo/branch, and full PR URL.
- Stop on any failure. Do not push or create/update PRs.

## Skills

If the task names or clearly matches a Codex skill, open that skill's
`SKILL.md` and follow it before acting. Keep skill-specific context scoped to
the current task.
