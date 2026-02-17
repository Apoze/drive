# Plan E2E “production-ready” — conteneur Playwright officiel + **COMPOSE (défaut)** / **HOST (fallback)**

Objectif : exécuter Playwright dans un conteneur dédié **sans installer de navigateurs dans `frontend-dev`** (Alpine), tout en gardant un comportement identique (origins/auth/media) entre local et CI.

---

## 0) État actuel du repo (réalité)

Ce qui existe déjà :
- `src/frontend/apps/e2e/package.json` : `@playwright/test` **pinné** à `1.56.1`.
- `src/frontend/apps/e2e/playwright.config.ts` :
  - `baseURL` piloté par `E2E_BASE_URL` (fallback `http://192.168.10.123:${PORT}`)
  - en mode `E2E_EXTERNAL_WEB=1` + `E2E_NETWORK_MODE=compose`, lancement de proxies loopback pour préserver `localhost:*` (usage CI)
  - artifacts : `./playwright-report/` (HTML reporter) et `./test-results/` (`outputDir`), avec `trace/video` sur retry et `screenshot` sur échec.
- `Makefile` :
  - `make run-tests-e2e` exécute les E2E via le conteneur Playwright **contre une stack déjà up**
  - `make run-tests-e2e-from-scratch` stop/reset/restart la stack E2E puis exécute les tests

Contrainte importante :
- `frontend-dev` est basé sur **Alpine** (`node:22-alpine`) → les navigateurs Playwright “officiels” ne sont pas supportés sur musl/Alpine (cf. section “Alpine” dans la doc Playwright Docker).

---

## 1) Réseau : deux modes documentés + choix par défaut

### 1.1 Choix par défaut (local LAN) : **HOST** (origins `192.168.10.123:*`)

Pourquoi ce choix :
- En accès LAN, `localhost` pointe vers *la machine du client* (pas vers le serveur Drive) : les redirects/login peuvent casser si le backend renvoie des URLs `localhost:*`.
- Pointer Playwright sur les endpoints LAN (`192.168.10.123:*`) reflète le comportement réel des utilisateurs sur le réseau.

Principe :
- Le conteneur Playwright vise directement :
  - UI: `http://192.168.10.123:3000`
  - API: `http://192.168.10.123:8071`
  - Edge: `http://192.168.10.123:8083`

Env typique :

```bash
E2E_NETWORK_MODE=host
E2E_EXTERNAL_WEB=1
E2E_BASE_URL=http://192.168.10.123:3000
E2E_API_ORIGIN=http://192.168.10.123:8071
E2E_EDGE_ORIGIN=http://192.168.10.123:8083
```

### 1.2 Mode CI recommandé : **COMPOSE + loopback proxies** (origins `localhost:*`)

Principe : en CI, on garde des origins `http://localhost:*` dans le navigateur via des proxies loopback dans le conteneur Playwright, tout en joignant la stack via DNS Compose (`frontend-dev`, `app-dev`, `nginx`).

Env typique :

```bash
E2E_NETWORK_MODE=compose
E2E_EXTERNAL_WEB=1
E2E_BASE_URL=http://localhost:3000
E2E_API_ORIGIN=http://localhost:8071
E2E_EDGE_ORIGIN=http://localhost:8083
```

Note :
- Ce mode est celui utilisé par `make run-tests-e2e-from-scratch` (CI).
- `make run-tests-e2e-from-scratch` démarre la stack avec `ENV_OVERRIDE=e2e` (endpoints OIDC/media en `localhost:*`).
  - Si vous l’exécutez sur votre machine **et** que vous voulez ensuite retrouver une stack dev LAN (endpoints `192.168.10.123:*`), recréez le backend en `local` :

```bash
ENV_OVERRIDE=local docker compose up -d --force-recreate app-dev nginx celery-dev celery-beat-dev
```

---

## 2) Image Playwright : **pinning obligatoire**

Règle : la version de l’image Docker Playwright doit **matcher** `@playwright/test`, sinon Playwright ne retrouve pas les navigateurs.

Dans ce repo :
- `@playwright/test` = `1.56.1` (`src/frontend/apps/e2e/package.json`)
- image recommandée : `mcr.microsoft.com/playwright:v1.56.1-jammy`

Références :
- Doc Playwright Docker : https://playwright.dev/docs/docker
- Tags Docker Hub : https://hub.docker.com/r/microsoft/playwright

---

## 3) Alpine / musl : caveat (clarification)

Playwright ne supporte pas officiellement les builds navigateurs sur Alpine/musl ; l’approche recommandée est :
- exécuter les E2E dans l’image officielle Ubuntu-based Playwright (`...-jammy`).

Référence : https://playwright.dev/docs/docker (section Alpine not supported).

---

## 4) Artifacts / reporting CI

Le repo écrit :
- HTML report : `src/frontend/apps/e2e/playwright-report/`
- Résultats bruts + traces/vidéos/screenshots : `src/frontend/apps/e2e/test-results/`
  - traces typiques : `src/frontend/apps/e2e/test-results/**/trace.zip`

Recommandations CI :
- Uploader `playwright-report/` et `test-results/` en artifacts du job (et garder les traces sur échec).

Références :
- CI intro : https://playwright.dev/docs/ci-intro
- Trace viewer : https://playwright.dev/docs/trace-viewer

---

## 5) Maintenance (clear DB / fixtures) sans Docker-in-Docker

Pour permettre `clearDb()` / fixtures depuis le conteneur Playwright, le backend expose des endpoints E2E protégés par token “server-to-server”.

Variables :
- `SERVER_TO_SERVER_API_TOKENS` (backend)
- `E2E_S2S_TOKEN` (runner)

Endpoints :
- `POST /api/v1.0/e2e/clear-db/`
- `POST /api/v1.0/e2e/run-fixture/` (allowlist)
