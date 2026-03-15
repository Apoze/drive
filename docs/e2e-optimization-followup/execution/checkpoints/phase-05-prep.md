# Phase 05 Prep Checkpoint

- phase id:
  `phase-05-prep`
- date/time UTC:
  `2026-03-15`
- branch:
  `codex/e2e-optimization-followup-phase1`
- objective:
  prepare the opt-in Chromium PR `workers=2` experiment path locally, validate
  the wiring statically, then stop before any real GitHub-side Phase 5 run

## What Changed

- updated `.github/workflows/drive-frontend.yml`
  - added `workflow_dispatch` input:
    `phase5_ci_experiment`
    with choices:
    `none`
    and
    `chromium-pr-workers2`
  - added workflow-dispatch-only job:
    `test-e2e-pr-workers2-experiment`
  - kept the normal PR job:
    `test-e2e-pr`
    unchanged
  - made `test-e2e-compat` skip itself when the workflow-dispatch experiment
    is selected, so the manual experiment path stays isolated
- updated `Makefile`
  - added opt-in targets:
    `run-tests-e2e-ci-browser-experiment`
    and
    `run-tests-e2e-ci-pr-workers2-experiment`
  - passed through:
    `PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE`
    to the Playwright runner container
- updated `src/frontend/apps/e2e/playwright.config.ts`
  - added explicit CI override gate:
    `PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE=1`
  - default CI behavior remains:
    `workers=1`
    unless that opt-in override is present

## What Was Validated Locally

- YAML parse:
  `.github/workflows/drive-frontend.yml`
  via
  `python3` + `yaml.safe_load`
- `actionlint`:
  not available locally in this environment
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr`
  - result:
    normal PR path still resolves to `PLAYWRIGHT_WORKERS=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-browser E2E_BROWSER=chromium`
  - result:
    normal CI browser path still resolves to `PLAYWRIGHT_WORKERS=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr-workers2-experiment`
  - result:
    opt-in experiment resolves to:
    `PLAYWRIGHT_WORKERS=2`
    and
    `PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-browser-experiment E2E_BROWSER=chromium PLAYWRIGHT_EXPERIMENTAL_WORKERS=2`
  - result:
    generic opt-in browser experiment path resolves identically
- static workflow audit:
  - checked `if`
  - checked `needs`
  - checked `concurrency`
  - checked `strategy`
  - checked workflow-dispatch input wiring
  - checked isolation of the experiment path relative to the normal PR path

## Exact Shape Of The Phase 5 Experimental Path

- manual trigger surface:
  workflow `Frontend Workflow`
  via `workflow_dispatch`
- opt-in selector:
  `phase5_ci_experiment=chromium-pr-workers2`
- dedicated workflow job:
  `test-e2e-pr-workers2-experiment`
- dedicated Make entrypoint:
  `run-tests-e2e-ci-pr-workers2-experiment`
- effective worker path:
  - `PLAYWRIGHT_WORKERS=2`
  - `PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE=1`
- default path remains separate:
  - PRs still call:
    `run-tests-e2e-ci-pr`
  - standard manual compat still calls:
    `run-tests-e2e-ci-browser`
    across the browser matrix when no experiment is selected

## What Remains Intentionally Unchanged

- default PR CI policy:
  Chromium only, `workers=1`
- default compat policy:
  Chromium/WebKit/Firefox, `workers=1`
- local default:
  `PLAYWRIGHT_WORKERS=1`
- sharding
- browser scope
- one-stack default architecture
- public `run_env_e2e.sh` CLI

## Why The Real Phase 5 Decision Remains Blocked

- the actual Phase 5 decision requires
  `5`
  real GitHub-side `workflow_dispatch` runs
  on pushed code
- current constraints still forbid:
  commit, push, and PR work
- without those runs there is no honest basis to conclude whether
  Chromium PR CI can move from `workers=1` to `workers=2`

## Residual Risks

- `actionlint` was not available locally, so validation relied on YAML parse,
  `make -n`, and static review
- the new workflow-dispatch experiment path has not been exercised on GitHub
  yet, so real runner behavior, timing, and artifact emission still need live
  confirmation
- the Playwright CI override path is intentionally narrow, but it still needs
  live verification under actual GitHub `CI=true` conditions

## What Will Need To Happen Later With Git/GitHub Authorized

- push the prepared branch/workflow changes
- trigger the opt-in experiment path on GitHub with:
  `phase5_ci_experiment=chromium-pr-workers2`
- run the required
  `5`
  manual experiment runs
- compare:
  - wall time vs the current `workers=1` PR baseline
  - flakes
  - OOM or bootstrap failures
  - artifact behavior
- only then decide whether the default PR Chromium worker count can change

## Recommendation

- `continue with caution`
