# Phase 04 Checkpoint

- phase id:
  `phase-04`
- date/time UTC:
  `2026-03-15`
- branch:
  `codex/e2e-optimization-followup-phase1`
- objective:
  implement the allowed CI workflow-efficiency changes only, validate them
  locally, then stop for orchestrator review without opening Phase 5

## What Changed

- updated `.github/workflows/drive-frontend.yml`
- added workflow-level `concurrency` with:
  - PR-scoped group:
    `frontend-pr-${{ github.event.pull_request.number }}`
  - `cancel-in-progress: true` for pull requests
- kept non-PR runs on unique fallback concurrency groups so this phase does not
  introduce accidental cancellation for `push` or `workflow_dispatch`
- added:
  `strategy.fail-fast: false`
  to `test-e2e-compat`
- changed Playwright artifact uploads in:
  - `test-e2e-pr`
  - `test-e2e-compat`
  so that both HTML reports and raw `test-results/` upload only on:
  `failure() || cancelled()`

## What Was Validated Locally

- YAML parse:
  `.github/workflows/drive-frontend.yml`
  via
  `python3` + `yaml.safe_load`
- `actionlint`:
  not available locally in this environment
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-browser E2E_BROWSER=chromium`
- static workflow coherence check against the resulting workflow:
  - top-level `concurrency`
  - PR cancellation scope
  - `needs`
  - job `if`
  - `strategy.fail-fast`
  - artifact upload conditions

## Phase 4 CI Policy Now Frozen

- pull requests:
  - still Chromium-only
  - still `workers=1`
  - workflow reruns for the same PR now cancel the older in-progress workflow
    via:
    `frontend-pr-${{ github.event.pull_request.number }}`
  - Playwright artifacts upload only on failure or cancellation
- `main` and `workflow_dispatch`:
  - still Chromium/WebKit/Firefox matrix
  - still `workers=1`
  - compat matrix now uses:
    `fail-fast: false`
  - Playwright artifacts upload only on failure or cancellation

## What Remains Intentionally Unchanged

- CI worker counts
- browser selection
- sharding policy
- `run_env_e2e.sh` public CLI
- one-stack default architecture
- transitional multi-stack fallback
- token wiring contract for local/CI E2E

## Why The Real Phase 5 Was Not Opened

- Phase 5 requires real GitHub-side measurement through pushed
  `workflow_dispatch` runs
- current constraints still forbid:
  commit, push, and PR work
- opening Phase 5 locally without those runs would produce an unverifiable CI
  worker decision, which would be weaker than the current conservative policy

## Residual Risks

- `actionlint` was not available locally, so validation relied on YAML parse,
  `make -n`, and static workflow inspection instead of the dedicated workflow
  linter
- artifact policy is now lighter, but successful runs no longer keep default
  Playwright reports/results as CI evidence
- PR concurrency behavior cannot be observed end-to-end without an actual
  GitHub PR rerun sequence

## What Phase 5 Would Touch When Git/GitHub Is Allowed

- `.github/workflows/drive-frontend.yml`
- `Makefile`
- `src/frontend/apps/e2e/playwright.config.ts`
- `docs/e2e-optimization-followup/plan.md`

Phase 5 would add a non-default Chromium PR experiment at `workers=2`, run the
required GitHub `workflow_dispatch` validation series, then decide whether the
default PR worker count can move from `1` to `2`.

## Recommendation

- `continue with caution`
