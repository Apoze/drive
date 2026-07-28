# Env config freeze report (LAN dev vs E2E CI-like)

## A) Executive summary

- Recommended model: **two overrides only** — `ENV_OVERRIDE=local` (LAN dev) and `ENV_OVERRIDE=e2e` (E2E CI-like, used both locally and in GitHub CI).
- **Do not split** `e2e-local` vs `e2e-github` unless behavior diverges; today the only difference is **token source**.
- Versioned env files **must not contain real tokens**; keep token vars empty and inject at runtime (shell / gitignored file / CI secrets).
- `/api/v1.0/e2e/*` requires a **matching token pair**:
  - backend accepts `DJANGO_SERVER_TO_SERVER_API_TOKENS`
  - Playwright sends `E2E_S2S_TOKEN`
- LAN risk: any browser-facing URL must not be `localhost` (breaks remote LAN clients).
- E2E risk: determinism depends on forcing **127.0.0.1 origins** + loopback proxies + clean DB.
- Docker Compose precedence reminder: **shell env overrides `env_file`** for container environment variables.
- Django reminder: `CSRF_TRUSTED_ORIGINS` validates the `Origin` header and **requires a scheme** (`http://...` / `https://...`).
- Playwright CI debugging: `trace: on-first-retry` is enabled in `src/frontend/apps/e2e/playwright.config.ts`.

## B) Env A — LAN dev (ENV_OVERRIDE=local)

### 1) Purpose + browser-facing base URLs

- Purpose: dev stack reachable from the LAN (remote browsers hit the host IP).
- Browser-facing URLs (expected):
  - UI: `http://192.168.10.123:3000`
  - API: `http://192.168.10.123:8071`
  - Edge (nginx): `http://192.168.10.123:8083`
  - S3 gateway (presigned PUT): `http://192.168.10.123:9000`

### 2) Files loaded (env_file chain) + precedence

- Compose `env_file` chain for backend containers is:
  - `env.d/development/common` (versioned baseline)
  - `env.d/development/common.${ENV_OVERRIDE}` (override; `common.local` in LAN)
  - `env.d/development/postgresql` + `env.d/development/postgresql.${ENV_OVERRIDE}`
- Postgres data dir is mounted from `./data/postgresql.${ENV_OVERRIDE}`.
- Precedence: **shell env > env_file** (Compose merges env, shell wins).

### 3) MUST overrides in `env.d/development/common.local` (names only)

File status in this checkout: `env.d/development/common.local` is **present** (gitignored).

Required LAN overrides status (names only; no values):

- `LOGIN_REDIRECT_URL`: SET
- `LOGIN_REDIRECT_URL_FAILURE`: SET
- `LOGOUT_REDIRECT_URL`: SET
- `OIDC_OP_AUTHORIZATION_ENDPOINT`: SET
- `OIDC_OP_URL`: SET
- `OIDC_REDIRECT_ALLOWED_HOSTS`: SET
- `MEDIA_BASE_URL`: SET
- `AWS_S3_DOMAIN_REPLACE`: SET
- `CSRF_TRUSTED_ORIGINS`: SET (scheme required)
- `DRIVE_PUBLIC_URL`: should be set to the LAN UI origin for public share URLs.

Other notable keys currently present in `common.local` (names only): `MOUNTS_REGISTRY` (SET), `SMB_PASSWORD` (SET; secret — keep out of git), plus OIDC backchannel endpoints (`OIDC_OP_TOKEN_ENDPOINT`, `OIDC_OP_USER_ENDPOINT`, `OIDC_OP_JWKS_ENDPOINT`, `OIDC_OP_INTROSPECTION_ENDPOINT`, `OIDC_OP_LOGOUT_ENDPOINT`).

### 4) LAN smoke E2E (non CI-like)

- Ce mode n’a pas pour but d’être deterministe (pas de reset DB).
- Le mode deterministe = ENV_OVERRIDE=e2e + run-tests-e2e-from-scratch.
- You can run the Playwright runner against the already-running LAN stack via `make run-tests-e2e ...`.
- If your E2E specs use fixtures/clear-db endpoints, you must provide the matching token pair:
  - backend: `DJANGO_SERVER_TO_SERVER_API_TOKENS` (via shell env or `common.local`)
  - runner: `E2E_S2S_TOKEN` (via shell env passed into `make run-tests-e2e`)
- If missing: `/api/v1.0/e2e/*` calls are refused → fixtures/clearDb steps fail or become no-ops → E2E becomes flaky/non-deterministic.

### 5) Quick validation checklist (LAN)

1) Ensure `ENV_OVERRIDE=local` and `env.d/development/common.local` exists (gitignored).
2) Open UI from another LAN machine: `http://192.168.10.123:3000` (no `localhost` redirects).
3) Login flow completes (no “invalid redirect_uri”).
4) Upload a small file (presigned PUT hits `http://192.168.10.123:9000`, not `localhost`).
5) API returns item URLs using `MEDIA_BASE_URL=http://192.168.10.123:8083`.

## C) Env B — E2E local CI-like (ENV_OVERRIDE=e2e)

### 1) Purpose

- Purpose: reproduce GitHub CI locally (fresh DB, fixed origins, deterministic runner wiring).

### 2) Origins forced + loopback proxies mapping (includes :9000)

`make run-tests-e2e-from-scratch` forces:

- `E2E_NETWORK_MODE=manual`
- `E2E_BASE_URL=http://127.0.0.1:3000`
- `E2E_API_ORIGIN=http://127.0.0.1:8071`
- `E2E_EDGE_ORIGIN=http://127.0.0.1:8083`

In `make run-tests-e2e`, when `E2E_NETWORK_MODE` is `manual` (or `compose`), it starts loopback proxies (`src/frontend/apps/e2e/scripts/loopback-proxies.js`) that bind to `127.0.0.1` and proxy:

- `127.0.0.1:3000` → `frontend-dev:3000`
- `127.0.0.1:8071` → `app-dev:8000`
- `127.0.0.1:8083` → `nginx:8083`
- `127.0.0.1:9000` → `seaweedfs-s3:8333`

### 3) OIDC model

- E2E override file `env.d/development/common.e2e` switches OIDC “frontchannel” endpoints to Compose hostnames (e.g. `http://nginx:8083/...`) so the Playwright browser (inside the runner container) can reach Keycloak on the Compose network.
- Redirect URLs are set to `http://127.0.0.1:3000` to match forced E2E origins.

### 4) Tokens (local supply; never commit)

Local E2E tooling now resolves one canonical input:

- `DRIVE_E2E_S2S_TOKEN`

Derived variables stay implementation details:

- `DJANGO_SERVER_TO_SERVER_API_TOKENS`
- `E2E_S2S_TOKEN`

Supported local contract:

- export `DRIVE_E2E_S2S_TOKEN=***`
- `Makefile` and `run_env_e2e.sh` derive both legacy variables from it
- if the canonical variable is missing, E2E entrypoints fail early with a
  clear actionable message

Temporary compatibility only:

- if `DRIVE_E2E_S2S_TOKEN` is absent but
  `DJANGO_SERVER_TO_SERVER_API_TOKENS=***` and `E2E_S2S_TOKEN=***` are both
  present and equal, local tooling still accepts them for one transition
  window
- any partial or mixed state fails fast

Because Compose env precedence is `shell > env_file`, the resolved token
overrides the empty tracked defaults.

### 5) Quick validation checklist (E2E local)

1) `export DRIVE_E2E_S2S_TOKEN=***`
2) `make bootstrap-e2e`
3) `make run-tests-e2e-from-scratch -- --project chromium`
4) Confirm base URLs in runner are `127.0.0.1:*` and that loopback proxy health checks pass (includes `127.0.0.1:9000`).
5) Confirm `/api/v1.0/e2e/*` endpoints succeed (fixtures/clear-db).

### 6) Known watch-outs (monitor)

- `MEDIA_BASE_URL` and `AWS_S3_DOMAIN_REPLACE` default to `http://localhost:...` (from `env.d/development/common`).
  - This is intended to work in E2E because the runner container can reach its own loopback proxy via `localhost`.
  - Risk: `localhost` may resolve to IPv6 `::1` in some contexts while the proxy binds `127.0.0.1`. If any flake appears, prefer forcing `127.0.0.1` consistently (to validate later).

## D) Env C — GitHub CI (ENV_OVERRIDE=e2e)

### 1) Same as Env B (confirm)

- GitHub CI uses the same Make targets:
  - `make bootstrap-e2e`
  - `make run-tests-e2e-from-scratch -- --project ${{ matrix.browser }}`
- Same forced `127.0.0.1` origins + loopback proxies model.

### 2) Differences

- Token source is CI secret injection (workflow `Frontend Workflow`, job `test-e2e`):
  - `DJANGO_SERVER_TO_SERVER_API_TOKENS: ${{ secrets.DRIVE_E2E_S2S_TOKEN }}`
  - `E2E_S2S_TOKEN: ${{ secrets.DRIVE_E2E_S2S_TOKEN }}`
- Local canonical name remains `DRIVE_E2E_S2S_TOKEN`; CI still exports the
  two derived names directly today.
- CI-only flags:
  - `CI=1` influences retries/workers in Playwright config.
- Mount E2E enablement: keep default **off** in CI unless explicitly desired later.

### 3) Quick validation checklist (CI)

1) Ensure repository secret `DRIVE_E2E_S2S_TOKEN` exists and is non-empty.
2) Open workflow run artifacts to confirm Playwright reports are uploaded for each browser.
3) If failures occur, use Playwright trace (on-first-retry) from artifacts.

## E) Variables matrix (freeze)

| Variable | LAN dev (`ENV_OVERRIDE=local`) | E2E local (`ENV_OVERRIDE=e2e`) | GitHub CI (`ENV_OVERRIDE=e2e`) |
|---|---|---|---|
| `ENV_OVERRIDE` | shell env (required) — selects `common.local` + `postgresql.local` | Make (`bootstrap-e2e` / `run-tests-e2e-from-scratch` export) (required) | same as E2E local (required) |
| `MEDIA_BASE_URL` | `common.local` (required) — item/media URLs host | `common` baseline (`localhost`) (required) — works via loopback proxy | same as E2E local |
| `AWS_S3_DOMAIN_REPLACE` | `common.local` (required) — presigned PUT host | `common` baseline (`localhost`) (required) — works via loopback proxy `:9000` | same as E2E local |
| `CSRF_TRUSTED_ORIGINS` | `common.local` (required) — allow LAN Origins (scheme required) | env/shell (optional) — add if CSRF errors appear | env/CI (optional) |
| `OIDC_OP_AUTHORIZATION_ENDPOINT` | `common.local` (required) — browser-reachable IdP auth endpoint | `common.e2e` (required) — Compose hostname (`nginx`) | same as E2E local |
| `OIDC_OP_URL` | `common.local` (required) — issuer base used by app | `common.e2e` (required) — Compose hostname (`nginx`) | same as E2E local |
| `OIDC_REDIRECT_ALLOWED_HOSTS` | `common.local` (required) — allow LAN UI/Edge origins | `common.e2e` (required) — allow `127.0.0.1:*` (+ localhost list) | same as E2E local |
| `LOGIN_REDIRECT_URL` / `*_FAILURE` / `LOGOUT_REDIRECT_URL` | `common.local` (required) — LAN UI origin | `common.e2e` (required) — `127.0.0.1:3000` | same as E2E local |
| `DRIVE_PUBLIC_URL` | `common.local` or shell — LAN UI origin for public share URLs | `common.e2e` — `http://127.0.0.1:3000` | same as E2E local |
| `DRIVE_E2E_S2S_TOKEN` | shell (optional) — canonical local E2E token input | shell export (required for supported local E2E contract) | optional future alias; not used by workflow today |
| `E2E_BASE_URL` | Make default (optional) — LAN UI origin | Make forced (required) — `http://127.0.0.1:3000` | same as E2E local |
| `E2E_API_ORIGIN` | Make default (optional) — LAN API origin | Make forced (required) — `http://127.0.0.1:8071` | same as E2E local |
| `E2E_EDGE_ORIGIN` | Make default (optional) — LAN Edge origin | Make forced (required) — `http://127.0.0.1:8083` | same as E2E local |
| `E2E_NETWORK_MODE` | Make default `host` (optional) | Make forced `manual` (required) — loopback proxies | same as E2E local |
| `DJANGO_SERVER_TO_SERVER_API_TOKENS` | shell or `common.local` (optional) — enable `/api/v1.0/e2e/*` | derived by Make/wrapper from `DRIVE_E2E_S2S_TOKEN`; legacy compatibility only if manually exported with `E2E_S2S_TOKEN` and equal | CI secret (required) — `${{ secrets.DRIVE_E2E_S2S_TOKEN }}` |
| `E2E_S2S_TOKEN` | shell (optional) — runner auth to `/api/v1.0/e2e/*` | derived by Make/wrapper from `DRIVE_E2E_S2S_TOKEN`; legacy compatibility only if manually exported with `DJANGO_SERVER_TO_SERVER_API_TOKENS` and equal | CI secret (required) — `${{ secrets.DRIVE_E2E_S2S_TOKEN }}` |
| `E2E_ENABLE_MOUNTS` | (intended) shell/Make (optional) — enable mounts E2E specs | currently **not injected by Make** (defaults off) | currently **not injected by workflow/Make** (defaults off) |

## F) To implement later (no changes now)

- Make wrappers (names only):
  - `run-lan` (sets `ENV_OVERRIDE=local` and starts LAN dev stack)
  - `run-e2e-ci-like` (sets `ENV_OVERRIDE=e2e` + forced `E2E_*` to `127.0.0.1` and runs from-scratch E2E)
- Token injection path (high-level):
  - Supported local mechanism: `export DRIVE_E2E_S2S_TOKEN=***`.
  - Temporary transition mechanism only:
    `export DJANGO_SERVER_TO_SERVER_API_TOKENS=***; export E2E_S2S_TOKEN=***`.
  - CI mechanism: map `secrets.DRIVE_E2E_S2S_TOKEN` to both vars (already done in workflow).
- Injecting `E2E_ENABLE_MOUNTS` into Playwright container:
  - Add a single `-e E2E_ENABLE_MOUNTS="$(E2E_ENABLE_MOUNTS)"` pass-through in `make run-tests-e2e` (and optionally a default in compose for LAN only).

## G) Open questions / items to validate

- LAN mode bootstrap: do we want `make run` to fail fast with a clear error if `env.d/development/common.local` is missing/incomplete (instead of failing later via redirects/CORS/CSRF)? (Validate later; no change now.)
- CSRF in E2E: if any E2E CSRF failures appear, confirm whether `CSRF_TRUSTED_ORIGINS` needs to be set explicitly in E2E (small test: run one E2E login + upload flow and check for 403 CSRF).
- `localhost` vs `127.0.0.1` in E2E: if any intermittent failures appear, test binding loopback proxies to `localhost` or forcing all URLs to `127.0.0.1` consistently.
