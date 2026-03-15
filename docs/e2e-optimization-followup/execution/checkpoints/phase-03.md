# Phase 03 Checkpoint

- phase id:
  `phase-03`
- date/time UTC:
  `2026-03-15`
- branch:
  `codex/e2e-optimization-followup-phase1`
- objective:
  finish Phase 2 local command-surface cleanup, run the full Phase 3 local
  worker-promotion gate, then stop for orchestrator review

## What Changed

- added explicit local one-stack Make targets:
  `run-tests-e2e-full-chromium`
  and
  `run-tests-e2e-from-scratch-chromium`
- added both new targets to the canonical token-resolution gate so they require
  the same local contract as the other E2E entrypoints
- updated `docs/WorkDone/e2e/local-vs-ci.md` to document the canonical local
  one-stack command surface
- kept the public `run_env_e2e.sh` CLI unchanged:
  `--reuse`
  and
  `--from-scratch`
- did not change local defaults in `Makefile` or `run_env_e2e.sh` because the
  Phase 3 promotion gate did not pass
- did not touch CI worker policy, sharding, or the multi-stack fallback

## New Local Commands Available

- `make run-tests-e2e-full`
- `make run-tests-e2e-full-chromium`
- `make run-tests-e2e-benchmark-local`
- `make run-tests-e2e-from-scratch`
- `make run-tests-e2e-from-scratch-chromium`
- `bash run_env_e2e.sh --reuse`
- `bash run_env_e2e.sh --from-scratch`

## What Was Validated In Phase 2

- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-full`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-full-chromium`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-benchmark-local`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-from-scratch`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-from-scratch-chromium`
- real reused-stack Chromium run:
  `DRIVE_E2E_S2S_TOKEN=*** make run-tests-e2e-full-chromium`
  - result:
    `70 passed`, `1 skipped`, Playwright summary about `9.0m`,
    wall time `560.58s`

## Phase 3 Measurement Notes

- all Phase 3 runs used the canonical local token contract:
  `DRIVE_E2E_S2S_TOKEN=***`
- measurement used a temporary local helper under
  `tmp/e2e-optimization-followup-phase3/`
  to capture:
  - wall time
  - command status
  - peak sampled Docker CPU
  - peak sampled Docker RAM
- the helper was not added to the tracked repo surface

## Phase 3 Measured Results

### Benchmark Batch

- `workers=1`
  - result:
    green
  - summary:
    `65 passed`
  - wall time:
    `466s`
  - peak sampled CPU:
    `525.72%`
  - peak sampled RAM:
    `23.06 GiB`

- `workers=4` run 1
  - result:
    green
  - summary:
    `65 passed`
  - wall time:
    `184s`
  - peak sampled CPU:
    `1161.60%`
  - peak sampled RAM:
    `24.99 GiB`

- `workers=4` run 2
  - result:
    failed
  - summary:
    `62 passed`, `3 failed`
  - failing specs:
    `breadcrumbs-from-page.spec.ts`
    `context-menu.spec.ts`
    `viewer-routing.spec.ts`
  - wall time:
    `190s`
  - peak sampled CPU:
    `1130.00%`
  - peak sampled RAM:
    `25.15 GiB`

- `workers=6`
  - result:
    green
  - summary:
    `65 passed`
  - wall time:
    `182s`
  - peak sampled CPU:
    `1325.90%`
  - peak sampled RAM:
    `26.28 GiB`
  - runtime gain vs best `workers=4` run:
    about `1.1%`

### Full Chromium On Existing E2E Stack At `workers=4`

- run 1
  - result:
    failed
  - summary:
    `69 passed`, `1 failed`, `1 skipped`
  - failing spec:
    `share.spec.ts:136`
  - wall time:
    `224s`
  - peak sampled CPU:
    `1156.90%`
  - peak sampled RAM:
    `25.49 GiB`

- run 2
  - result:
    green
  - summary:
    `70 passed`, `1 skipped`
  - wall time:
    `225s`
  - peak sampled CPU:
    `1141.17%`
  - peak sampled RAM:
    `25.52 GiB`

### Full Chromium From Scratch At `workers=4`

- result:
  green
- summary:
  `70 passed`, `1 skipped`
- wall time:
  `287s`
- peak sampled CPU:
  `1507.92%`
- peak sampled RAM:
  `26.50 GiB`

### Stable Full Three-Browser From Scratch Path

- command path:
  existing default path with `PLAYWRIGHT_WORKERS=1`
- overall result:
  green
- overall wall time:
  `1935s`
- overall peak sampled CPU:
  `1479.33%`
- overall peak sampled RAM:
  `25.60 GiB`
- per-browser summaries:
  - Chromium:
    `68 passed`, `3 skipped`, about `8.2m`
  - WebKit:
    `67 passed`, `4 skipped`, about `12.1m`
  - Firefox:
    `67 passed`, `4 skipped`, about `10.4m`

## Decision On Local Worker Default

- local default stays:
  `PLAYWRIGHT_WORKERS=1`
- `workers=4` is not promotable because it failed the required stability gate:
  - benchmark requirement was `3/3` green and already failed on run 2
  - reused-stack full Chromium requirement was `2/2` green and only achieved
    `1/2`
- `workers=6` stays benchmark-only opt-in:
  - the stricter promotion gate cannot pass because `workers=4` already failed
  - its runtime gain vs the best `workers=4` run was only about `1.1%`
  - it used more RAM than `workers=4`
- memory was not the blocker:
  all measured peaks stayed below the plan cap of `28 GiB`

## Residual Risks

- the reused-stack and benchmark `workers=4` runs exposed instability in:
  `share`, `context-menu`, `viewer-routing`, and `breadcrumbs` paths
- the failure mix is broad enough that promotion without root-cause work would
  likely codify flakiness instead of reducing iteration time safely
- the stable one-stack default path remains slower locally, especially for the
  full from-scratch three-browser campaign

## What Phase 4 Would Touch

- `.github/workflows/drive-frontend.yml`
- `Makefile`
- `docs/e2e-optimization-followup/plan.md`

Phase 4 would focus on CI workflow efficiency only:
workflow concurrency, cancellation, artifact policy, and matrix fail-fast
behavior. It should not change CI worker counts yet.

## Recommendation

- `continue with caution`
