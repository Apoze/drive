# E2E Optimization Follow-Up Current Status

- status:
  `phase_05_github_ready_complete_waiting_orchestrator_review`
- branch:
  `codex/e2e-optimization-followup-phase1`
- current phase:
  `phase-05-github-ready`
- summary:
  the GitHub readiness handoff is complete: workflow-dispatch control and
  experiment paths are explicit, `actionlint` is clean locally, the default CI
  policy remains unchanged, and the real Phase 5 decision stays blocked pending
  Git-enabled execution
- next expected checkpoint:
  `orchestrator review of phase-05-github-ready.md`

## Phase 0 — Baseline Freeze

- `docker compose ps` before changes:
  healthy local stack
- frozen baseline commands:
  - local benchmark:
    `PLAYWRIGHT_WORKERS=4 make run-tests-e2e-benchmark-local`
  - full Chromium on reused stack:
    current improvised sequence is `make run-tests-e2e-readiness` then
    `E2E_NETWORK_MODE=manual ... make run-tests-e2e -- --project chromium`
  - full from scratch:
    `bash run_env_e2e.sh --from-scratch`
  - CI PR:
    workflow `test-e2e-pr` runs `make bootstrap-e2e` then
    `ENV_OVERRIDE=e2e make run-tests-e2e-ci-pr`
  - CI browser matrix:
    workflow `test-e2e-compat` runs `make bootstrap-e2e` then
    `ENV_OVERRIDE=e2e make run-tests-e2e-ci-browser E2E_BROWSER=<browser>`
- frozen observed durations before Phase 1:
  - representative local benchmark at `PLAYWRIGHT_WORKERS=4`:
    about `3.0m` for `65` Chromium tests
  - recent green Frontend Workflow:
    about `20m`
  - recent green CI browser jobs:
    Chromium `17m48s`, Firefox `19m36s`, WebKit `19m48s`
  - note:
    the closed initiative recorded green status for the full from-scratch path
    but did not store a standalone wall time for `bash run_env_e2e.sh --from-scratch`
  - note:
    there was no dedicated local reused-stack full-Chromium target or
    standalone wall time before this follow-up

## Phase 1 — Canonical Token Contract

- added shared resolver:
  `bin/resolve_e2e_s2s_token.sh`
- `Makefile` now resolves one local token contract for all E2E entrypoints,
  exports:
  `DRIVE_E2E_S2S_TOKEN`,
  `DJANGO_SERVER_TO_SERVER_API_TOKENS`,
  `E2E_S2S_TOKEN`,
  and fails early on missing or inconsistent states
- `run_env_e2e.sh` now uses the shared resolver and no longer commits a token
- `docs/env_freeze_report.md` now documents the canonical local input and the
  temporary legacy transition path
- no change in local worker default, CI worker policy, sharding policy, or the
  multi-stack fallback

## Phase 2 — Local Command Surface Cleanup

- added explicit local one-stack targets:
  `run-tests-e2e-full-chromium`
  and
  `run-tests-e2e-from-scratch-chromium`
- both new targets participate in the canonical token resolution gate
- `docs/WorkDone/e2e/local-vs-ci.md` now documents the canonical local
  one-stack commands:
  - `make run-tests-e2e-full`
  - `make run-tests-e2e-full-chromium`
  - `make run-tests-e2e-benchmark-local`
  - `make run-tests-e2e-from-scratch`
  - `make run-tests-e2e-from-scratch-chromium`
  - `bash run_env_e2e.sh --reuse`
  - `bash run_env_e2e.sh --from-scratch`
- wrapper CLI stayed unchanged:
  `--reuse`
  and
  `--from-scratch`

## Phase 2 Validation

- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-full`:
  passed
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-full-chromium`:
  passed
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-benchmark-local`:
  passed
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-from-scratch`:
  passed
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-from-scratch-chromium`:
  passed
- targeted real run on current E2E stack:
  `DRIVE_E2E_S2S_TOKEN=*** make run-tests-e2e-full-chromium`
  - result:
    `70 passed`, `1 skipped`, Playwright summary about `9.0m`,
    wall time `560.58s`

## Phase 3 — Local Worker Promotion Gate

- measured benchmark batch:
  - `workers=1`:
    green, `466s`, RAM peak `23.06 GiB`
  - `workers=4` run 1:
    green, `184s`, RAM peak `24.99 GiB`
  - `workers=4` run 2:
    failed, `190s`, RAM peak `25.15 GiB`
  - `workers=6`:
    green, `182s`, RAM peak `26.28 GiB`
- measured full Chromium on reused stack at `workers=4`:
  - run 1:
    failed, `224s`, RAM peak `25.49 GiB`
  - run 2:
    green, `225s`, RAM peak `25.52 GiB`
- measured full Chromium from scratch at `workers=4`:
  green, `287s`, RAM peak `26.50 GiB`
- measured stable full three-browser from scratch path at the existing default:
  green, `1935s`, RAM peak `25.60 GiB`
  - Chromium:
    `68 passed`, `3 skipped`, about `8.2m`
  - WebKit:
    `67 passed`, `4 skipped`, about `12.1m`
  - Firefox:
    `67 passed`, `4 skipped`, about `10.4m`
- decision:
  local default remains `PLAYWRIGHT_WORKERS=1`
- reason:
  `workers=4` failed the required stability gate before promotion, and
  `workers=6` improved runtime by only about `1.1%` vs the best `workers=4`
  run while using more RAM

## Phase 3 Failure Notes

- benchmark `workers=4` run 2 failed with:
  - `breadcrumbs-from-page.spec.ts`
  - `context-menu.spec.ts`
  - `viewer-routing.spec.ts`
- reused-stack full Chromium `workers=4` run 1 failed with:
  - `share.spec.ts:136`
- all measured peaks stayed below the plan cap of `28 GiB`; stability, not
  memory, blocked promotion

## Phase 4 — CI Workflow Efficiency Without Worker Changes

- `.github/workflows/drive-frontend.yml` now defines workflow-level
  `concurrency`
  with:
  - PR-scoped group:
    `frontend-pr-${{ github.event.pull_request.number }}`
  - `cancel-in-progress: true` for pull requests only
- non-PR runs keep unique fallback concurrency groups so Phase 4 does not
  introduce cross-run cancellation outside pull requests
- `test-e2e-compat` now sets:
  `strategy.fail-fast: false`
- Playwright HTML report and raw `test-results/` artifacts now upload only on:
  `failure() || cancelled()`
  for both:
  - `test-e2e-pr`
  - `test-e2e-compat`
- browser selection remains unchanged:
  PR stays Chromium-only; non-PR stays Chromium/WebKit/Firefox
- CI workers remain unchanged:
  `workers=1`
- sharding remains untouched
- Phase 5 was intentionally not opened because its required validation depends
  on pushed GitHub `workflow_dispatch` runs, which remains outside the current
  no-commit / no-push / no-PR constraint

## Phase 4 Validation

- YAML parse:
  `python3` + `yaml.safe_load` on
  `.github/workflows/drive-frontend.yml`
  passed
- `actionlint`:
  not available locally in this environment
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr`:
  passed
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-browser E2E_BROWSER=chromium`:
  passed
- static workflow audit:
  checked the coherence of
  `if`,
  `needs`,
  `concurrency`,
  `strategy.fail-fast`,
  and artifact upload conditions against the resulting diff

## Phase 5 Prep — Local Preflight Only

- added opt-in Make targets:
  - `run-tests-e2e-ci-browser-experiment`
  - `run-tests-e2e-ci-pr-workers2-experiment`
- added a dedicated CI override env path in
  `src/frontend/apps/e2e/playwright.config.ts`:
  `PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE=1`
- kept the default CI worker rule unchanged:
  CI still resolves to `workers=1` unless that explicit override is present
- added `workflow_dispatch` input:
  `phase5_ci_experiment`
  with choices:
  - `none`
  - `chromium-pr-workers2`
- added a workflow-dispatch-only job:
  `test-e2e-pr-workers2-experiment`
- kept the normal PR path unchanged:
  `test-e2e-pr` still runs Chromium at `workers=1`
- isolated the opt-in path from the standard manual compat path:
  when the workflow-dispatch input selects the experiment,
  `test-e2e-compat` is skipped
- true Phase 5 remains blocked:
  no GitHub-side `workflow_dispatch` runs were executed in this phase

## Phase 5 Prep Validation

- YAML parse:
  `.github/workflows/drive-frontend.yml`
  passed
- `actionlint`:
  not available locally in this environment
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr`:
  passed and still resolves to `PLAYWRIGHT_WORKERS=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-browser E2E_BROWSER=chromium`:
  passed and still resolves to `PLAYWRIGHT_WORKERS=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr-workers2-experiment`:
  passed and resolves to:
  `PLAYWRIGHT_WORKERS=2`
  plus
  `PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-browser-experiment E2E_BROWSER=chromium PLAYWRIGHT_EXPERIMENTAL_WORKERS=2`:
  passed with the same opt-in worker override
- static workflow audit:
  checked the coherence of
  `if`,
  `needs`,
  `concurrency`,
  `strategy`,
  workflow-dispatch inputs,
  and the isolation of the experiment path relative to the normal PR path

## Phase 5 GitHub Readiness

- strengthened the prepared workflow-dispatch surface so Phase 5 can compare a
  PR-equivalent control and experiment on the same GitHub trigger type
- `.github/workflows/drive-frontend.yml` now exposes:
  - `phase5_ci_experiment=chromium-pr-workers1-control`
  - `phase5_ci_experiment=chromium-pr-workers2`
- added a workflow-dispatch-only control job:
  `test-e2e-pr-workers1-control`
- added an explicit Make alias:
  `run-tests-e2e-ci-pr-workers1-control`
- kept the normal PR job unchanged:
  `test-e2e-pr` still runs Chromium at `workers=1`
- kept the standard compat workflow-dispatch path unchanged when:
  `phase5_ci_experiment=none`
- `actionlint` initially caught one duplicated workflow job key during the local
  refinement; that defect was fixed before this checkpoint

## Phase 5 GitHub Readiness Validation

- `docker compose ps`:
  healthy stack
- YAML parse:
  `.github/workflows/drive-frontend.yml`
  passed via
  `python3` + `yaml.safe_load`
- `actionlint`:
  installed temporarily under
  `tmp/actionlint/actionlint`
  at version
  `1.7.11`
  and now passes cleanly on
  `.github/workflows/drive-frontend.yml`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr`:
  passed and still resolves to `PLAYWRIGHT_WORKERS=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-browser E2E_BROWSER=chromium`:
  passed and still resolves to `PLAYWRIGHT_WORKERS=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr-workers1-control`:
  passed and resolves to the same conservative Chromium PR path at
  `PLAYWRIGHT_WORKERS=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr-workers2-experiment`:
  passed and resolves to:
  `PLAYWRIGHT_WORKERS=2`
  plus
  `PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-browser-experiment E2E_BROWSER=chromium PLAYWRIGHT_EXPERIMENTAL_WORKERS=2`:
  passed with the same opt-in worker override
- static workflow audit:
  confirmed:
  - unique job keys
  - workflow-dispatch-only isolation of control and experiment jobs
  - unchanged PR default path
  - compat matrix skipped whenever a non-`none` experiment option is selected
  - distinct failure/cancelled artifact names for control vs experiment

## Validation

- `bash -n run_env_e2e.sh`:
  passed
- `DRIVE_E2E_S2S_TOKEN=*** make -n bootstrap-e2e`:
  passed
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-full`:
  passed
- `DRIVE_E2E_S2S_TOKEN=*** make run-backend-e2e`:
  passed
- `DOCKER_USER="$(id -u):$(id -g)" ENV_OVERRIDE=e2e docker compose up -d frontend-dev`:
  passed
- `DRIVE_E2E_S2S_TOKEN=*** make run-tests-e2e-readiness`:
  passed (`1` test, `17.1s`)
- `DJANGO_SERVER_TO_SERVER_API_TOKENS=*** E2E_S2S_TOKEN=*** make -n run-tests-e2e-full`:
  passed through the temporary legacy-compatibility path
- `env -u DRIVE_E2E_S2S_TOKEN -u DJANGO_SERVER_TO_SERVER_API_TOKENS -u E2E_S2S_TOKEN make -n run-tests-e2e-full`:
  failed early with a clear missing-contract message
- `env -u DRIVE_E2E_S2S_TOKEN -u DJANGO_SERVER_TO_SERVER_API_TOKENS -u E2E_S2S_TOKEN bash run_env_e2e.sh --reuse`:
  failed early with the same guidance
- `docker compose ps` after Phase 1 validation:
  healthy stack

## Local Workflow Dependency Note

- supported local paths no longer need legacy variable names:
  `DRIVE_E2E_S2S_TOKEN` is sufficient for `Makefile` E2E targets and
  `run_env_e2e.sh`
- temporary transition support remains for local users/scripts that still
  export both legacy names with the same value
- ad hoc raw `docker compose` invocations outside Make/wrapper still do not
  resolve the canonical name by themselves and therefore remain outside the
  supported local contract
