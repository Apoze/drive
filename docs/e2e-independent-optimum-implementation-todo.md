# E2E Independence Implementation Todo

## Closeout Outcome

Implementation result:

- phases `0` through `13` are complete
- the intended definition of done is satisfied
- Phase `14` stayed optional and was **not opened**
- final decision: `initiative closed without Phase 14`

Why this todo stopped here:

- the worker-safe one-stack harness is green in targeted benchmarking
- the legacy readiness control path is green
- the official deterministic from-scratch campaign is green
- the conservative CI policy is already in place and coherent with the final
  architecture

This document is the concrete implementation companion to:

- [docs/e2e-independent-optimum-plan.md](./e2e-independent-optimum-plan.md)

It is ordered by dependency chain, not by subsystem ownership.

Rule of execution:

- do not start worker scaling before the backend/bootstrap contract exists
- do not migrate complex specs before the common fixtures exist
- do not optimize CI before local single-stack parallelism is proven stable

## Current Repository Context Before Implementation

Read these files first before starting any code change:

- `AGENTS.md`
- `docs/e2e-independent-optimum-plan.md`
- `docs/e2e-independent-optimum-implementation-todo.md`
- `src/frontend/apps/e2e/playwright.config.ts`
- `src/frontend/apps/e2e/__tests__/app-drive/utils-common.ts`
- `src/backend/e2e/viewsets.py`
- `src/backend/e2e/utils.py`
- `src/backend/e2e/tests/test_api_e2e.py`
- `Makefile`
- `compose.yaml`
- `src/frontend/apps/e2e/scripts/loopback-proxies.js`

Current transitional work already present:

- isolated-stack support exists in `Makefile` / `compose.yaml`
- loopback proxies already support non-default E2E origins and ports
- E2E `user-auth` currently creates a fully initialized user profile to avoid
  first-boot CSRF/profile-update fragility

Operational commands to keep in mind:

- backend/bootstrap only:
  - `make bootstrap-e2e`
- existing E2E stack full campaign:
  - `bash run_env_e2e.sh --reuse`
- from scratch:
  - `bash run_env_e2e.sh --from-scratch`

Validation strategy during implementation:

- do not default to a full from-scratch run on every step
- prefer:
  - backend targeted tests
  - targeted Playwright specs on the existing E2E stack
- reserve full from-scratch E2E for checkpoints and pre-PR validation

Execution reporting location:

- `docs/e2e-independent-optimum-execution/index.md`
- `docs/e2e-independent-optimum-execution/current-status.md`
- `docs/e2e-independent-optimum-execution/checkpoints/phase-XX.md`

Checkpoint rule:

- when a mandatory checkpoint phase is reached, stop and request orchestrator
  confirmation before continuing
- do not continue by default past a checkpoint without updating the execution
  docs above

## Phase 0. Baseline, inventory, and guardrails

Goal:

- freeze the current baseline
- classify every spec by isolation difficulty
- create the migration map before touching runtime behavior

Files to update:

- [src/frontend/apps/e2e/playwright.config.ts](/root/Apoze/drive/src/frontend/apps/e2e/playwright.config.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/db.setup.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/db.setup.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/utils-common.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/utils-common.ts)
- [docs/e2e-independent-optimum-plan.md](/root/Apoze/drive/docs/e2e-independent-optimum-plan.md)
- [docs/e2e-independent-optimum-implementation-todo.md](/root/Apoze/drive/docs/e2e-independent-optimum-implementation-todo.md)

Actions:

- add a temporary classification table to the docs for every spec
- document which specs still require:
  - global DB reset
  - repeated login
  - multi-user actors
  - async search fixtures
  - mounts
  - WOPI/editors
- preserve current readiness smoke as a legacy control check

Phase 0 classification table:

| Spec | Current constraints | Migration category | Target fixture strategy |
| --- | --- | --- | --- |
| `breadcrumbs-from-page.spec.ts` | `clearDb`, repeated `login`, folder/star state | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` seeded with folders and favorites |
| `config-custom-assets.spec.ts` | repeated `login`, config-route stubbing | `worker-auth-only` | `primaryActor` worker fixture only |
| `context-menu.spec.ts` | `clearDb`, repeated `login`, folder CRUD | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` |
| `create-file-from-template.spec.ts` | `clearDb`, repeated `login`, template create flow | `isolated-workspace` | `primaryActor` + `isolatedWorkspace`, plus template-create scenario helpers |
| `create-folder.spec.ts` | `clearDb`, repeated `login` | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` |
| `delete-item.spec.ts` | `clearDb`, repeated `login`, nested folders | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` |
| `e2e-ready-smoke.spec.ts` | `clearDb`, repeated `login`, end-to-end control check | `legacy-control` | keep legacy `clearDb()` + `login()` until the new harness is proven |
| `heic-file-preview.spec.ts` | `clearDb`, repeated `login`, upload/preview fixture | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` + preview file seed/upload helper |
| `item/right-content-info.spec.ts` | `clearDb`, repeated `login` | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` |
| `language-sync.spec.ts` | `clearDb`, repeated `login`, direct API patching, null-vs-set language semantics | `auth-transition` | `primaryActor` bootstrap-session variants with explicit language/null language |
| `left-bar.spec.ts` | repeated `login` only | `worker-auth-only` | `primaryActor` worker fixture only |
| `login.spec.ts` | real Keycloak/OIDC login control | `legacy-control` | keep as dedicated interactive OIDC smoke |
| `mounts-basic.spec.ts` | `clearDb`, repeated `login`, mounts, preview/download/WOPI init | `mount-fixture` | `primaryActor` + `mountFixtureTree` |
| `mounts-preview-cycles.spec.ts` | `clearDb`, repeated `login`, mounts, reopen/edit cycles | `mount-fixture` | `primaryActor` + `mountFixtureTree` with deterministic subtree |
| `move-item.spec.ts` | `clearDb`, repeated `login`, nested tree mutations | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` |
| `pdf-preview-layout.spec.ts` | repeated `login`, upload/preview layout assertion | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` + preview PDF helper |
| `redirect-401.spec.ts` | `clearDb`, repeated `login`, real Keycloak relogin after session loss | `auth-transition` | `primaryActor` bootstrap for setup + explicit OIDC relogin control |
| `release-note.spec.ts` | repeated `login`, API stubbing | `worker-auth-only` | `primaryActor` worker fixture only |
| `search.spec.ts` | `clearDb`, repeated `login`, async fixture command | `search-dataset` | `primaryActor` + `searchDataset` scenario fixture |
| `share.spec.ts` | `clearDb`, repeated `login`, multi-context actors | `multi-actor-share` | `primaryActor` + `secondaryActor` + `sharedWorkspace` |
| `silent-login.spec.ts` | real Keycloak session reuse, localStorage behavior | `auth-transition` | keep real OIDC flow, independent from synthetic bootstrap auth |
| `starred.spec.ts` | `clearDb`, repeated `login`, favorites state | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` |
| `upload.spec.ts` | `clearDb`, repeated `login`, upload limit stubbing | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` |
| `url-file-preview.spec.ts` | `clearDb`, repeated `login`, share-link preview | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` + preview/share-link helper |
| `viewer-routing.spec.ts` | `clearDb`, repeated `login`, synthetic file imports | `isolated-workspace` | `primaryActor` + `isolatedWorkspace` + preview fixture helper |
| `wopi-onlyoffice-editnew.spec.ts` | `clearDb`, repeated `login`, ONLYOFFICE create/editnew | `wopi-editor` | `primaryActor` + isolated workspace + editor fixture helper |
| `wopi.spec.ts` | `clearDb`, repeated `login`, editor load/retry behavior | `wopi-editor` | `primaryActor` + isolated workspace + editor fixture helper |

Acceptance:

- every spec has one migration category
- every spec has a target fixture strategy
- no product code changes yet

## Phase 1. Backend bootstrap contract

Goal:

- replace "truncate DB + ad hoc login" with explicit E2E bootstrap primitives

Existing files to update:

- [src/backend/e2e/serializers.py](/root/Apoze/drive/src/backend/e2e/serializers.py)
- [src/backend/e2e/urls.py](/root/Apoze/drive/src/backend/e2e/urls.py)
- [src/backend/e2e/utils.py](/root/Apoze/drive/src/backend/e2e/utils.py)
- [src/backend/e2e/viewsets.py](/root/Apoze/drive/src/backend/e2e/viewsets.py)
- [src/backend/e2e/tests/test_api_e2e.py](/root/Apoze/drive/src/backend/e2e/tests/test_api_e2e.py)

New files to add:

- [src/backend/e2e/services/bootstrap.py](/root/Apoze/drive/src/backend/e2e/services/bootstrap.py)
- [src/backend/e2e/services/namespaces.py](/root/Apoze/drive/src/backend/e2e/services/namespaces.py)
- [src/backend/e2e/tests/test_api_e2e_bootstrap.py](/root/Apoze/drive/src/backend/e2e/tests/test_api_e2e_bootstrap.py)

Contract to implement:

- `POST /api/v1.0/e2e/bootstrap-session/`
- `POST /api/v1.0/e2e/bootstrap-scenario/`
- optional `POST /api/v1.0/e2e/cleanup-scope/`

Bootstrap session responsibilities:

- create or reuse a deterministic actor
- initialize actor profile fully
- create or reuse the actor main workspace
- authenticate the browser session
- ensure CSRF cookie is present
- return stable identifiers for the harness

Bootstrap scenario responsibilities:

- create namespaced test data under one worker/scenario scope
- support at least:
  - clean isolated workspace root
  - paired-share scenario
  - search dataset
  - preview fixture set
  - mount subtree

Rules:

- idempotent
- no global truncate
- safe to retry
- no provider-specific mount branching in the public contract

Acceptance:

- a fresh actor can be created without `clear-db`
- the same bootstrap request can be replayed safely
- scenario data is namespaced and does not collide
- mandatory orchestrator checkpoint after this phase

## Phase 2. Backend cleanup and observability

Goal:

- make non-global cleanup practical
- give tests deterministic lifecycle hooks

Existing files to update:

- [src/backend/e2e/utils.py](/root/Apoze/drive/src/backend/e2e/utils.py)
- [src/backend/e2e/viewsets.py](/root/Apoze/drive/src/backend/e2e/viewsets.py)
- [src/backend/e2e/tests/test_api_e2e.py](/root/Apoze/drive/src/backend/e2e/tests/test_api_e2e.py)

New files to add:

- [src/backend/e2e/tests/test_api_e2e_cleanup_scope.py](/root/Apoze/drive/src/backend/e2e/tests/test_api_e2e_cleanup_scope.py)

Actions:

- implement scoped cleanup by run/worker/scenario
- add deterministic naming helpers used by every bootstrap path
- expose enough metadata for frontend fixtures to avoid guessing names

Quality improvement tasks:

- keep `clear-db` only as a readiness/legacy endpoint
- disable or bypass test-only debug overhead when it causes false failures

Acceptance:

- cleanup can remove one worker namespace without touching others
- the full suite no longer depends on DB-global cleanup as a correctness rule

## Phase 3. Playwright harness foundation

Goal:

- add worker-scoped and scenario-scoped fixtures before migrating specs

Existing files to update:

- [src/frontend/apps/e2e/playwright.config.ts](/root/Apoze/drive/src/frontend/apps/e2e/playwright.config.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/db.setup.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/db.setup.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/utils-common.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/utils-common.ts)

New files to add:

- [src/frontend/apps/e2e/__tests__/app-drive/fixtures/actors.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/fixtures/actors.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/fixtures/scenarios.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/fixtures/scenarios.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/fixtures/namespaces.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/fixtures/namespaces.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/fixtures/types.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/fixtures/types.ts)

Fixture model to introduce:

- `primaryActor` worker fixture
- `secondaryActor` worker fixture
- `isolatedWorkspace` test fixture
- `sharedWorkspace` test fixture
- `searchDataset` test fixture
- `mountFixtureTree` test fixture

Rules:

- auth state is created once per worker, not once per test
- actor accounts are namespaced per worker
- scenario data is namespaced per test
- normal tests do not call `clearDb()`
- normal tests do not call raw `login()`

Acceptance:

- a simple CRUD spec can run with zero direct calls to `clearDb()` and `login()`
- actor fixture reuses session state safely across tests in one worker
- mandatory orchestrator checkpoint after this phase

## Phase 4. Low-risk spec migration wave

Goal:

- migrate the easiest specs first to validate the fixture model

Files to migrate first:

- [src/frontend/apps/e2e/__tests__/app-drive/config-custom-assets.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/config-custom-assets.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/left-bar.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/left-bar.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/release-note.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/release-note.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/pdf-preview-layout.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/pdf-preview-layout.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/heic-file-preview.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/heic-file-preview.spec.ts)

Why these first:

- mostly single-user
- low data complexity
- good signal for fixture quality

Acceptance:

- these specs pass with worker fixtures
- no global cleanup
- no repeated UI or API login per test

## Phase 5. Single-user CRUD migration wave

Goal:

- move the bulk of the suite to namespaced, worker-safe execution

Files to migrate:

- [src/frontend/apps/e2e/__tests__/app-drive/create-folder.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/create-folder.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/delete-item.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/delete-item.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/move-item.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/move-item.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/upload.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/upload.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/starred.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/starred.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/context-menu.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/context-menu.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/item/right-content-info.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/item/right-content-info.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/url-file-preview.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/url-file-preview.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/viewer-routing.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/viewer-routing.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/breadcrumbs-from-page.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/breadcrumbs-from-page.spec.ts)

Common refactors:

- replace direct global setup with `isolatedWorkspace`
- convert fixed names to namespaced names
- remove hidden assumptions on root workspace contents

Acceptance:

- these specs run concurrently on one stack with no collisions
- failures, if any, are product failures, not harness-global-state failures
- mandatory orchestrator checkpoint after this phase

## Phase 6. Auth and shell behavior wave

Goal:

- isolate tests that still care about auth/session behavior explicitly

Files to migrate:

- [src/frontend/apps/e2e/__tests__/app-drive/login.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/login.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/silent-login.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/silent-login.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/redirect-401.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/redirect-401.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/language-sync.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/language-sync.spec.ts)

Rules:

- auth-product tests are allowed to exercise explicit login paths
- they must still avoid DB-global resets when not strictly necessary
- language/profile tests should use deliberately bootstrapped actor states

Quality improvements to consider here:

- make first-render profile sync explicit instead of implicit
- reduce hidden page-boot writes

Acceptance:

- auth flows are isolated without forcing unrelated specs into the same model

## Phase 7. Multi-user/share wave

Goal:

- migrate the specs that genuinely need multiple actors

Files to migrate:

- [src/frontend/apps/e2e/__tests__/app-drive/share.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/share.spec.ts)

Supporting files to update:

- [src/frontend/apps/e2e/__tests__/app-drive/utils/share-utils.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/utils/share-utils.ts)

Requirements:

- one paired actor fixture per worker
- one namespaced shared resource per scenario
- no globally named users
- no DB truncation

Acceptance:

- share specs run concurrently with each other and with single-user specs

## Phase 8. Search and async-data wave

Goal:

- remove the last known global fixture dependency

Files to migrate:

- [src/frontend/apps/e2e/__tests__/app-drive/search.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/search.spec.ts)

Existing backend files to extend:

- [src/backend/e2e/management/commands/e2e_fixture_search.py](/root/Apoze/drive/src/backend/e2e/management/commands/e2e_fixture_search.py)
- [src/backend/e2e/viewsets.py](/root/Apoze/drive/src/backend/e2e/viewsets.py)

Requirements:

- make search fixture creation namespaced
- wait for indexing deterministically
- avoid global fixture pollution

Acceptance:

- search can run in parallel with CRUD/share specs
- mandatory orchestrator checkpoint after this phase

## Phase 9. WOPI and editor wave

Goal:

- migrate the most integration-heavy editor flows after the harness is stable

Files to migrate:

- [src/frontend/apps/e2e/__tests__/app-drive/wopi.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/wopi.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/wopi-onlyoffice-editnew.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/wopi-onlyoffice-editnew.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/create-file-from-template.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/create-file-from-template.spec.ts)

Requirements:

- worker-safe editor fixture files
- explicit actor profile/language bootstrap
- no reliance on global newly-created-user state

Acceptance:

- editor specs no longer require DB-global setup to remain deterministic

## Phase 10. Mount and storage wave

Goal:

- migrate mount specs to per-worker storage namespaces

Files to migrate:

- [src/frontend/apps/e2e/__tests__/app-drive/mounts-basic.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/mounts-basic.spec.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/mounts-preview-cycles.spec.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/mounts-preview-cycles.spec.ts)

Existing backend files to extend:

- [src/backend/e2e/fixtures/mounts_registry.e2e.json](/root/Apoze/drive/src/backend/e2e/fixtures/mounts_registry.e2e.json)
- [src/backend/e2e/viewsets.py](/root/Apoze/drive/src/backend/e2e/viewsets.py)

Requirements:

- one mount subtree per run/worker/scenario
- deterministic cleanup of that subtree
- no shared filenames in mount roots

Acceptance:

- mount specs can run concurrently without stepping on each other
- mandatory orchestrator checkpoint after this phase

## Phase 11. Legacy cleanup removal

Goal:

- make the new fixture model the default and retire old helpers from normal
  usage

Files to update:

- [src/frontend/apps/e2e/__tests__/app-drive/utils-common.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/utils-common.ts)
- [src/frontend/apps/e2e/__tests__/app-drive/db.setup.ts](/root/Apoze/drive/src/frontend/apps/e2e/__tests__/app-drive/db.setup.ts)
- [src/backend/e2e/viewsets.py](/root/Apoze/drive/src/backend/e2e/viewsets.py)
- [src/backend/e2e/urls.py](/root/Apoze/drive/src/backend/e2e/urls.py)

Actions:

- keep `clear-db` only for readiness and transitional legacy coverage
- deprecate direct `login()` in normal specs
- mark raw global helpers as legacy-only

Acceptance:

- no normal product spec depends on `clearDb()` or ad hoc `login()`

## Phase 12. Worker scaling on one stack

Goal:

- prove the suite scales on one stack before adding shards

Files to update:

- [src/frontend/apps/e2e/playwright.config.ts](/root/Apoze/drive/src/frontend/apps/e2e/playwright.config.ts)
- [Makefile](/root/Apoze/drive/Makefile)
- [run_env_e2e.sh](/root/Apoze/drive/run_env_e2e.sh)

Execution order:

1. benchmark `workers: 4`
2. benchmark `workers: 6`
3. benchmark `workers: 8`

Mandatory orchestrator checkpoints:

- before starting Phase 12
- after Phase 12 benchmarking and default selection

Measurements required:

- wall time
- flake rate
- CPU saturation
- RAM pressure
- browser crash rate

Acceptance:

- choose one stable local default
- document one heavier validation mode if needed

## Phase 13. CI policy update

Goal:

- align CI with the new independent-suite model

Files to update:

- [.github/workflows/drive-frontend.yml](/root/Apoze/drive/.github/workflows/drive-frontend.yml)
- [Makefile](/root/Apoze/drive/Makefile)
- [run_env_e2e.sh](/root/Apoze/drive/run_env_e2e.sh)
- [AGENTS.md](/root/Apoze/drive/AGENTS.md) if the repo policy wants the new
  commands documented in tracked docs later

Recommended target modes:

- PR:
  - one stack per job
  - Chromium full suite with multiple workers
  - WebKit/Firefox targeted compatibility coverage if policy allows
- `main` / nightly:
  - broader browser coverage
  - optional shards only after worker-based scaling is exhausted

Acceptance:

- PR feedback loop gets shorter than the current serial model
- full compatibility coverage remains available on a broader cadence

## Phase 14. Optional second-stage sharding

Goal:

- keep sharding available only if worker scaling is no longer enough

Files to update only if needed:

- [Makefile](/root/Apoze/drive/Makefile)
- [run_env_e2e.sh](/root/Apoze/drive/run_env_e2e.sh)
- [.github/workflows/drive-frontend.yml](/root/Apoze/drive/.github/workflows/drive-frontend.yml)

Rule:

- do not start this phase before Phase 12 and Phase 13 are complete

Acceptance:

- sharding is an optional accelerator, not a requirement for correctness

Current status:

- not started
- not required at closeout

## Final implementation order summary

1. backend bootstrap contract
2. backend scoped cleanup
3. frontend worker/scenario fixtures
4. easy single-user specs
5. bulk single-user CRUD specs
6. auth-shell specs
7. multi-user share specs
8. search specs
9. WOPI/editor specs
10. mount specs
11. legacy helper cleanup
12. worker scaling on one stack
13. CI policy update
14. optional sharding

Final outcome:

- steps `1` through `13` completed
- step `14` intentionally not opened

## Definition of done

The initiative is complete when all of the following are true:

- normal specs no longer rely on global DB truncation
- normal specs no longer rely on repeated raw login
- one-stack multi-worker local runs are stable
- CI PR policy is faster than the current serial baseline
- browser compatibility remains covered by an explicit documented policy
- stack multiplication is no longer the main scaling mechanism

Current outcome:

- satisfied
