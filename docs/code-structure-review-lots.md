# Code Structure Review Lots

This document defines the dedicated architecture/code-structure review cycle.
It is separate from catch-up execution and publication stabilization.

Primary skill:

- `/root/.codex/skills/code-structure/SKILL.md`
- The review agent must read this skill before each lot and apply its
  orchestration-vs-service boundary model.

## Threads

- Orchestrator:
  `codex://threads/019f329f-a5db-7003-b9cf-0d4ccdfc1589`
- Code-structure review:
  `codex://threads/019f40a2-5797-7f31-a875-1ce3331461ad`
- Dev:
  `codex://threads/019f32a2-7ba5-7492-8446-abb1b058d929`
- QA:
  `codex://threads/019f32af-aa7d-74e0-953c-0d980ae1e348`

The review thread reports to orchestrator after every lot and then waits.
It does not self-advance to the next lot. Orchestrator sequences the next lot
when no user decision is required.

The orchestrator records every returned finding in
`docs/code-structure-review-findings.md`. That ledger is the source of truth
for open review findings, triage state, and final synthesis inputs.

## Review Mode

The code-structure review agent is review-only by default.

Allowed:

- inspect code and docs;
- run read-only searches and lightweight static commands;
- produce findings with file and line references;
- suggest minimal refactor plans.

Not allowed unless orchestrator explicitly requests it:

- product-code edits;
- commits;
- pushes, PRs, publication, merge, rebase, or branch rewrites;
- broad test campaigns;
- feature implementation.

The review agent should use a code-review stance: findings first, ordered by
severity, with summaries secondary. If no issue is found, say so clearly and
name residual risks or unreviewed surfaces.

## Finding Criteria

Use `$code-structure` to identify whether operational mechanics are duplicated
or hidden in orchestration code.

Good findings usually show at least one of:

- duplicated operational mechanics across two or more callers;
- orchestration code doing reusable provider/SDK/request/cache mechanics;
- a service mutating domain state through hidden side effects;
- inconsistent structured return/error handling for the same operation;
- a bug-fix risk where one flow can be fixed while another remains broken;
- an over-broad service that hides product policy and control flow.

Avoid findings for:

- one-off domain-specific logic used by a single caller;
- style preferences without behavioral or maintenance risk;
- large refactors whose benefit is speculative.

## Report Format

Each lot report should use `AGENT_MSG v1` and `context:
code-structure-review`.

```text
AGENT_MSG v1
from: review
to: orchestrator
context: code-structure-review
type: REVIEW_REPORT
correlation_id: <id>
blocking: yes|no
user_decision_needed: yes|no

summary:
<1-3 lines>

refs:
- branch: <branch>
- sha: <sha>
- lot: <R1/R2/...>
- artifacts: <path-or-n/a>

payload:
- files inspected:
- findings:
  - [P1] <title> — <file:line>
    impact:
    evidence:
    recommendation:
- open questions:
- suggested next lot:

requested_next_action:
wait for orchestrator
```

Severity:

- `P0`: likely data loss, security break, or unavailable core workflow.
- `P1`: plausible production bug, serious maintenance hazard, or inconsistent
  behavior across flows.
- `P2`: medium maintainability risk or duplication likely to cause drift.
- `P3`: minor cleanup, naming, or future refactor note.

## Lots

### R1 Backend API, Jobs, And Commands

Goal: review backend orchestration boundaries.

Primary surfaces:

- `src/backend/core/api/viewsets.py`
- `src/backend/core/api/serializers.py`
- `src/backend/core/api/filters.py`
- `src/backend/core/tasks/`
- `src/backend/core/management/commands/`
- `src/backend/core/services/`
- `src/backend/core/entitlements/`
- `src/backend/core/tests/` only as evidence for duplicated behavior.

Questions:

- Are viewsets/commands/tasks owning product policy while reusable mechanics
  live in services?
- Are repeated operations such as permission filtering, metrics, email,
  import/export, purge/delete, or CSV processing extracted coherently?
- Do services use explicit inputs and structured outputs?
- Are errors classified at the right layer?

### R2 Storage, Upload, Export, WOPI, And Conversion

Goal: review service boundaries around file operations and external providers.

Read before this lot:

- `docs/agent-storage-contract.md`

Primary surfaces:

- `src/backend/core/storage/`
- `src/backend/core/services/item_exports.py`
- `src/backend/core/api/viewsets.py` file endpoints
- `src/backend/core/tasks/`
- `src/backend/wopi/`
- upload/download/export/conversion tests.

Questions:

- Are regular Drive Storage mechanics separated from MountProvider mechanics?
- Are streaming/bounded operations centralized rather than duplicated?
- Are WOPI/conversion/export mechanics reusable without hiding domain policy?
- Are storage keys, signed URLs, and file contents kept out of logs?

### R3 Frontend Explorer Orchestration

Goal: review frontend orchestration boundaries in the main explorer.

Primary surfaces:

- `src/frontend/apps/drive/src/features/explorer/components/app-view/`
- `src/frontend/apps/drive/src/features/explorer/hooks/`
- `src/frontend/apps/drive/src/features/explorer/components/modals/`
- `src/frontend/apps/drive/src/features/drivers/`
- `src/frontend/apps/drive/src/features/ui/preview/`

Questions:

- Does the canonical explorer shell stay thin?
- Are drivers/adapters responsible for backend mechanics instead of UI shells?
- Are action menus, selection, upload, delete, preview, and conversion flows
  sharing mechanics without burying product policy?
- Are cache invalidation and transient-row mechanics centralized enough to
  avoid drift?

### R4 MountProvider Boundaries

Goal: review mount-specific boundaries and parity deferrals.

Read before this lot:

- `docs/agent-storage-contract.md`
- `docs/mounts-preview-correction-plan.md`

Primary surfaces:

- `src/backend/core/mounts/`
- mount viewsets and provider contracts
- `src/frontend/apps/drive/src/features/mounts/`
- mount preview/action/upload/download tests.

Questions:

- Does MountProvider stay capability-driven instead of provider-brand-driven?
- Are regular item APIs and mount APIs kept separate where required?
- Are deferred parity decisions explicit instead of accidental gaps?
- Are mount preview/WOPI/archive/upload actions using shared mechanics safely?

### R5 E2E And Test Helper Architecture

Goal: review test-helper service boundaries after catch-up stabilization.

Primary surfaces:

- `src/frontend/apps/e2e/__tests__/app-drive/fixtures/`
- `src/frontend/apps/e2e/__tests__/app-drive/utils*.ts`
- `src/frontend/apps/e2e/__tests__/app-drive/utils/`
- `src/backend/e2e/`
- `docs/WorkDone/e2e/test-execution-contract.md`

Questions:

- Are repeated browser operations factored into reliable helpers?
- Do helpers preserve product assertions instead of hiding failures?
- Are bootstrap/session/fixture mechanics explicit and deterministic?
- Are full-suite convergence helpers becoming too broad or leaky?

### R6 Cross-Cutting Mechanics

Goal: synthesize repeated mechanics found across backend, frontend, and tests.

Primary themes:

- permissions/capabilities;
- cache invalidation and polling;
- transient rows and long-running operations;
- toast/error surfaces;
- public config and auth bootstrap;
- preview/source resolution;
- share links and public routes.

Questions:

- Which mechanics are repeated across backend/frontend/test layers?
- Which should become explicit service/helper contracts?
- Which are intentionally duplicated because domain policy differs?

### R7 Final Synthesis

Goal: produce a prioritized plan from R1-R6.

Output:

- top findings grouped by risk and expected effort;
- refactor sequence with small safe steps;
- tests or regression checks needed for each proposed refactor;
- items that require user/product/security decisions;
- items explicitly not worth changing.

Do not implement the plan unless orchestrator sends a separate implementation
request.

## Orchestration Rules

1. Orchestrator sends one lot at a time.
2. Review thread reports to orchestrator and waits.
3. Orchestrator may send the next lot automatically when:
   - no user decision is needed;
   - the prior report is understandable;
   - no urgent dev fix must be routed first.
4. User decision is required for:
   - accepting a risky architectural tradeoff;
   - approving implementation of suggested refactors;
   - changing product behavior;
   - publication/PR work;
   - destructive Git/history changes.
5. Review findings do not automatically authorize code edits.
