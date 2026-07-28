# QA Browser Testing Contract

This document defines the QA agent role for Apoze Drive catch-up and browser
validation work.

Use `docs/agent-thread-coordination-protocol.md` for the canonical
thread-to-thread message envelope and report formats.

## Dedicated QA Thread

QA agent:

- thread: `codex://threads/019f32af-aa7d-74e0-953c-0d980ae1e348`
- host: local macOS Codex app
- observed cwd: `/Users/maz/Documents/drive_localmacos`

Related threads:

- orchestrator:
  `codex://threads/019fa296-86ed-77c2-88ed-565a4a2efefa`
- catch-up dev:
  `codex://threads/019fa701-91ca-7d41-a4c7-f8f8ae14e9e7`

## Purpose

The QA agent handles browser checks that need Codex app local capabilities and
a more human-like visual review.

Use QA for:

- integrated browser testing
- DevTools console and network inspection
- screenshots and visual evidence
- explorer/preview/viewer UX checks
- responsive and layout checks
- manual reproduction of user-facing regressions
- focused verification after dev fixes

Do not use QA as the primary Git implementation agent. Product code changes and
catch-up apply work remain with the dev agent unless the orchestrator explicitly
changes the assignment.

## Availability Rule

The QA thread runs on the user's local Mac and may be unavailable when that
environment is offline, asleep, disconnected, or the Codex app is not ready.

If QA is not reachable:

- record the QA task as `PENDING_QA_RETRY`
- include the intended QA scope and reason it is pending
- continue orchestrator/dev work when safe
- retry later when the QA thread is available

QA unavailability must not block catch-up PREP or normal dev execution.

## Expected QA Local Setup

The QA agent should maintain a local instruction set under its Mac workspace.
Recommended files:

- `/Users/maz/Documents/drive_localmacos/AGENTS.md`
- `/Users/maz/Documents/drive_localmacos/docs/qa-drive-context.md`
- `/Users/maz/Documents/drive_localmacos/docs/qa-browser-checks.md`
- `/Users/maz/Documents/drive_localmacos/docs/qa-report-template.md`
- `/Users/maz/Documents/drive_localmacos/tmp/qa-runs/`

Keep the Mac-local `AGENTS.md` concise. Put long checklists and templates in
the `docs/` files above.

## QA Inputs

A QA prompt should specify:

- goal and risk area
- target URL/environment
- branch/SHA or app state if known
- exact workflow to inspect
- expected behavior
- artifacts requested
- whether the result is blocking or advisory

Do not paste secrets, tokens, cookies, auth headers, or signed URLs into QA
prompts. Use public LAN/dev URLs and normal login flows.

## QA Output

QA reports must use the `QA_REPORT` format from
`docs/agent-thread-coordination-protocol.md` and include:

- status: `QA_PASS`, `QA_FAIL`, `QA_BLOCKED`, or `PENDING_QA_RETRY`
- environment and URL tested
- browser/tool used
- concise steps performed
- screenshots or artifact paths when useful
- console errors and network failures, with secrets masked
- observed vs expected behavior
- likely root cause only if evidence supports it
- recommended next step

QA may send a `QA_REPORT` directly to dev only when the failure is concrete,
reproducible, in the approved scope, and does not need a user decision. QA must
also notify the orchestrator with the same `correlation_id`.

QA must not ask the user to forward prompts or reports between agents. Use
Codex thread tools for QA-to-orchestrator, QA-to-dev, and ACK messages whenever
available; otherwise leave the structured report in the QA thread for the
orchestrator to read.

When QA sends a `QA_REPORT`, `ACK`, or direct request to another agent thread,
that send is a handoff point. QA must stop active polling of the recipient and
wait for an incoming `AGENT_MSG`, a new user instruction, or a documented retry
condition. Do not loop on dev/orchestrator thread reads after delegation.

## Standard Drive URLs

LAN/local dev stack:

- UI: `http://192.168.10.123:3000`
- API: `http://192.168.10.123:8071`
- Edge: `http://192.168.10.123:8083`
- S3: `http://192.168.10.123:9000`

CI-like E2E loopback URLs are for the remote/dev E2E contract and are not the
default QA browser target unless the prompt says so.

## LAN Auth Preflight

Before sending a Mac-local browser `QA_REQUEST` against the LAN stack, the
requesting agent must run:

```bash
make qa-lan-ready
```

This target:

- runs local migrations and WOPI configuration without resetting local data
- force-recreates `app-dev`, `nginx`, `celery-dev`, `celery-beat-dev`, and
  `frontend-dev` with `ENV_OVERRIDE=local`
- validates `/api/v1.0/authenticate/` returns a browser-facing `302 Location`
  on `http://192.168.10.123:8083`
- masks redirect query values in command output

The expected sanitized proof looks like:

```text
[qa-lan-auth] status: 302
[qa-lan-auth] location: http://192.168.10.123:8083/...?...
[qa-lan-auth] PASS: redirect origin is http://192.168.10.123:8083
```

If this preflight fails, do not send QA into the known-bad auth flow. Report
the QA item as pending on the failed LAN auth preflight and include the
sanitized failure, not cookies, tokens, auth headers, or full redirect query
values.

## Authenticated LAN QA Bootstrap

For authenticated browser QA, run:

```bash
make qa-lan-authenticated-ready
```

This runs `make qa-lan-ready`, then validates the dev-only browser bootstrap
endpoint:

```text
http://192.168.10.123:8071/api/v1.0/e2e/qa-browser-bootstrap/
```

The endpoint is available only in the E2E URL tree used by local/dev and E2E
settings. It creates deterministic E2E dummy data, logs the browser into an
`e2e+...@example.com` dummy user with an unusable password, sets normal session
cookies, and redirects to a regular Drive folder fixture. It does not expose
server-to-server tokens, cookies, passwords, auth headers, signed URLs, or real
credentials.

The authenticated preflight output may include:

- the fixed QA browser start URL above
- the regular Drive fixture URL
- a mount fixture URL when a mount is configured
- `set-cookie: present`

It must not print cookie values or local token values.

An authenticated `QA_REQUEST` should include:

- the sanitized `make qa-lan-ready` auth redirect PASS
- the sanitized `make qa-lan-authenticated-ready` bootstrap PASS
- the QA browser start URL
- the regular fixture URL
- the mount fixture URL, or `mount fixture: unavailable`

QA should first open the QA browser start URL in the integrated browser. After
the redirect, the browser should be authenticated on the LAN UI and ready for
the requested visual workflow.

## Operator-Enabled Conversion QA Bootstrap

For browser QA that must exercise the B0074 legacy Office conversion action,
run:

```bash
make qa-lan-conversion-ready
```

This target first restores the regular LAN QA stack, then force-recreates
`onlyoffice`, `app-dev`, `celery-dev`, `celery-beat-dev`, `nginx`, and
`frontend-dev` with a dev-only compose override for conversion. The override:

- keeps conversion disabled for normal `make qa-lan-ready`
- sets `WOPI_ONLYOFFICE_OPTIONS` only for the QA conversion run
- generates one local ephemeral JWT secret and passes it to Drive and
  OnlyOffice without printing it
- keeps MountProvider conversion absent/hidden

The preflight uses:

```text
http://192.168.10.123:8071/api/v1.0/e2e/qa-browser-bootstrap/?include_conversion=1
```

It verifies the authenticated dummy browser session, creates a deterministic
regular `.doc` fixture, checks the item API exposes `abilities.convert: true`,
and prints only safe data: LAN fixture URLs, fixture title, status, and boolean
ability proof. It must not print cookies, JWT secrets, auth headers, signed
URLs, storage keys, or file contents.

An operator-enabled conversion `QA_REQUEST` should include:

- the sanitized `make qa-lan-conversion-ready` PASS
- the QA browser start URL from the conversion preflight
- the conversion fixture URL and title
- the mount fixture URL, or `mount fixture: unavailable`

QA should open the conversion QA browser start URL first. After redirect, the
browser is authenticated and the regular legacy `.doc` fixture should show the
conversion action. Running `make qa-lan-ready` again restores the normal LAN QA
stack without conversion enabled.

## QA Guardrails

- Do not modify product code unless explicitly asked.
- Do not commit, push, PR, merge, or rebase unless explicitly asked.
- Never leak secrets or local token file contents.
- Prefer screenshots and concise evidence over long raw logs.
- Mask cookies, auth headers, signed URLs, tokens, and user-sensitive file
  contents.
- Do not declare a regression fixed unless the tested behavior matches the
  expected user-visible result.
