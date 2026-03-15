# Phase 05 GitHub Ready Checkpoint

- phase id:
  `phase-05-github-ready`
- date/time UTC:
  `2026-03-15`
- branch:
  `codex/e2e-optimization-followup-phase1`
- objective:
  strengthen the local/static validation of the prepared Phase 5 workflow,
  produce an executable Git/GitHub handoff, then stop before any live GitHub
  run

## What Was Reverified Or Adjusted

- installed `actionlint` temporarily under:
  `tmp/actionlint/actionlint`
  for real local workflow linting instead of YAML-only review
- extended the `workflow_dispatch` selector:
  `phase5_ci_experiment`
  so the future GitHub benchmark can choose either:
  - `chromium-pr-workers1-control`
  - `chromium-pr-workers2`
- added a workflow-dispatch-only control job:
  `test-e2e-pr-workers1-control`
- added an explicit Make entrypoint for that control path:
  `run-tests-e2e-ci-pr-workers1-control`
- kept the experimental job:
  `test-e2e-pr-workers2-experiment`
  unchanged in intent:
  it still uses
  `PLAYWRIGHT_WORKERS=2`
  plus
  `PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE=1`
- kept the normal PR job:
  `test-e2e-pr`
  unchanged at
  `workers=1`
- during refinement, `actionlint` caught one duplicated workflow job key; that
  defect was fixed before this checkpoint

## Actionlint Result

- tool:
  `tmp/actionlint/actionlint`
- version:
  `1.7.11`
- install mode:
  temporary download under `tmp/`, no repo pollution
- command:
  `tmp/actionlint/actionlint -color .github/workflows/drive-frontend.yml`
- result:
  passed with exit code `0`

## What Was Validated Locally

- `docker compose ps`
  - result:
    local stack healthy
- YAML parse on:
  `.github/workflows/drive-frontend.yml`
  via
  `python3` + `yaml.safe_load`
  - result:
    passed
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr`
  - result:
    normal PR path still resolves to `PLAYWRIGHT_WORKERS=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-browser E2E_BROWSER=chromium`
  - result:
    normal CI browser path still resolves to `PLAYWRIGHT_WORKERS=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr-workers1-control`
  - result:
    workflow-dispatch control path resolves to the same conservative Chromium
    PR flow at `PLAYWRIGHT_WORKERS=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-pr-workers2-experiment`
  - result:
    opt-in experiment resolves to:
    `PLAYWRIGHT_WORKERS=2`
    and
    `PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE=1`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-ci-browser-experiment E2E_BROWSER=chromium PLAYWRIGHT_EXPERIMENTAL_WORKERS=2`
  - result:
    generic opt-in browser experiment path resolves identically
- final static workflow audit:
  - control and experiment are `workflow_dispatch` only
  - normal PR Chromium path stays unchanged
  - compat matrix runs only when `phase5_ci_experiment=none`
  - control and experiment artifact names are distinct
  - all workflow job keys are unique

## Final Shape Of The GitHub Experimental Path

- workflow:
  `Frontend Workflow`
- trigger:
  `workflow_dispatch`
- selector:
  `phase5_ci_experiment`
- selector values now supported:
  - `none`
  - `chromium-pr-workers1-control`
  - `chromium-pr-workers2`
- control job:
  `test-e2e-pr-workers1-control`
  calling:
  `make run-tests-e2e-ci-pr-workers1-control`
  at effective
  `PLAYWRIGHT_WORKERS=1`
- experiment job:
  `test-e2e-pr-workers2-experiment`
  calling:
  `make run-tests-e2e-ci-pr-workers2-experiment`
  at effective
  `PLAYWRIGHT_WORKERS=2`
  with
  `PLAYWRIGHT_CI_ALLOW_WORKERS_OVERRIDE=1`
- unchanged default PR job:
  `test-e2e-pr`
  remains Chromium-only at `workers=1`
- unchanged standard manual compat behavior:
  when `phase5_ci_experiment=none`, the compat matrix stays the normal
  Chromium/WebKit/Firefox path

## Exact Runbook For Real Phase 5 Later

- prerequisites:
  - Git work must be explicitly authorized
  - the current branch must be pushed with this readiness handoff
  - GitHub secret `DRIVE_E2E_S2S_TOKEN` must be present
  - no new code changes should land between the control and experiment runs
- workflow to launch:
  `Frontend Workflow`
- runbook:
  1. Push the branch that contains this checkpoint and workflow wiring.
  2. Open GitHub Actions and manually run `Frontend Workflow`.
  3. Launch one control run with:
     `phase5_ci_experiment=chromium-pr-workers1-control`
  4. Launch one experiment run with:
     `phase5_ci_experiment=chromium-pr-workers2`
  5. Repeat until there are `5` completed experiment runs and `5` matched
     control runs on the same commit SHA.
  6. Prefer alternating runs in this order to reduce GitHub-hosted runner drift:
     control-1, experiment-1, control-2, experiment-2, control-3,
     experiment-3, control-4, experiment-4, control-5, experiment-5.
  7. Compare the PR-equivalent job durations, not the total workflow duration,
     because lint/unit/setup jobs are shared noise unrelated to the worker
     count.
  8. Do not change the normal PR path during this measurement window.

## Metrics To Collect During The 5 Runs

- for each of the `5` experiment runs and each matched control run, record:
  - workflow run URL or run id
  - commit SHA
  - selected `phase5_ci_experiment` value
  - final job conclusion
  - wall time of the PR-equivalent job only:
    `test-e2e-pr-workers1-control`
    or
    `test-e2e-pr-workers2-experiment`
  - step durations for:
    - `Start Docker services`
    - `Wait for Keycloak to be ready`
    - `Run ... e2e tests`
  - Playwright outcome:
    passes, failures, skips, retries, and any flake signature
  - infrastructure outcome:
    OOM, runner abort, bootstrap failure, or unexpected cancellation
  - artifact outcome on `failure()` or `cancelled()`:
    HTML report present, `test-results/` present, traces usable

## Keep Or Promote Decision Rule

- promote Chromium PR CI to `workers=2` only if:
  - the `5/5` experiment runs are green
  - no new flakes are observed
  - no OOM or bootstrap instability appears
  - failure/cancelled artifact behavior stays correct
  - the median PR-equivalent job wall time at `workers=2` is at least `15%`
    faster than the matched `workers=1` control median
- otherwise keep the default PR path at:
  `workers=1`

## Residual Risks

- no live GitHub run has happened yet in this phase, so the readiness result is
  still static/local only
- GitHub-hosted runner variance can still blur wall-time comparisons, which is
  why alternating control and experiment runs on the same SHA is recommended
- the protocol now compares identical `workflow_dispatch` surfaces, but it still
  does not prove that a later PR event will be free of incidental GitHub-side
  variance
- the control and experiment jobs share bootstrap/setup cost; a speedup smaller
  than the `15%` rule may be lost in job-level noise and must not be promoted

## Recommendation

- `ready for git-enabled phase-5 execution`
