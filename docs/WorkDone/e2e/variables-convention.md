# Convention de variables (noms + defaults)

Objectif: une configuration unique des tests E2E qui fonctionne:
- en **local** (stack dev déjà up)
- en **CI** (stack up dans le job)
- sans changer le câblage dev existant

---

## Variables recommandées (`E2E_*`)

### Origins (source de vérité)

- `E2E_BASE_URL`
  - **Default**: `http://192.168.10.123:3000`
  - **Rôle**: URL UI que Playwright ouvre.
  - **Note repo**: en environnement LAN, on vise l’UI via l’IP LAN (pas `localhost`) pour éviter les redirections/callbacks vers la loopback du client.

- `E2E_API_ORIGIN`
  - **Default**: `http://192.168.10.123:8071`
  - **Rôle**: origine API utilisée par les helpers de tests (calls directs).

- `E2E_EDGE_ORIGIN`
  - **Default**: `http://192.168.10.123:8083`
  - **Rôle**: origine edge/nginx (media `/media/*`, previews, etc.) si un test en a besoin explicitement.

### Mode d’exécution

- `E2E_EXTERNAL_WEB`
  - **Default**: `0`
  - **Rôle**: si `1`, Playwright n’essaie pas de démarrer un serveur (pas de `yarn dev` via `webServer.command`).

### Mode réseau (HOST vs COMPOSE)

> Objectif : rendre explicite comment le conteneur Playwright résout UI/API/Edge.
> Voir aussi la table : `./local-vs-ci.md`.

- `E2E_NETWORK_MODE`
  - **Default**: `host`
  - **Valeurs**:
    - `compose` : stack joignable via DNS Compose (`frontend-dev`, `app-dev`, `nginx`) ; recommandé pour CI et pour éviter `host.docker.internal`.
    - `host` : stack joignable via ports host / IP LAN (ex: `http://192.168.10.123:*`).

### Proxys (pour préserver `localhost:*` dans un conteneur)

But : garder des origins `http://localhost:*` dans le navigateur même quand la stack est jointe via DNS Compose.

Exemples d’upstreams :
- UI upstream : `http://frontend-dev:3000`
- API upstream : `http://app-dev:8000`
- Edge upstream : `http://nginx:8083`

### Auth / comptes de test (éviter d’écrire des secrets dans le repo)

- `E2E_TEST_USER_EMAIL`
  - **Default**: `e2e@example.com` (à adapter)
  - **Rôle**: email utilisé par les helpers d’auth E2E.

- `E2E_TEST_USER_PASSWORD`
  - **Default**: vide
  - **Rôle**: uniquement si certains tests passent par un login UI Keycloak.
  - **CI**: fournir via secret CI (ne jamais l’imprimer).

### Playwright / CI

- `CI`
  - **Default**: `0`
  - **Rôle**: active le mode CI (retries, `forbidOnly`, etc. selon votre config Playwright).

---

## Variables existantes (optionnelles / héritées)

- `PORT`
  - **Rôle**: port UI si vous gardez un fallback `http://localhost:${PORT}`.
  - **Reco**: `E2E_BASE_URL` doit primer sur `PORT`.

- `PLAYWRIGHT_BROWSERS_PATH`
  - **Rôle**: utile si vous voulez persister/cacher l’installation des navigateurs.
  - **Avec l’image officielle Playwright**: souvent non nécessaire.

---

## E2E maintenance (clear DB / fixtures)

Pour exécuter les E2E depuis un conteneur Playwright **sans accès Docker-in-Docker** (pas de `docker compose exec`), on préfère des endpoints E2E backend protégés par un token “server-to-server”.

- `E2E_S2S_TOKEN`
  - **Default**: vide
  - **Rôle**: si défini, les helpers E2E peuvent appeler :
    - `POST /api/v1.0/e2e/clear-db/`
    - `POST /api/v1.0/e2e/run-fixture/`
  - **Note**: côté backend, la liste des tokens acceptés est `SERVER_TO_SERVER_API_TOKENS`.

---

## Yarn install reproductible (docs only)

Le repo frontend indique `packageManager: yarn@1.22.22` (Yarn Classic).

Recommandations (selon la version Yarn) :
- Yarn v1 : `yarn install --frozen-lockfile --non-interactive`
- Yarn v2/v3/v4 : `yarn install --immutable` (optionnel : `--immutable-cache`)

Référence : https://yarnpkg.com/cli/install
