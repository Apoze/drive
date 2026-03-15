# E2E Independence And True-Optimum Plan

## Closeout Status

Final status:

- phases `0` through `13` are implemented and validated
- Phase `14` stayed optional and was **not opened**
- final decision: `initiative closed without Phase 14`

Why this was enough:

- the independent one-stack harness is validated
- the representative local `PLAYWRIGHT_WORKERS=4` benchmark is green
- the legacy readiness smoke is green
- the official `bash run_env_e2e.sh --from-scratch` campaign is green
- the conservative CI policy from Phase `13` is already in place

What remains true after closeout:

- the default local mode intentionally remains `PLAYWRIGHT_WORKERS=1`
- Phase `13` CI remains conservative by design
- the transitional multi-stack fallback remains useful but secondary

If this topic is ever reopened, the first question is not "finish Phase 14 by
default", but rather:

- is there a measured local or CI need that the current green one-stack model
  no longer satisfies?

## Goal

Build a Playwright E2E architecture that is truly independent test-by-test and
worker-by-worker, so the suite can scale mostly with Playwright workers instead
of duplicating full application stacks.

Primary target:

- one application stack per machine/job in the steady state
- worker-scoped test data and accounts
- no global `clearDb()` in normal specs
- no shared mutable user/account state across parallel workers
- Playwright workers used as the main acceleration lever

Secondary target:

- keep multi-stack sharding as a fallback for very large suites or CI scaling,
  but no longer as the primary strategy

This plan supersedes the "multiply stacks first" strategy as the main long-term
direction. The existing isolated-stack work remains useful as a fallback and for
CI sharding, but it is not the desired end state.

Implementation companion:

- [docs/e2e-independent-optimum-implementation-todo.md](./e2e-independent-optimum-implementation-todo.md)

## Current Implementation Context

This plan is being prepared on a dedicated working branch for the E2E/Playwright
optimization effort.

Context to keep in mind before starting implementation:

- the repo already contains transitional isolated-stack work in:
  - `Makefile`
  - `compose.yaml`
  - `src/frontend/apps/e2e/scripts/loopback-proxies.js`
  - `src/backend/e2e/viewsets.py`
  - `src/backend/e2e/tests/test_api_e2e.py`
- that transitional work already proved:
  - isolated `alpha` and `beta` E2E stacks can coexist
  - readiness can pass on both isolated stacks
  - shard-oriented runs can execute against an isolated stack
- this transitional work is **not** the target architecture anymore, but it is
  a valid fallback and must not be broken accidentally

Operational local commands to know:

- bootstrap backend-only E2E stack:
  - `make bootstrap-e2e`
- full E2E campaign from scratch:
  - `bash run_env_e2e.sh --from-scratch`
- full E2E campaign on an existing E2E stack:
  - `bash run_env_e2e.sh --reuse`

For this long-term initiative, prefer:

- local E2E environment first
- unit/backend-targeted validation during implementation
- full from-scratch E2E mainly before PRs or for high-confidence checkpoints

Execution reporting for this initiative lives in:

- `docs/e2e-independent-optimum-execution/index.md`
- `docs/e2e-independent-optimum-execution/current-status.md`
- `docs/e2e-independent-optimum-execution/checkpoints/phase-XX.md`

## Why This Is The Better Long-Term Direction

For this repo today, multiplying stacks is the safest way to parallelize because
the suite is still coupled to global state. But once tests are made truly
independent, the better model is:

- fewer application stacks
- more Playwright workers
- less Docker/bootstrap overhead
- better resource efficiency
- shorter iteration loops

This aligns with current Playwright guidance:

- tests should be isolated and avoid relying on shared mutable state
- authentication for stateful apps should use dedicated accounts when tests
  modify server-side state
- sharding is useful, but the strongest baseline is an independently parallel
  suite, not a serial suite multiplied by infrastructure

References:

- Playwright best practices: https://playwright.dev/docs/best-practices
- Playwright auth: https://playwright.dev/docs/auth
- Playwright fixtures: https://playwright.dev/docs/test-fixtures
- Playwright parallelism: https://playwright.dev/docs/test-parallel
- Playwright sharding: https://playwright.dev/docs/test-sharding
- Playwright CI: https://playwright.dev/docs/ci
- GitHub Actions billing: https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions
- GitHub product usage included: https://docs.github.com/en/billing/reference/product-usage-included
- GitHub Actions limits: https://docs.github.com/en/actions/reference/limits

## Current Repo Findings

Current suite shape:

- `27` app-drive Playwright specs
- `21` specs call `clearDb()`
- `25` specs call `login()`
- `1` spec uses `runFixture()`

Current technical constraints:

- `playwright.config.ts` uses `workers: 1`
- `playwright.config.ts` uses `fullyParallel: false`
- the suite depends heavily on:
  - `/api/v1.0/e2e/clear-db/`
  - `/api/v1.0/e2e/user-auth/`
  - shared fixed accounts like `drive@example.com`
  - global mutable data

Current bottlenecks:

- DB-wide truncation is used as normal test setup
- login happens repeatedly instead of being worker-scoped
- many tests rely on the same user/workspace names and same initial state
- fixture data is often global rather than namespaced
- the suite can only scale safely by duplicating the whole stack

Additional baseline notes from Phase 0:

- `src/frontend/apps/e2e/__tests__/app-drive/db.setup.ts` exists but is not
  wired by `playwright.config.ts`; the effective legacy control check is
  `src/frontend/apps/e2e/__tests__/app-drive/e2e-ready-smoke.spec.ts`
- `src/frontend/apps/e2e/__tests__/app-drive/login.spec.ts` and
  `src/frontend/apps/e2e/__tests__/app-drive/silent-login.spec.ts` are true
  OIDC/session controls and should not be merged blindly into synthetic
  bootstrap flows

### Phase 0 Spec Migration Inventory

The app-drive suite is currently split into these migration buckets:

- `legacy-control` (`2` specs):
  `e2e-ready-smoke.spec.ts`, `login.spec.ts`
- `worker-auth-only` (`3` specs):
  `config-custom-assets.spec.ts`, `left-bar.spec.ts`,
  `release-note.spec.ts`
- `isolated-workspace` (`13` specs):
  `breadcrumbs-from-page.spec.ts`, `context-menu.spec.ts`,
  `create-file-from-template.spec.ts`, `create-folder.spec.ts`,
  `delete-item.spec.ts`, `heic-file-preview.spec.ts`,
  `item/right-content-info.spec.ts`, `move-item.spec.ts`,
  `pdf-preview-layout.spec.ts`, `starred.spec.ts`, `upload.spec.ts`,
  `url-file-preview.spec.ts`, `viewer-routing.spec.ts`
- `auth-transition` (`3` specs):
  `language-sync.spec.ts`, `redirect-401.spec.ts`, `silent-login.spec.ts`
- `search-dataset` (`1` spec): `search.spec.ts`
- `multi-actor-share` (`1` spec): `share.spec.ts`
- `mount-fixture` (`2` specs):
  `mounts-basic.spec.ts`, `mounts-preview-cycles.spec.ts`
- `wopi-editor` (`2` specs):
  `wopi.spec.ts`, `wopi-onlyoffice-editnew.spec.ts`

These buckets are the dependency order for the migration waves: backend
bootstrap first, then worker fixtures, then low-risk worker-auth-only and
isolated-workspace specs, then search/share/mount/WOPI hotspots.

Current machine context used for this plan:

- `16` vCPU
- `31 GiB` RAM
- current state already shows that multiple full stacks are expensive

Current GitHub context used for this plan:

- repository is public
- GitHub-hosted Actions are therefore a realistic execution target
- CI cost pressure is lower than for a private GitHub Free repo
- CI still has practical limits around runtime, artifact size, and matrix
  complexity

## Target End State

### Core execution model

The steady-state target is:

- one application stack per machine or CI job
- many Playwright workers against that one stack
- one isolated account namespace per worker
- one isolated data namespace per test or scenario

That means:

- local dev fast path: one stack, Chromium-heavy run, many workers
- full local/browser-validation path: one stack, all browser projects, bounded
  worker count
- CI path: one stack per CI job; matrix by browser remains optional policy, not
  a correctness requirement

### Execution policies by environment

The target architecture must support three distinct execution policies:

#### 1. Local E2E machine

This is the primary optimization target.

Expected target:

- `1` stack
- multiple Playwright workers
- optional single-browser fast mode for iteration
- optional full 3-browser run for high confidence

Reason:

- this is where developer iteration speed matters most
- this machine has enough CPU/RAM to benefit from worker-based scaling
- stack duplication is the least efficient use of local resources

#### 2. GitHub public PR CI

This should be optimized for:

- fast signal
- good stability
- bounded artifact volume
- enough compatibility coverage without overcomplicating the matrix

Recommended target policy after migration:

- Chromium full suite with multiple workers
- WebKit and Firefox as reduced compatibility suites, or full suites only if
  duration remains acceptable
- `1` stack per CI job
- no default shard explosion on every PR

Reason:

- public GitHub repos can use GitHub-hosted Actions without the same private
  minutes pressure
- but PR feedback still needs to stay quick and readable
- artifact upload and matrix complexity remain real costs

#### 3. `main` / nightly CI

This should be the most complete policy.

Recommended target policy after migration:

- full browser coverage
- more workers than PR if stable
- optional shards only if the suite is still too slow after worker scaling
- retain traces/artifacts only where useful

Reason:

- this is the right place for exhaustive confidence
- it can carry a broader compatibility burden than PR CI

### What "independent" means here

For this repo, a test is independent only if it does not require any of the
following global resets or shared assumptions:

- truncating the whole DB
- reusing the same mutable account as another worker
- reusing the same mutable workspace/folder names as another worker
- assuming search fixtures are global
- assuming mounts share the same writable namespace across tests
- relying on "first boot" side effects such as automatic profile mutation

## Architecture Principles

### 1. One stack per machine/job, not per browser by default

Once tests are independent, the application stack can serve many workers and
many browsers concurrently. The minimum required number of stacks becomes:

- `1` stack per local run
- `1` stack per CI job

Not:

- one stack per browser
- one stack per shard

Those remain fallback scaling modes only if the suite is still too large after
the independence work.

For this repo, this principle applies to both:

- the local E2E machine
- GitHub public CI jobs

The repo being public improves CI feasibility, but it does not change the fact
that worker-based scaling on one stack is the cleaner long-term architecture.

### 2. One account per worker for mutable flows

Playwright explicitly recommends avoiding shared accounts when tests mutate
server-side state. For this repo, the default must become:

- one logical worker actor account per worker
- optional additional actor accounts for multi-user scenarios

Not:

- one global `drive@example.com` account reused by every test

### 3. One namespace per worker and per scenario

Every worker must get deterministic isolation keys, derived from:

- run id
- project/browser
- worker parallel index

Every scenario that writes data must do so under a unique namespace, for
example:

- folder title prefix
- workspace title suffix
- search fixture namespace
- mount test root subfolder

### 4. Global reset is a fallback, not the normal path

`clearDb()` must stop being the default setup primitive for normal specs.

It should remain only for:

- dedicated readiness/bootstrap smoke
- legacy fallback while migrating tests
- occasional emergency cleanup flows

### 5. Test bootstrap must be declarative and idempotent

E2E setup should become scenario-driven:

- "give me an authenticated actor"
- "give me an actor with a clean workspace namespace"
- "give me two actors sharing one folder"
- "give me a search dataset under namespace X"

Not:

- "truncate everything, then rebuild the world"

### 6. The initiative must be reviewable in-place

The implementing agent must not rely on conversational memory alone.

At meaningful checkpoints, the state of the initiative must be written under:

- `docs/e2e-independent-optimum-execution/`

So that an orchestrator can review progress directly from the repository without
requiring the user to copy/paste context across conversations.

## What Must Change

## A. Backend E2E Contract

### A1. Replace ad hoc user bootstrapping with explicit actor bootstrapping

Create or evolve E2E-only endpoints/services so the test runner can request
well-defined actors and namespaces.

Recommended contract:

- `POST /api/v1.0/e2e/bootstrap-session/`
  - authenticates a test actor in the browser session
  - accepts actor key, run id, worker key, optional scenario
  - ensures the actor profile is fully initialized
  - returns stable metadata useful to the test harness

- `POST /api/v1.0/e2e/bootstrap-scenario/`
  - provisions scenario data under an explicit namespace
  - examples:
    - clean workspace root
    - share scenario
    - search dataset
    - mount fixture tree
    - preview dataset

- optional `POST /api/v1.0/e2e/cleanup-scope/`
  - deletes data created for one run/worker/scenario
  - cleanup should be precise, not DB-global

Key properties:

- idempotent
- namespaced
- authorization enforced via current E2E S2S token model
- no leaking provider/storage secrets

### A2. Introduce first-class run and worker namespace semantics

Every E2E-created object should be attributable to:

- run id
- worker key
- scenario key

This can be encoded through:

- titles/prefixes
- metadata fields
- dedicated E2E tracking records

Preferred direction:

- a small E2E bootstrap service layer that centralizes naming, ownership and
  cleanup

### A3. Stop depending on global DB truncation for correctness

The backend should allow isolated test setup without requiring:

- `TRUNCATE` of every table
- re-running onboarding assumptions globally

This means:

- actor bootstrap creates or reuses only the requested actor
- workspace bootstrap creates only the requested namespace
- fixture bootstrap creates only the requested dataset

### A4. Make search/index fixtures namespace-safe

Today search uses one global fixture command.

Long-term target:

- search fixture bootstrap must create data under a worker/scenario namespace
- tests must search within that namespace or against known unique titles
- fixture completion must wait for indexing deterministically

### A5. Make mount fixtures namespace-safe

Mount tests must stop sharing a mutable mount root implicitly.

Needed:

- dedicated subfolder per run/worker inside the mounted backend
- cleanup path for that subfolder
- no fixed filenames shared across tests

### A6. Quality improvements worth doing in product-adjacent code

These are not infra changes, but they improve both product quality and test
quality:

- make first-render user/profile side effects explicit and predictable
- avoid requiring profile mutation during ordinary page boot
- make onboarding/setup idempotent
- ensure stateful APIs used by tests are deterministic and safe to retry
- disable non-essential debug tooling in test contexts where it causes false
  failures or overhead

## B. Frontend / Playwright Harness

### B1. Replace `clearDb() + login()` as the default test preamble

Current pattern:

- clear DB
- login
- start testing

Target pattern:

- get worker fixture
- get actor fixture
- get isolated scenario fixture
- start testing

### B2. Add worker-scoped actor fixtures

Create worker-scoped Playwright fixtures for:

- primary actor account
- optional secondary actor account
- optional anonymous context

Auth state should be generated once per worker and reused across tests in that
worker, following Playwright auth best practices for stateful apps.

### B3. Add scenario-scoped fixtures

Recommended fixture families:

- `isolatedWorkspace`
- `sharedWorkspace`
- `searchDataset`
- `mountFixtureTree`
- `previewFixtureSet`

Each scenario fixture should:

- bootstrap data via E2E APIs
- expose IDs/paths/titles to the spec
- avoid relying on global browse state

### B4. Make names deterministic

All names created by tests should derive from:

- run id
- browser/project name
- worker parallel index
- short scenario slug

This avoids collisions across:

- workers
- browsers
- retries
- shards

### B5. Keep auth-specific flows separate

Tests whose purpose is to verify:

- login page
- Keycloak round-trip
- unauthorized redirects

should remain in a dedicated category and may still use explicit sign-in flows.

All other tests should use prebootstrapped authenticated fixtures instead of
walking through login repeatedly.

## C. Playwright Configuration Strategy

### C1. Move from "serial by necessity" to "parallel by construction"

Once the suite is migrated:

- global `workers` can increase
- `fullyParallel` can be enabled selectively where justified
- project-level worker caps can protect sensitive projects if needed

The intended progression is:

1. keep `fullyParallel: false`, increase `workers`
2. make whole files independent
3. optionally enable `test.describe.configure({ mode: 'parallel' })` in safe
   files
4. only then consider `fullyParallel: true` globally

### C2. Use worker percentages and project caps

Playwright supports worker counts as a percentage of logical CPU cores.

Recommended starting point for this machine:

- local Chromium-focused fast run: `workers: '50%'`
- local full multi-browser run: start with total effective concurrency around
  `6`, then benchmark `8`

Because this host has `16` vCPU and `31 GiB` RAM, the likely sustainable range
after true independence is:

- `6` workers total as the first safe target
- `8` workers total as the next benchmark target

Do not jump directly to `16`.

### C3. Use project dependencies only for setup that is really setup

The readiness smoke should stay separate from product specs.

Long-term:

- use a setup project or worker fixtures for auth/bootstrap concerns
- keep readiness/bootstrap checks out of the product suite counts

## D. CI Strategy

## D1. Recommended default CI topology after migration

Preferred PR topology:

- one app stack per job
- Chromium full suite with multiple workers
- WebKit/Firefox targeted compatibility suite, not necessarily the entire
  product suite, if policy allows
- keep artifact retention and trace scope disciplined to avoid noisy PR runs

Preferred nightly/main topology:

- one stack per job
- full browser coverage
- optional sharding only if run time still exceeds SLA
- allow a broader compatibility and artifact policy than PR

This is the best resource/perf compromise for most teams.

### D1.a Public GitHub repo implication

Because this repository is public, GitHub-hosted Actions are a realistic part of
the target design.

That changes the plan in one important way:

- we do not need to optimize CI primarily around scarce private-plan minutes

But it does not change these priorities:

- local E2E remains the main optimization target
- PR CI should still stay lean and fast
- `main` / nightly can carry the heaviest validation
- matrix size should still be justified by signal quality, not by "it is free"

## D2. Keep sharding as a second-stage scaler

After independence work, sharding should become optional:

- only used if one job with many workers is still too slow
- only used for very large CI throughput requirements

Then the scaling path becomes:

1. increase workers on one stack/job
2. if still too slow, add browser/job matrix
3. if still too slow, add shards

Not the reverse.

## E. Migration Plan

## F. Orchestrator Checkpoint Policy

The implementing agent must stop and request orchestrator confirmation after:

- Phase 1
- Phase 3
- Phase 5
- Phase 8
- Phase 10
- pre-Phase 12
- post-Phase 12

At each checkpoint, the implementing agent must:

1. update `docs/e2e-independent-optimum-execution/current-status.md`
2. create or update the matching checkpoint file in:
   - `docs/e2e-independent-optimum-execution/checkpoints/`
3. summarize:
   - what changed
   - what passed
   - what remains risky
   - what the next phase will touch
4. stop and wait for orchestrator review before continuing

### Phase 0. Baseline and guardrails

- record current suite duration by:
  - Chromium only
  - full 3-browser run
- record current suite duration separately for:
  - local E2E machine
  - GitHub PR CI
  - GitHub `main` / nightly CI if available
- record current flake hotspots
- tag every spec with one migration category:
  - `auth-only`
  - `single-user isolated`
  - `multi-user share`
  - `search/index`
  - `mount/storage`
  - `wopi/editors`

Acceptance:

- every spec is categorized
- every spec has an owner fixture strategy

### Phase 1. Backend bootstrap primitives

- implement worker/scenario-aware E2E bootstrap endpoints/services
- introduce actor bootstrap
- introduce scenario bootstrap
- introduce optional scoped cleanup
- make bootstrap idempotent

Acceptance:

- an actor can be created/reused without DB truncation
- a scenario can be created under a unique namespace
- repeating bootstrap does not corrupt state

### Phase 2. Frontend fixture rewrite

- add worker-scoped actor fixtures
- add scenario fixtures
- remove `clearDb()` from default helpers
- remove repetitive login from normal specs

Acceptance:

- a normal single-user test uses zero DB-global cleanup
- a worker reuses one authenticated actor state safely

### Phase 3. Migrate easy single-user specs first

Prioritize:

- config/custom assets
- left bar
- release note
- preview routing where no multi-user interaction is needed
- create/move/delete/upload single-user CRUD

Acceptance:

- these specs run in parallel workers on one stack with no collisions

### Phase 4. Migrate multi-user/share specs

- create paired worker-scoped actors
- bootstrap shared resources via scenario fixture
- remove any dependence on globally named accounts

Acceptance:

- share tests no longer require DB truncation
- multiple share tests can run concurrently

### Phase 5. Migrate search and asynchronous fixture specs

- replace global search fixture with namespaced dataset bootstrap
- add deterministic wait-for-indexing primitive

Acceptance:

- search tests are worker-safe
- no global fixture pollution

### Phase 6. Migrate mount and preview specs

- provision per-worker mount subtrees
- isolate preview fixture files by namespace
- ensure cleanup is mount-safe and provider-agnostic

Acceptance:

- mount tests can run concurrently without shared file collisions

### Phase 7. Raise worker count on one stack

Suggested benchmark ladder on this host:

- `workers: 4`
- `workers: 6`
- `workers: 8`

Measure at each step:

- wall-clock duration
- CPU saturation
- RAM pressure
- flake rate

Acceptance:

- choose the highest level that remains stable and leaves healthy RAM headroom

### Phase 8. Reevaluate browser strategy

Once the suite is independent:

- decide PR policy:
  - full Chromium + targeted WebKit/Firefox
  - or full 3-browser suite if duration remains acceptable
- decide nightly policy:
  - full matrix
  - optional shards if still needed

Acceptance:

- documented policy for:
  - local dev
  - pre-PR
  - nightly/main

## Resource Model: Current Plan vs True Optimum

Current multi-stack direction:

- primary speedup comes from multiplying stacks
- good for correctness while state is global
- expensive in RAM/CPU and bootstrap time

True-optimum direction after independence:

- primary speedup comes from Playwright workers on one stack per machine/job
- much lower Docker overhead
- much better resource efficiency

Expected steady-state target:

- local: `1` stack, multiple workers
- GitHub PR CI: `1` stack per job, multiple workers, limited browser policy
- GitHub `main` / nightly CI: `1` stack per job, multiple workers, broader
  browser policy
- shards only when genuinely needed

### Example target envelopes

These are planning targets, not hard commitments.

Local E2E machine, first stable target:

- `1` stack
- `6` workers total
- Chromium fast run as the day-to-day default
- full 3-browser run as a heavier validation

Local E2E machine, second benchmark target:

- `1` stack
- `8` workers total
- keep only if RAM and flake rate remain healthy

GitHub PR CI target:

- `1` stack per job
- Chromium with multiple workers
- optional WebKit/Firefox reduced scope or full scope depending on duration

GitHub `main` / nightly target:

- `1` stack per job
- broader browser coverage
- optional shards only after worker scaling has been exhausted

## Recommended Quality Improvements Beyond Pure Test Speed

These are worth doing because they improve both the app and the testability:

- make user bootstrap explicit and fully initialized
- remove first-render profile mutations where possible
- keep API writes idempotent when retries are legitimate
- reduce reliance on global mutable defaults
- reduce hidden onboarding side effects
- make search/indexing completion observable for tests
- make mounts test fixtures namespace-aware rather than path-global

## Risks

- the biggest migration risk is half-migrating the suite and ending up with two
  competing models at once
- mount and WOPI flows will likely be the slowest families to fully decouple
- some existing tests may reveal real product coupling that deserves fixing

## Non-Goals

- no product infra redesign for local/prod
- no requirement to change production deployment topology
- no provider-specific branching in mount behavior
- no unsafe shortcuts like in-memory full downloads just to simplify tests

## Final Recommendation

Do not continue the "many isolated stacks first" plan as the primary roadmap.

Use the already-built isolated-stack work only as:

- a transitional safety net
- a fallback CI scaling mode
- a diagnostic tool

The main roadmap should now be:

1. make the suite independent
2. move to one stack per machine/job
3. increase Playwright workers
4. shard only if the suite is still too large

Closeout outcome:

- steps `1` through `3` are satisfied in the implemented architecture
- step `4` remained optional and was not needed
- initiative closed without Phase `14`
