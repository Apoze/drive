# E2E Optimization Follow-Up Implementation Todo

This document is the execution companion for:

- [plan.md](./plan.md)

It is ordered for safe implementation, not by subsystem ownership.

Execution note (2026-03-15):

- Phase 0 baseline freeze and Phase 1 implementation reached the mandatory
  stop point; measured evidence lives in
  [execution/current-status.md](./execution/current-status.md) and
  [execution/checkpoints/phase-01.md](./execution/checkpoints/phase-01.md).

Rule:

- keep the one-stack model as the default mental model
- do not reopen stack multiplication as the primary strategy
- do not raise workers in CI before local env/token cleanup is done
- do not open sharding until the decision gate is measured

## Phase 0 — Baseline freeze and measurement harness

Goal:

- freeze the real starting point before changing any runtime contract

Files to inspect and update:

- [docs/e2e-optimization-followup/plan.md](/root/Apoze/drive/docs/e2e-optimization-followup/plan.md)
- [docs/e2e-optimization-followup/implementation-todo.md](/root/Apoze/drive/docs/e2e-optimization-followup/implementation-todo.md)
- [Makefile](/root/Apoze/drive/Makefile)
- [run_env_e2e.sh](/root/Apoze/drive/run_env_e2e.sh)
- [drive-frontend.yml](/root/Apoze/drive/.github/workflows/drive-frontend.yml)

Actions:

- freeze the exact current commands for:
  - local benchmark
  - full Chromium on reused stack
  - full from scratch
  - CI PR
  - CI browser matrix
- record current observed durations before changes
- keep the existing representative benchmark batch unchanged

Acceptance:

- baseline commands and baseline durations are documented
- no behavior changes yet

## Phase 1 — Canonical S2S token contract

Goal:

- remove the committed token and replace it with a clean runtime contract

Files to update:

- [run_env_e2e.sh](/root/Apoze/drive/run_env_e2e.sh)
- [Makefile](/root/Apoze/drive/Makefile)
- [docs/env_freeze_report.md](/root/Apoze/drive/docs/env_freeze_report.md)
- [docs/e2e-optimization-followup/plan.md](/root/Apoze/drive/docs/e2e-optimization-followup/plan.md)
- [docs/e2e-optimization-followup/implementation-todo.md](/root/Apoze/drive/docs/e2e-optimization-followup/implementation-todo.md)

Changes:

- define `DRIVE_E2E_S2S_TOKEN` as the only supported local input
- derive:
  - `DJANGO_SERVER_TO_SERVER_API_TOKENS`
  - `E2E_S2S_TOKEN`
- remove the hardcoded base64 token from the wrapper
- add one shared make/shell resolution path so all relevant targets use the
  same token logic
- fail early with a clear actionable message when the token contract is missing
  or inconsistent

Compatibility behavior:

- allow one transition case only:
  `DJANGO_SERVER_TO_SERVER_API_TOKENS` and `E2E_S2S_TOKEN` both present and
  equal
- any other partial state fails

Validation:

- `bash -n run_env_e2e.sh`
- `make -n bootstrap-e2e`
- `make -n run-tests-e2e-full`
- one targeted E2E command with the canonical token exported
- one failure-path check with token intentionally absent

Exit criteria:

- no committed token remains
- local usage can be explained with one exported variable
- bootstrap and test entrypoints fail early when misconfigured

Mandatory checkpoint:

- stop after this phase and record whether any existing local workflow still
  depends on the old variable names

## Phase 2 — Local command surface cleanup

Goal:

- make the local one-stack flows explicit before promoting workers

Files to update:

- [Makefile](/root/Apoze/drive/Makefile)
- [run_env_e2e.sh](/root/Apoze/drive/run_env_e2e.sh)
- [docs/WorkDone/e2e/local-vs-ci.md](/root/Apoze/drive/docs/WorkDone/e2e/local-vs-ci.md)
- [docs/e2e-optimization-followup/plan.md](/root/Apoze/drive/docs/e2e-optimization-followup/plan.md)

Changes:

- keep `run_env_e2e.sh` CLI unchanged:
  - `--from-scratch`
  - `--reuse`
- add an explicit make target for local full Chromium on an existing E2E stack
- keep the existing benchmark target and make it the canonical speed reference
- ensure all local targets pass `PLAYWRIGHT_WORKERS` consistently

Recommended targets after this phase:

- `run-tests-e2e-full`
- `run-tests-e2e-full-chromium`
- `run-tests-e2e-benchmark-local`
- `run-tests-e2e-from-scratch`

Validation:

- `make -n` for all four targets
- one real targeted Chromium run on an existing stack

Exit criteria:

- local one-stack commands are explicit
- no user needs to improvise a Chromium-only full command

## Phase 3 — Local worker promotion experiment

Goal:

- determine whether the safe local default can move from `1` to `4`

Files to update:

- [playwright.config.ts](/root/Apoze/drive/src/frontend/apps/e2e/playwright.config.ts)
- [Makefile](/root/Apoze/drive/Makefile)
- [run_env_e2e.sh](/root/Apoze/drive/run_env_e2e.sh)
- [docs/e2e-optimization-followup/plan.md](/root/Apoze/drive/docs/e2e-optimization-followup/plan.md)

Changes:

- do not change CI behavior yet
- run the promotion gates exactly as specified in `plan.md`
- if `workers=4` passes all gates, promote the local default to `4`
- keep `6` opt-in unless it passes the stricter gate

Required validation matrix:

- benchmark batch:
  - `workers=1`
  - `workers=4`
  - `workers=6`
- full Chromium on reused stack:
  - `workers=4` twice
- full Chromium from scratch:
  - `workers=4` once
- full three-browser from scratch:
  - existing stable path once

Decision rule:

- if `4` is clean, set local default to `4`
- if `4` is not clean, keep `1` and document why
- do not promote `6` unless all stricter gates pass

Mandatory checkpoint:

- stop after this phase with the measured durations, pass/fail results, RAM
  peak, and chosen default

## Phase 4 — CI workflow efficiency without changing worker count

Goal:

- reduce wasted CI time and artifacts without changing test semantics

Files to update:

- [drive-frontend.yml](/root/Apoze/drive/.github/workflows/drive-frontend.yml)
- [Makefile](/root/Apoze/drive/Makefile)
- [docs/e2e-optimization-followup/plan.md](/root/Apoze/drive/docs/e2e-optimization-followup/plan.md)

Changes:

- add workflow `concurrency`:
  - one PR-scoped group:
    `frontend-pr-${{ github.event.pull_request.number }}`
- enable `cancel-in-progress: true` for PRs
- set matrix `fail-fast: false` for compatibility runs
- upload Playwright HTML report and raw `test-results/` on failure or
  cancellation only
- leave browser selection unchanged
- leave worker count unchanged

Validation:

- YAML parse
- local `actionlint`
- `make -n run-tests-e2e-ci-pr`
- `make -n run-tests-e2e-ci-browser E2E_BROWSER=chromium`
- one branch PR run if implementation reaches that point

Exit criteria:

- PR reruns cancel obsolete earlier runs
- compat matrix keeps all browser signals
- artifact policy is lighter and explicit

## Phase 5 — Chromium PR CI worker experiment

Goal:

- determine whether PR Chromium can safely move from `workers=1` to `2`

Files to update:

- [drive-frontend.yml](/root/Apoze/drive/.github/workflows/drive-frontend.yml)
- [Makefile](/root/Apoze/drive/Makefile)
- [playwright.config.ts](/root/Apoze/drive/src/frontend/apps/e2e/playwright.config.ts)
- [docs/e2e-optimization-followup/plan.md](/root/Apoze/drive/docs/e2e-optimization-followup/plan.md)

Changes:

- add a non-default CI experiment path for Chromium with `workers=2`
- do not change the default PR path until measurement is complete
- use `workflow_dispatch` for the experiment, not normal PR runs

Validation:

- run the Chromium PR-equivalent job `5` times at `workers=2`
- compare wall time vs `workers=1`
- watch for:
  - flakes
  - OOM
  - bootstrap instability
  - artifact regressions

Decision rule:

- promote PR Chromium to `workers=2` only if:
  - `5/5` green
  - runtime gain is at least `15%`
- otherwise keep PR CI at `1`

Mandatory checkpoint:

- stop after this phase with measured CI data and the explicit keep/promote
  decision

## Phase 6 — Sharding decision spike

Goal:

- decide with evidence whether sharding is still worth doing

Precondition:

- only run this phase if the runtime thresholds from `plan.md` are still too
  high after Phases 3 through 5

Files to update if needed:

- [playwright.config.ts](/root/Apoze/drive/src/frontend/apps/e2e/playwright.config.ts)
- [Makefile](/root/Apoze/drive/Makefile)
- [drive-frontend.yml](/root/Apoze/drive/.github/workflows/drive-frontend.yml)
- [loopback-proxies.js](/root/Apoze/drive/src/frontend/apps/e2e/scripts/loopback-proxies.js)
- [compose.yaml](/root/Apoze/drive/compose.yaml)
- [docs/e2e-optimization-followup/plan.md](/root/Apoze/drive/docs/e2e-optimization-followup/plan.md)

Constraints:

- Chromium only
- `2` shards only
- `workers=1`
- `fullyParallel: false`
- blob report + report merge
- file-level sharding only
- no change to the standard local wrapper CLI

Validation:

- one local spike or one CI manual run
- compare total wall time and stability to the best non-sharded path

Decision rule:

- keep sharding only if gain is at least `20%` and stability stays green
- otherwise close the shard spike and keep it out of the standard contract

Mandatory checkpoint:

- stop after this phase with an explicit adopt/reject decision

## Phase 7 — Transitional fallback disposition

Goal:

- decide what happens to the old multi-stack fallback after the optimization
  initiative

Files to inspect and potentially update:

- [Makefile](/root/Apoze/drive/Makefile)
- [compose.yaml](/root/Apoze/drive/compose.yaml)
- [loopback-proxies.js](/root/Apoze/drive/src/frontend/apps/e2e/scripts/loopback-proxies.js)
- [docs/e2e-optimization-followup/plan.md](/root/Apoze/drive/docs/e2e-optimization-followup/plan.md)

Decision:

- if sharding was rejected:
  - document the fallback as removable debt
  - do not remove it in the same PR unless the diff stays small and obvious
- if sharding was accepted:
  - document the fallback as shard-only infra
  - keep it but remove any implication that it is the normal path

Validation:

- one smoke of the fallback path if it is retained
- docs review for consistency

Exit criteria:

- fallback status is explicit:
  - retained for shard-only use
  - or slated for removal in a later cleanup

## Final deliverables

At the end of the initiative, produce:

- updated runtime docs for the canonical E2E token contract
- updated local/CI command docs
- explicit decision on local default workers
- explicit decision on CI Chromium workers
- explicit decision on sharding
- explicit status for the multi-stack fallback

The final outcome must let another engineer answer these questions without
guessing:

- what token do I export locally?
- what is the default local E2E path?
- what is the CI worker policy?
- is sharding part of the standard contract?
- is the multi-stack fallback still alive, and why?
