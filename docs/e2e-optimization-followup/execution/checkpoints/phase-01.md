# Phase 01 Checkpoint

- phase id:
  `phase-01`
- date/time UTC:
  `2026-03-15`
- branch:
  `codex/e2e-optimization-followup-phase1`
- objective:
  finish Phase 0 baseline freeze and Phase 1 canonical local token cleanup,
  then stop for orchestrator review

## What Changed

- added shared token resolver:
  `bin/resolve_e2e_s2s_token.sh`
- removed the committed token from `run_env_e2e.sh`
- made `Makefile` E2E entrypoints derive
  `DJANGO_SERVER_TO_SERVER_API_TOKENS` and `E2E_S2S_TOKEN` from
  `DRIVE_E2E_S2S_TOKEN`
- added early failure on missing, partial, or inconsistent token states
- kept one transition path only:
  both legacy variables present and equal
- updated `docs/env_freeze_report.md` for the canonical local input
- updated execution docs with the frozen Phase 0 baseline and Phase 1 evidence

## What Was Validated

- `bash -n run_env_e2e.sh`
- `DRIVE_E2E_S2S_TOKEN=*** make -n bootstrap-e2e`
- `DRIVE_E2E_S2S_TOKEN=*** make -n run-tests-e2e-full`
- `DRIVE_E2E_S2S_TOKEN=*** make run-backend-e2e`
- `DOCKER_USER="$(id -u):$(id -g)" ENV_OVERRIDE=e2e docker compose up -d frontend-dev`
- `DRIVE_E2E_S2S_TOKEN=*** make run-tests-e2e-readiness`
  - result:
    `1 passed (17.1s)`
- `DJANGO_SERVER_TO_SERVER_API_TOKENS=*** E2E_S2S_TOKEN=*** make -n run-tests-e2e-full`
  - result:
    transition compatibility still works
- `env -u DRIVE_E2E_S2S_TOKEN -u DJANGO_SERVER_TO_SERVER_API_TOKENS -u E2E_S2S_TOKEN make -n run-tests-e2e-full`
  - result:
    fails early with clear guidance
- `env -u DRIVE_E2E_S2S_TOKEN -u DJANGO_SERVER_TO_SERVER_API_TOKENS -u E2E_S2S_TOKEN bash run_env_e2e.sh --reuse`
  - result:
    fails early with the same guidance
- `docker compose ps`
  - result:
    healthy stack after the validation wave

## Token And Env Contract State

- canonical supported local input:
  `DRIVE_E2E_S2S_TOKEN`
- derived implementation details:
  `DJANGO_SERVER_TO_SERVER_API_TOKENS` and `E2E_S2S_TOKEN`
- wrapper CLI unchanged:
  `bash run_env_e2e.sh --from-scratch`
  `bash run_env_e2e.sh --reuse`
- no committed token remains in the wrapper
- CI source wiring unchanged in this phase

## Impacts On Existing Local Usages

- supported local Make/wrapper flows now need only:
  `export DRIVE_E2E_S2S_TOKEN=***`
- users/scripts that still export both legacy variables with the same value are
  still accepted temporarily
- partial legacy states are now rejected earlier than before
- direct raw `docker compose` usage outside Make/wrapper still depends on the
  derived legacy names because Compose itself does not resolve the canonical
  input

## Residual Risks

- some ad hoc local habits may still rely on exporting legacy names manually
- raw `docker compose` commands remain outside the supported contract unless
  they also derive/export the legacy names
- Phase 1 deliberately did not touch local workers, CI workers, sharding, or
  the fallback multi-stack surface

## What Phase 2 Would Touch

- `Makefile`
- `run_env_e2e.sh`
- `docs/WorkDone/e2e/local-vs-ci.md`
- `docs/e2e-optimization-followup/plan.md`

Phase 2 should make the one-stack local command surface explicit, especially a
dedicated full-Chromium reused-stack target.

## Recommendation

- `continue`
