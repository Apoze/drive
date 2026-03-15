# E2E Optimization Follow-Up Plan

## Summary

This follow-up starts after the independent one-stack E2E initiative was
closed successfully without Phase 14 sharding.

Execution note (2026-03-15):

- Phase 0 baseline freeze and Phase 1 token cleanup are tracked in
  [execution/current-status.md](./execution/current-status.md) and
  [execution/checkpoints/phase-01.md](./execution/checkpoints/phase-01.md).

What is already true:

- the independent harness is green
- the legacy readiness smoke is green
- `bash run_env_e2e.sh --from-scratch` is green
- the representative local Chromium benchmark is green at
  `PLAYWRIGHT_WORKERS=4`
- CI policy is intentionally conservative:
  - pull requests: Chromium only, `workers=1`
  - `main` / `workflow_dispatch`: Chromium, WebKit, Firefox, `workers=1`

What is still suboptimal:

- local default remains `PLAYWRIGHT_WORKERS=1`
- CI browser jobs are still fully serial inside each browser job
- the local wrappers still rely on a committed S2S token instead of a clean
  local runtime contract
- the transitional multi-stack fallback remains present and undocumented as a
  second-class path
- sharding was never re-evaluated after the harness became stable

This new initiative does **not** reopen the previous architecture project.
It optimizes the now-stable one-stack model first, and evaluates sharding only
if measured runtime still justifies it.

## Current Baseline

### Local baseline

From the closed initiative:

- representative benchmark batch size:
  `65` Chromium tests
- stable measured point:
  `PLAYWRIGHT_WORKERS=4`
- representative benchmark result:
  `65 passed / 0 failed`
- representative benchmark wall time:
  about `3.0m`

Current defaults:

- `PLAYWRIGHT_WORKERS=1` in [Makefile](/root/Apoze/drive/Makefile)
- `PLAYWRIGHT_WORKERS=1` in
  [run_env_e2e.sh](/root/Apoze/drive/run_env_e2e.sh)
- CI hard-forces `workers=1` in
  [playwright.config.ts](/root/Apoze/drive/src/frontend/apps/e2e/playwright.config.ts)

### CI baseline

Current policy in
[drive-frontend.yml](/root/Apoze/drive/.github/workflows/drive-frontend.yml):

- PR:
  one Chromium E2E job with readiness, `workers=1`
- `main` and `workflow_dispatch`:
  browser matrix (`chromium`, `webkit`, `firefox`) with readiness,
  `workers=1`

Recent green `main` run baseline:

- whole Frontend Workflow:
  about `20m`
- browser job durations:
  - Chromium:
    about `17m48s`
  - Firefox:
    about `19m36s`
  - WebKit:
    about `19m48s`

Each browser job still pays:

- stack bootstrap cost
- readiness cost
- one fully serial Playwright run

## Goals

Primary goals:

- make local E2E iteration faster on the stable one-stack model
- make the CI contract cleaner and more explicit
- remove the fragile local S2S token handling
- reduce CI wall time where it is safe to do so
- decide whether sharding is still worth doing after one-stack optimization

Non-goals:

- no product redesign
- no return to "multi-stack by default"
- no `fullyParallel: true` rollout in this initiative
- no reopening of the old Phase 14 unless runtime data proves it is needed

## Decisions And Defaults

### 1. Canonical local S2S token contract

The single canonical runtime input becomes:

- `DRIVE_E2E_S2S_TOKEN`

Derived variables remain implementation details:

- backend:
  `DJANGO_SERVER_TO_SERVER_API_TOKENS`
- Playwright runner:
  `E2E_S2S_TOKEN`

Contract:

- local wrappers and Make targets must derive both legacy variables from
  `DRIVE_E2E_S2S_TOKEN`
- the token must never stay hardcoded in committed shell scripts
- if the canonical token is missing, `make bootstrap-e2e` and the
  `run-tests-e2e*` targets must fail early with a clear message

Temporary compatibility rule:

- if `DRIVE_E2E_S2S_TOKEN` is absent but both legacy variables are present and
  equal, the tooling may accept them for one transition window
- any other mixed state must fail fast

### 2. Local default worker policy

Target promotion path:

- first candidate default:
  `PLAYWRIGHT_WORKERS=4`
- `6` stays opt-in unless it clearly beats `4`

Promotion gate for changing the local default from `1` to `4`:

- representative benchmark batch at `4`:
  `3/3` green
- full Chromium campaign on reused stack at `4`:
  `2/2` green
- full Chromium from scratch at `4`:
  `1/1` green
- full browser campaign from scratch at the existing default path:
  still green
- observed RAM peak stays below `28 GiB`

Promotion gate for considering `6` as default:

- all `workers=4` gates pass
- same stability gates pass at `6`
- runtime gain vs `4` is at least `10%`
- RAM peak stays below `28 GiB`

If those gates are not met:

- local default becomes `4` if `4` is stable
- otherwise local default stays `1`
- `6` remains explicitly benchmark-only

### 3. CI policy

PR policy target:

- keep Chromium only
- start by keeping `workers=1`
- add workflow `concurrency` with `cancel-in-progress: true`
- use one PR-scoped concurrency group:
  `frontend-pr-${{ github.event.pull_request.number }}`
- upload Playwright HTML report and raw `test-results/` only on
  `failure()` or `cancelled()`

`main` / `workflow_dispatch` policy target:

- keep Chromium/WebKit/Firefox matrix
- add `strategy.fail-fast: false`
- keep artifacts on failure only
- keep `workers=1` unless a separate CI benchmark phase proves `2` is stable

CI worker promotion rule:

- first and only target for this initiative:
  Chromium PR job at `workers=2`
- promotion gate:
  `5` manual `workflow_dispatch` runs green with no flakes and at least `15%`
  wall-time gain vs `workers=1`
- WebKit and Firefox stay at `1`

### 4. Transitional multi-stack fallback

Policy:

- keep the existing fallback working
- do not use it in the standard local or CI contract
- do not expand it further in this initiative

End-of-initiative decision:

- if sharding is not adopted, schedule a later cleanup mini-initiative to
  remove or archive the fallback
- if sharding is adopted, keep the fallback but document it explicitly as
  shard-only infrastructure

### 5. Sharding decision gate

Sharding is **not** part of the default plan.

It becomes eligible only if, after the token cleanup and one-stack worker
optimizations:

- PR Chromium E2E still exceeds `15m` wall time
- or the slowest `main` browser job still exceeds `18m` wall time

If opened, the only allowed first step is:

- Chromium-only
- `2` shards
- `workers=1` per shard
- `fullyParallel: false`
- blob report + report merge
- file-level sharding only; no test-level balancing attempt in this initiative

If measured gain is below `20%` or stability regresses, the sharding effort is
closed immediately and the fallback remains non-default.

## Workstreams

### Workstream A — Env and token hygiene

- remove the committed local token from the wrapper
- define one canonical local token input
- make all E2E entrypoints fail early when the token contract is incomplete
- keep CI secret usage unchanged at the source level, but allow workflows to
  export only the canonical name if desired

### Workstream B — Local speed on one stack

- add a dedicated local full-Chromium target
- benchmark and promote a safe local worker default
- keep the full three-browser path available for final confidence

### Workstream C — CI runtime efficiency

- add workflow concurrency cancellation
- reduce artifact upload cost
- keep browser breadth while preserving failure visibility
- optionally promote Chromium PR CI to `workers=2` if measured stable

### Workstream D — Fallback and shard policy

- document the multi-stack path as fallback-only
- run a narrow shard spike only if runtime still demands it
- decide explicitly whether fallback stays for shard-only use or becomes
  removable debt

## Acceptance Criteria

The optimization initiative is done when:

- the local token contract is clean, explicit, and non-hardcoded
- the local default worker count is evidence-based and documented
- CI has explicit concurrency and artifact policies
- CI worker policy is either:
  - unchanged for good reasons, or
  - promoted with measured evidence
- sharding is either:
  - explicitly rejected with evidence, or
  - adopted narrowly with evidence
- the resulting docs make the standard path obvious:
  one stack first, fallback only when justified

## References

- Playwright auth:
  https://playwright.dev/docs/auth
- Playwright parallelism:
  https://playwright.dev/docs/test-parallel
- Playwright sharding:
  https://playwright.dev/docs/test-sharding
- Playwright CI:
  https://playwright.dev/docs/ci
- GitHub Actions concurrency:
  https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-your-workflow-runs/control-workflow-concurrency
- GitHub Actions matrix strategy:
  https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs
