# Agent Thread Coordination Protocol

This is the standard thread-to-thread communication protocol for Apoze Drive
catch-up, QA, and code-structure review work.

Goal: agents should coordinate directly until a real user decision is needed.
The user should only be interrupted for decisions that affect product behavior,
security, publication, scope, or risk acceptance.

## Threads

- Orchestrator:
  `codex://threads/019f329f-a5db-7003-b9cf-0d4ccdfc1589`
- Dev:
  `codex://threads/019f32a2-7ba5-7492-8446-abb1b058d929`
- QA:
  `codex://threads/019f32af-aa7d-74e0-953c-0d980ae1e348`
- Code-structure review:
  `codex://threads/019f40a2-5797-7f31-a875-1ce3331461ad`

## Roles

Orchestrator owns:

- planning and sequencing
- prompts in `PROMPT.md`
- user-facing decisions
- routing between dev and QA
- final status synthesis

Dev owns:

- repository inspection and implementation
- PREP artifacts
- batch execution after explicit user `GO`
- deterministic tests and reports
- asking for QA when a browser-human check is useful and already in scope

QA owns:

- browser-integrated checks on the local Mac
- DevTools console/network inspection
- screenshots and visual evidence
- reporting browser findings in the standard QA report format

Code-structure review owns:

- read-only architecture and service-boundary review
- use of `/root/.codex/skills/code-structure/SKILL.md`
- lot-by-lot findings with file and line references
- reporting to orchestrator after every review lot
- waiting for orchestrator before starting the next lot

## Core Rules

- Agents may contact each other directly when the next action is already within
  the approved scope.
- Agents must contact each other directly through Codex thread tools. Do not
  ask the user to copy/paste prompts between agents.
- Delegation is a handoff point: after an agent sends a work request to another
  agent thread, the sender must stop active polling and enter the matching
  waiting state (`WAITING_DEV`, `WAITING_QA`, or `WAITING_ORCHESTRATOR`).
  The sender resumes only when an agent sends an `AGENT_MSG` back, the user
  gives a new instruction, or a documented retry condition is reached.
- Do not run wait loops that repeatedly read another active thread after a
  delegation. A direct user status request is allowed, but routine orchestration
  should be event-driven by incoming thread messages.
- Agents must not ask the user unless a user decision is actually required.
- User decisions are required for:
  - Mode B execution `GO`
  - publication, push, PR, merge, or ready-for-review
  - product behavior tradeoffs
  - security or privacy risk acceptance
  - MountProvider parity deferral
  - destructive Git/history changes
  - ambiguous root cause where safe action is unclear
- QA unavailability is not blocking. Mark `PENDING_QA_RETRY` and continue safe
  orchestrator/dev work.
- No agent may leak secrets, cookies, tokens, auth headers, signed URLs, or
  local secret file contents.

## Message Envelope

Every direct agent-to-agent message should use this compact envelope.

```text
AGENT_MSG v1
from: orchestrator|dev|qa|review
to: orchestrator|dev|qa|review
context: catchup-behind|code-structure-review
type: <TYPE>
correlation_id: <YYYYMMDD-HHMM-short-slug>
blocking: yes|no
user_decision_needed: yes|no

summary:
<1-3 lines>

refs:
- branch: <branch-or-n/a>
- sha: <sha-or-n/a>
- prompt: <PROMPT.md-or-n/a>
- artifacts: <path-or-n/a>
- repositories: <full repo identities when remotes/PRs/publication are involved>

payload:
<structured details, concise and no secrets>

requested_next_action:
<exact next action requested from recipient>
```

Keep messages short enough to be readable in thread summaries. Put long
evidence in files/artifacts and link paths.

When a message mentions remotes, fetch, push, PRs, publication, bases, or
branch tracking, repository aliases alone are not enough. Include full
repository identities and roles:

- `origin`: full fetch URL and push URL
- `upstream`: full fetch URL and explicit push-disabled/fetch-only status
- pushed branch: full repository owner/name and branch
- PR base: full repository owner/name and branch
- PR head: full repository owner/name and branch
- PR URL: full `https://github.com/<owner>/<repo>/pull/<number>` URL

Catch-up reports that claim completion or local publication readiness must also
include ancestry state, not only product/test state:

- audited upstream target SHA
- whether that target is an ancestor of the reported head
- before/after `git rev-list --left-right --count` values
- ledger coverage for upstream commits through the target
- remaining right-side/behind count, if any, and whether it is deferred
- no-content proof when an ancestry-sync merge was created
- for ancestry-sync publication, required merge method
  (`Create a merge commit`) and the post-merge right-side-zero proof plan or
  result

Example:

```text
repositories:
- origin: https://github.com/Apoze/drive.git (fetch/push)
- upstream: https://github.com/suitenumerique/drive.git (fetch-only, push disabled)
- pushed: Apoze/drive codex/example
- PR base: Apoze/drive main
- PR head: Apoze/drive codex/example
- PR URL: https://github.com/Apoze/drive/pull/123
```

## Message Types

Use these `type` values:

- `ACK`: connectivity or receipt acknowledgement
- `DEV_PREP_REQUEST`: orchestrator asks dev to run PREP ONLY
- `DEV_EXECUTE_REQUEST`: orchestrator asks dev to run an approved batch
- `DEV_REPORT`: dev reports PREP/batch/fix outcome
- `QA_REQUEST`: orchestrator or dev asks QA for browser evidence
- `QA_REPORT`: QA returns browser evidence
- `REVIEW_REQUEST`: orchestrator asks review to inspect one code-structure lot
- `REVIEW_REPORT`: review returns one lot's findings
- `FIX_REQUEST`: orchestrator asks dev for a correction
- `BLOCKED`: an agent cannot proceed in scope
- `DECISION_REQUIRED`: user/orchestrator decision required
- `INFO`: non-blocking status update

## Status Values

Dev status values:

- `DONE_PREP`
- `DONE_BATCH`
- `DONE_FIX`
- `BLOCKED`
- `NEEDS_DECISION`

QA status values:

- `QA_PASS`
- `QA_FAIL`
- `QA_BLOCKED`
- `PENDING_QA_RETRY`

Review status values:

- `REVIEW_PASS`
- `REVIEW_FINDINGS`
- `REVIEW_BLOCKED`
- `REVIEW_NEEDS_DECISION`

Orchestrator status values:

- `PROMPT_READY`
- `WAITING_DEV`
- `WAITING_QA`
- `WAITING_ORCHESTRATOR`
- `WAITING_USER_DECISION`
- `DONE_STEP`

## Wait-After-Delegation Rule

When an agent sends `DEV_PREP_REQUEST`, `DEV_EXECUTE_REQUEST`, `QA_REQUEST`,
`FIX_REQUEST`, or any other work request to another thread, the sender's active
work on that chain is temporarily complete.

Required sender behavior:

- record the outgoing `AGENT_MSG` with a clear `correlation_id`
- stop polling the recipient thread
- do not send chained follow-up work until the recipient reports back
- resume only on an incoming `AGENT_MSG`, a new user instruction, or an
  explicit retry condition such as `PENDING_QA_RETRY`

This applies to all directions: orchestrator to dev, orchestrator to QA,
orchestrator to review, dev to QA, QA to dev, and dev/QA/review back to
orchestrator.

If the sender still has unrelated local work that does not depend on the
delegated thread, it may finish that work. It must not monitor the recipient in
a loop as a substitute for a return message.

## Completion Routing Rule

Before an agent stops after completing, blocking, or deferring work, it must
route its result to orchestrator. Dev, QA, and review do not decide to go idle
by merely documenting local state; orchestrator decides the next action.

Required completion checklist:

1. If dev completed, blocked, or hit a decision gate, send `DEV_REPORT`,
   `BLOCKED`, or `DECISION_REQUIRED` to orchestrator.
2. If QA completed, blocked, or has pending evidence, send `QA_REPORT` to
   orchestrator. Also send the same report to dev when the failure is concrete,
   reproducible, in scope, and does not need a user decision.
3. If code-structure review completed, blocked, or hit a decision gate, send
   `REVIEW_REPORT`, `REVIEW_BLOCKED`, or `REVIEW_NEEDS_DECISION` to
   orchestrator.
4. Dev, QA, and review may add `requested_next_action: wait for orchestrator`,
   but only after sending the report to orchestrator. They must not stop with
   only a local/final answer.
5. If orchestrator receives a non-decision report and another agent can continue
   safely, orchestrator sends the next `DEV_EXECUTE_REQUEST`, `FIX_REQUEST`, or
   `QA_REQUEST` directly. For code-structure review, orchestrator sends the
   next `REVIEW_REQUEST` when the next lot is safe to inspect.
6. Only orchestrator may intentionally stop without sending a new agent prompt,
   and only when a user decision is required or all approved work is fully
   complete. Orchestrator must state that waiting/completion reason explicitly.

Do not leave a report only as a local final answer when orchestrator needs it.
Use Codex thread tools when available. If thread tools are unavailable, leave a
complete `AGENT_MSG v1` in the current thread and state that the message was not
delivered directly.

## Routing Matrix

Orchestrator to dev:

- PREP prompt
- approved execution prompt
- fix request after dev/QA evidence
- request for impact analysis or decision report
- sent directly by the orchestrator through the dev Codex thread

Dev to orchestrator:

- all PREP and execution reports
- blockers and decision reports
- requests for user decision
- completion summaries
- sent directly by the dev Codex thread when tooling is available, otherwise
  reported in the dev thread for the orchestrator to read

Orchestrator to QA:

- planned browser QA lots
- focused visual/regression checks
- retest requests after dev fixes
- advisory checks when useful
- sent directly by the orchestrator through the QA Codex thread

QA to orchestrator:

- every `QA_REPORT`
- every `QA_BLOCKED` or `PENDING_QA_RETRY`
- evidence that may require dev action
- sent directly by the QA Codex thread when tooling is available, otherwise
  reported in the QA thread for the orchestrator to read

Orchestrator to code-structure review:

- one review lot at a time
- scoped architecture/service-boundary inspection prompts
- no implementation unless explicitly authorized by the user through
  orchestrator
- sent directly by the orchestrator through the code-structure review Codex
  thread

Code-structure review to orchestrator:

- every `REVIEW_REPORT`
- every `REVIEW_BLOCKED` or `REVIEW_NEEDS_DECISION`
- findings that may require dev or user action
- sent directly by the review Codex thread when tooling is available,
  otherwise reported in the review thread for the orchestrator to read

Dev to QA:

- allowed only for already-approved, in-scope browser evidence
- must copy or notify orchestrator with the same `correlation_id`
- use `QA_REQUEST`
- sent directly through the QA Codex thread, not via the user

QA to dev:

- allowed when QA finds a concrete, reproducible failure that clearly needs a
  dev fix and no user decision is required
- must copy or notify orchestrator with the same `correlation_id`
- use `QA_REPORT`, not free-form advice
- sent directly through the dev Codex thread, not via the user

Any agent to user:

- only when `user_decision_needed: yes`
- include concise options and the consequences of each option
- never include a prompt for the user to forward to another agent

## Dev Report Payload

For `DEV_REPORT`, use:

```text
status: DONE_PREP|DONE_BATCH|DONE_FIX|BLOCKED|NEEDS_DECISION
branch: <branch>
worktree_clean: yes|no
head: <sha>
repositories:
- origin: <full fetch/push URLs and role>
- upstream: <full fetch URL and push-disabled/fetch-only status>
pr_refs:
- base: <owner/repo> <branch or n/a>
- head: <owner/repo> <branch or n/a>
- url: <full PR URL or n/a>
origin_main: <sha>
upstream_main: <sha>
divergence: behind=<n> ahead=<n>
artifacts:
- <paths>
files_changed:
- <paths or n/a>
validations:
- <command>: PASS|FAIL|NOT_RUN (<reason>)
qa_needed: yes|no
decision_needed: yes|no
next_recommended_step: <short>
```

## QA Request Payload

For `QA_REQUEST`, use:

```text
scope: <feature/workflow>
target_url: <url>
environment: LAN|E2E|other
branch_or_sha: <branch/sha if relevant>
lan_auth_preflight: PASS|FAIL|NOT_APPLICABLE
lan_auth_location: <sanitized 302 Location or n/a>
preconditions:
- <known app state, credentials only if user explicitly provided them>
steps:
1. <step>
2. <step>
expected:
- <observable result>
evidence_requested:
- screenshot|console|network|video|notes
blocking: yes|no
```

## QA Report Payload

For `QA_REPORT`, use:

```text
status: QA_PASS|QA_FAIL|QA_BLOCKED|PENDING_QA_RETRY
scope: <feature/workflow>
environment: <LAN/E2E/etc>
url: <url>
browser_tool: <Codex integrated browser / DevTools / other>
steps_performed:
1. <step>
2. <step>
evidence:
- <screenshot/artifact paths or n/a>
console_network:
- <errors/warnings/failures, secrets masked, or none>
expected:
<expected behavior>
observed:
<observed behavior>
risk_impact:
<short impact>
recommended_next_action:
<dev fix | retest | user decision | no action>
```

## Blocked And Decision Rules

Use `BLOCKED` when the agent cannot proceed because of environment/tooling or
missing information, but no product decision is needed.

Use `DECISION_REQUIRED` when proceeding would choose product behavior, accept a
security/storage risk, defer MountProvider parity, publish, or rewrite history.

For QA unavailability:

```text
AGENT_MSG v1
from: orchestrator
to: orchestrator
context: catchup-behind
type: INFO
correlation_id: <id>
blocking: no
user_decision_needed: no

summary:
QA unavailable; task marked PENDING_QA_RETRY.

refs:
- artifacts: <where noted>

payload:
status: PENDING_QA_RETRY
retry_condition: QA thread reachable again

requested_next_action:
Continue dev/orchestrator work that is safe without QA.
```

## Evidence Rules

- Prefer artifact paths over large pasted logs.
- Screenshots should live under a run-specific folder when possible.
- Mask secrets in logs, URLs, headers, cookies, screenshots, and network data.
- Never claim a test passed if it was not executed.
- If a result is advisory, say so explicitly.
