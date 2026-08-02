# AGENTS.md - Apoze Drive

This repository is a brownfield Drive fork: Django/DRF backend, Next.js/TS
frontend, S3-compatible object storage for regular Drive items, and
MountProvider for filesystem-like mounts.

Keep this file short. Codex discovers `AGENTS.md` before work and the default
project instruction budget is 32 KiB; long contracts live in linked docs.

## Read First

Always start with this file. Do not read every linked document by default. Use
this routing table and open only the rows relevant to the task:

| Task area | Read next | Avoid unless relevant |
| --- | --- | --- |
| Broad repo/product orientation | `README.md`, `docs/architecture.md` | Long planning ledgers |
| Storage, mounts, streaming, WOPI, archive, upload/download, preview, search | `docs/agent-storage-contract.md` | Catch-up docs |
| Local env, CI-like E2E, Playwright execution | `docs/env_freeze_report.md`, `docs/WorkDone/e2e/test-execution-contract.md` | Historical E2E plans |
| Mount preview parity or viewer correction | `docs/mounts-preview-correction-plan.md`, storage contract | Catch-up ledgers |
| Upstream catch-up / behind-zero work | `PLANS_catchup_commits.md`, `docs/catchup-behind-orchestration.md`, `docs/catchup-behind-orchestrator-handoff.md`, `docs/agent-thread-coordination-protocol.md` | Review-cycle docs |
| Browser QA / human-vision testing | `docs/qa-browser-testing-contract.md`, thread protocol | E2E history plans |
| Code-structure architecture review | `docs/code-structure-review-lots.md`; consult `docs/code-structure-review-findings.md` only for ledger/status | Catch-up docs |
| Code-structure implementation/validation | `docs/code-structure-commit-plan.md`, relevant finding entry | Full findings ledger unless needed |
| Thread-to-thread coordination | `docs/agent-thread-coordination-protocol.md` | Manual copy/paste prompt templates |

If a referenced canonical doc is missing in a fresh workspace, report the missing
context instead of substituting memory.

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

Use `rg`/`rg --files` for search. Exclude noisy local artifacts unless the task
is specifically about them: `tmp/`, `tmp_old/`, `data/`, `.next*`,
`playwright-report*/`, and `test-results/`. Do not use destructive Git commands
unless the user explicitly asks for them.

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

For catch-up-behind work, follow `PLANS_catchup_commits.md`,
`docs/catchup-behind-orchestration.md`,
`docs/catchup-behind-orchestrator-handoff.md`, and
`docs/agent-thread-coordination-protocol.md`.

Dedicated threads:

- catch-up dev agent:
  `codex://threads/019fa701-91ca-7d41-a4c7-f8f8ae14e9e7`
- catch-up orchestrator agent:
  `codex://threads/019fa296-86ed-77c2-88ed-565a4a2efefa`
- browser QA agent:
  `codex://threads/019f32af-aa7d-74e0-953c-0d980ae1e348`
- code-structure review agent:
  `codex://threads/019f40a2-5797-7f31-a875-1ce3331461ad`

Project agents must be visible, top-level Codex conversations opened in this
project. Never use `spawn_agent`, a sub-agent, child agent, or internal
delegation as a substitute. If an authorized replacement conversation does not
exist, create it through the project App Server with the required model,
reasoning effort, and cwd, then persist its returned thread ID. If that creation
cannot be verified, stop with a routing failure; do not silently fall back.

Default catch-up mode is PREP ONLY: refresh remotes, audit current Git state,
regenerate missing lists/meta, propose lots, and stop. No cherry-pick, commit,
push, or PR until the user gives explicit `GO` for execution.

Completion is not only product parity. GitHub `behind` is ancestry-based:
ledger coverage plus an audited upstream target recorded as an ancestor are
required. An ancestry-sync PR must be merged with GitHub `Create a merge
commit`; squash/rebase drops the upstream second parent and can keep `behind`
nonzero.

Orchestrated catch-up uses one complete prompt at a time in `PROMPT.md`.
Treat `PROMPT.md` as local live state, not a durable project contract.

Use browser QA only for focused visual/browser evidence. Before LAN browser QA
after E2E, run `make qa-lan-ready`; for authenticated LAN QA also run
`make qa-lan-authenticated-ready`. Include sanitized URLs/preflight only, never
cookies, tokens, headers, or signed URLs.

Agents must communicate directly through Codex threads using
`docs/agent-thread-coordination-protocol.md` until a real user decision is
needed. Escalate to the user only for explicit `GO`, publication, security or
product tradeoffs, destructive Git/history changes, or ambiguous decisions.
Do not ask the user to copy/paste prompts between agents.
Project-agent creation, routing, observation, and completion delivery must use
the Codex App Server attached to this project. Use its thread and turn APIs and
streamed notifications. `codex exec`, `codex exec resume`, detached CLI
launchers, `--output-last-message` delivery, and direct rollout-file injection
are forbidden for inter-agent work. If the App Server route is unavailable,
stop with a routing failure; never fall back to a CLI process.
Before every handoff, resolve the active sender thread from runtime state and
put it in `reply_to_thread`; never reuse a historical orchestrator ID. A dev,
QA, or review task is not complete until its structured final report is sent as
a new prompt to that exact thread. A local final answer or report file alone is
not delivery.

Delegation and completion are routing points. After sending work to another
agent thread, stop active polling and wait for `AGENT_MSG`, a new user
instruction, or a documented retry condition. Dev, QA, and code-structure
review agents must route final status to orchestrator before stopping.
Automatic goal continuations and still-running terminal statuses are not return
messages: do not poll or emit repeated waiting replies. `WAITING_*` is a
logical routing state, never a running turn. The App Server client must observe
`turn/completed` and route the direct completion prompt to the orchestrator
thread. If `/goal`
nevertheless wakes the sender on the same external dependency for at least
three consecutive goal turns and no meaningful work is possible, follow the
strict blocked audit once to stop the scheduler. This is an external-state
impasse, not a user-decision request; the callback or `AGENT_MSG` resumes work.

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

## Agent skills

### Issue tracker

Les specs et tickets vivent dans GitHub Issues pour `Apoze/drive`. Les
changements ST Deploy Center restent locaux et doivent pouvoir être proposés
proprement au dépôt officiel. Voir `docs/agents/issue-tracker.md`.

### Triage labels

Utiliser les cinq labels Matt par défaut. Voir
`docs/agents/triage-labels.md`.

### Domain docs

Utiliser une documentation de domaine single-context. Voir
`docs/agents/domain.md`.

## Skills

If the task names or clearly matches a Codex skill, open that skill's
`SKILL.md` and follow it before acting. Keep skill-specific context scoped to
the current task.
