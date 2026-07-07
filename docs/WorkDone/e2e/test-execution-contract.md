# E2E Test Execution Contract

This document is the source of truth for how Playwright E2E tests are launched
in this repository.

It describes:
- the supported local E2E contract
- the supported CI contract
- the current worker policy
- what is standard vs non-standard

For detailed background, keep using:
- [playwright-plan.md](./playwright-plan.md)
- [local-vs-ci.md](./local-vs-ci.md)
- [variables-convention.md](./variables-convention.md)

## Official Origins And Hosts

Nothing changed in the supported origin split:

- LAN development mode (`ENV_OVERRIDE=local`) still uses the LAN host:
  - UI:
    `http://192.168.10.123:3000`
  - API:
    `http://192.168.10.123:8071`
  - Edge:
    `http://192.168.10.123:8083`
  - S3:
    `http://192.168.10.123:9000`
- CI-like local E2E mode (`ENV_OVERRIDE=e2e`) still uses loopback origins:
  - UI:
    `http://127.0.0.1:3000`
  - API:
    `http://127.0.0.1:8071`
  - Edge:
    `http://127.0.0.1:8083`
  - S3:
    `http://127.0.0.1:9000`

Rule:
- use LAN origins for the normal local dev stack
- use loopback origins for the standard E2E contract

## Standard Local E2E Contract

Use the CI-like local E2E environment:
- `ENV_OVERRIDE=e2e`
- loopback origins on `127.0.0.1`
- one stack
- default local worker count:
  `PLAYWRIGHT_WORKERS=4`

Canonical local token input:
- `DRIVE_E2E_S2S_TOKEN`

Preferred local source:
- gitignored file:
  `env.d/development/e2e.tokens.local`

Supported file content:
- `DRIVE_E2E_S2S_TOKEN=...`

Supported alternative:
- export `DRIVE_E2E_S2S_TOKEN` in the current shell session

Derived runtime variables are set automatically by the wrapper/Makefile:
- `DJANGO_SERVER_TO_SERVER_API_TOKENS`
- `E2E_S2S_TOKEN`

Official local entrypoints:
- full 3-browser confidence on the current E2E stack:
  `bash run_env_e2e.sh --reuse`
- full 3-browser confidence from scratch:
  `bash run_env_e2e.sh --from-scratch`

Proper explicit local E2E stack startup:
- provide the canonical token through the local gitignored file:
  `env.d/development/e2e.tokens.local`
- or export it in the current shell:
  `export DRIVE_E2E_S2S_TOKEN=***`
- bootstrap backend E2E:
  `make bootstrap-e2e`
- start the frontend against that stack:
  `make run-frontend-e2e`
- then run:
  - `bash run_env_e2e.sh --reuse`
  - or the targeted Make commands below

Important local behavior:
- if the token is not already exported, the resolver automatically reads:
  `env.d/development/e2e.tokens.local`
- `run_env_e2e.sh` keeps the public CLI limited to:
  - `--reuse`
  - `--from-scratch`
- it injects the CI-like loopback origins:
  - `http://127.0.0.1:3000`
  - `http://127.0.0.1:8071`
  - `http://127.0.0.1:8083`
  - `http://127.0.0.1:9000`
- it now defaults to:
  `PLAYWRIGHT_WORKERS=4`

After E2E before Mac-local QA:
- `bash run_env_e2e.sh --from-scratch` and the from-scratch Make targets leave
  the running app stack in `ENV_OVERRIDE=e2e`
- before requesting browser QA from the Mac-local Codex app, restore the LAN
  stack and validate the browser-facing auth redirect:
  `make qa-lan-ready`
- the preflight must show a sanitized `302 Location` whose origin is
  `http://192.168.10.123:8083`, not `http://nginx:8083`,
  `http://localhost:8083`, or `http://127.0.0.1:8083`
- for authenticated browser QA, also run `make qa-lan-authenticated-ready`;
  this validates the local/dev E2E browser bootstrap URL, creates deterministic
  dummy fixtures, and reports only fixture URLs plus `set-cookie: present`
- a `QA_REQUEST` for LAN browser work must include the preflight status, or
  explicitly mark the QA item pending because the preflight failed

Useful local Make targets:
- bootstrap backend E2E only:
  `make bootstrap-e2e`
- readiness only:
  `make run-tests-e2e-readiness`
- full 3-browser campaign on current E2E stack:
  `make run-tests-e2e-full`
- full Chromium only on current E2E stack:
  `make run-tests-e2e-full-chromium`
- representative local Chromium benchmark:
  `make run-tests-e2e-benchmark-local`
- full 3-browser campaign from scratch:
  `make run-tests-e2e-from-scratch`
- full Chromium only from scratch:
  `make run-tests-e2e-from-scratch-chromium`
- authenticated LAN browser QA bootstrap:
  `make qa-lan-authenticated-ready`

Expected local usage:
- normal implementation loop:
  - prefer targeted backend/unit tests first
  - use `make run-tests-e2e-full-chromium` or targeted `make run-tests-e2e`
    on an existing E2E stack when you need real user-flow coverage
- pre-PR confidence:
  - use `bash run_env_e2e.sh --from-scratch`

Catch-up validation cadence:
- Do not use the full three-browser L3 matrix as the default exit gate for
  every user-visible batch.
- Prefer this order: static/lint gates, targeted unit or backend tests,
  focused E2E for the changed workflow, then a scheduled L3 checkpoint.
- Run full L3 immediately only for broad runtime/dependency changes, shared
  navigation/auth/explorer-shell changes, preview/storage/WOPI/mount rewrites,
  or before publication.
- After one full L3 attempt, if the remaining failure is clearly outside the
  current batch, fix or record it with focused reproduction and reruns. Do not
  keep looping full L3 after every out-of-scope stabilization unless the
  stabilization touched shared helpers or product code broadly enough to justify
  a new full-matrix proof.
- When several adjacent lots all touch visible workflows, group the final full
  L3 as a checkpoint after the cluster when targeted gates are green.

## Standard CI Contract

CI E2E uses the same CI-like loopback contract, but stays conservative on
workers.

### Pull Requests

Workflow:
- [drive-frontend.yml](/root/Apoze/drive/.github/workflows/drive-frontend.yml)
  job `test-e2e-pr`

Policy:
- browser coverage:
  `chromium` only
- worker count:
  `PLAYWRIGHT_WORKERS=1`
- readiness:
  required

Operational shape:
- `make bootstrap-e2e`
- start `frontend-dev`
- run:
  `ENV_OVERRIDE=e2e make run-tests-e2e-ci-pr`

Reason:
- `workers=2` was measured and faster, but it introduced a new flaky
  signature, so PR CI stays at `1`

### Main And Workflow Dispatch

Workflow:
- [drive-frontend.yml](/root/Apoze/drive/.github/workflows/drive-frontend.yml)
  job `test-e2e-compat`

Policy:
- browser coverage:
  `chromium`, `webkit`, `firefox`
- worker count per browser job:
  `PLAYWRIGHT_WORKERS=1`
- matrix:
  `fail-fast: false`

Operational shape:
- bootstrap the E2E stack
- start `frontend-dev`
- run one browser job per matrix entry through:
  `ENV_OVERRIDE=e2e make run-tests-e2e-ci-browser E2E_BROWSER=<browser>`

### CI Experiments

These are not part of the standard contract:
- `run-tests-e2e-ci-pr-workers1-control`
- `run-tests-e2e-ci-pr-workers2-experiment`
- `run-tests-e2e-ci-browser-experiment`

They exist only for controlled benchmarking or follow-up investigations.

## Standard vs Non-Standard

Standard:
- local one-stack CI-like E2E
- local default:
  `PLAYWRIGHT_WORKERS=4`
- PR CI Chromium:
  `workers=1`
- `main` / `workflow_dispatch` browser matrix:
  `workers=1`

Non-standard:
- sharded Playwright runs
- the old multi-stack fallback
- ad-hoc direct Playwright invocations that bypass the wrapper/Make targets
- LAN-mode Playwright as the default path

Current policy:
- sharding is not part of the standard contract
- the multi-stack path is retained only as fallback / removable debt
- LAN mode is for explicit local scenarios only, not the normal E2E contract

## Quick Reference

Local reuse current E2E stack:
- `bash run_env_e2e.sh --reuse`

Local from scratch:
- `bash run_env_e2e.sh --from-scratch`

Local Chromium only:
- `make run-tests-e2e-full-chromium`

Local benchmark:
- `make run-tests-e2e-benchmark-local`

PR CI policy:
- Chromium only
- `workers=1`

Main / workflow_dispatch CI policy:
- Chromium + WebKit + Firefox
- `workers=1`
