# Table “Local vs CI” (valeurs exactes) — **HOST (LAN, défaut)** + **COMPOSE (CI)**

Objectif : rendre explicite, *copier-coller*, les variables E2E (UI/API/Edge) pour exécuter Playwright :
- en local
- en CI
- **dans un conteneur Playwright dédié** (`e2e-playwright`)

Ports “host” standards du repo (quand ils sont publiés) :
- UI: `:3000` (`frontend-dev`)
- API: `:8071` (`app-dev`)
- Edge: `:8083` (`nginx`)

---

## Décision : mode réseau par défaut = **HOST (LAN)**

**Mode HOST** = le conteneur Playwright consomme la stack via les endpoints publiés (ici l’IP LAN), sans dépendre de `localhost`.

En local LAN, le défaut est :
- `http://192.168.10.123:3000` (UI)
- `http://192.168.10.123:8071` (API)
- `http://192.168.10.123:8083` (Edge)

Référence détaillée : `./playwright-plan.md`.

Pour CI (Docker-in-Docker / runners), on privilégie **COMPOSE + loopback proxies** avec des origins `http://localhost:*` (voir section 2).

---

## 1) Scénarios — Mode **HOST (LAN, défaut)**

> Ce mode vise la stack dev LAN directement depuis le conteneur Playwright.

| Scénario | Où tourne Playwright ? | `E2E_EXTERNAL_WEB` | `E2E_BASE_URL` | `E2E_API_ORIGIN` | `E2E_EDGE_ORIGIN` | `CI` |
|---|---|---:|---|---|---|---:|
| Local (LAN) | Dans `e2e-playwright` | `1` | `http://192.168.10.123:3000` | `http://192.168.10.123:8071` | `http://192.168.10.123:8083` | `0` |

---

## 2) Scénarios — Mode **COMPOSE (CI)**

> IMPORTANT : ces valeurs supposent que `localhost:3000/8071/8083` existent **dans le conteneur Playwright** (via proxies loopback).
> Upstreams typiques des proxies : `frontend-dev:3000`, `app-dev:8000`, `nginx:8083`.

| Scénario | Où tourne Playwright ? | `E2E_EXTERNAL_WEB` | `E2E_BASE_URL` | `E2E_API_ORIGIN` | `E2E_EDGE_ORIGIN` | `CI` |
|---|---|---:|---|---|---|---:|
| CI — GitHub Actions (Linux) | Dans `e2e-playwright` | `1` | `http://localhost:3000` | `http://localhost:8071` | `http://localhost:8083` | `1` |
| CI — Runner self-hosted | Dans `e2e-playwright` | `1` | `http://localhost:3000` | `http://localhost:8071` | `http://localhost:8083` | `1` |

Option (si vous n’utilisez **pas** de loopback proxies) : “COMPOSE direct”.

| Variante | `E2E_BASE_URL` | `E2E_API_ORIGIN` | `E2E_EDGE_ORIGIN` |
|---|---|---|---|
| COMPOSE direct (DNS Compose dans le navigateur) | `http://frontend-dev:3000` | `http://app-dev:8000` | `http://nginx:8083` |

⚠️ Cette variante est **non défaut** car elle change `window.location.hostname` (ex: `frontend-dev`) et casse facilement :
- les calculs d’origin API côté UI (souvent `${hostname}:8071`)
- des allowlists existantes (Keycloak redirect URIs et CORS media) qui whitelistent `localhost:3000`

---

## 3) Fallback : `host.docker.internal:*` (si l’IP LAN n’est pas stable)

Linux : `host.docker.internal` n’existe pas toujours ; il faut généralement mapper vers `host-gateway`.

Références :
- Docker `host-gateway` : https://docs.docker.com/reference/cli/dockerd/ (host-gateway)
- Pattern Linux `host.docker.internal` : https://stackoverflow.com/questions/48546124/what-is-the-linux-equivalent-of-host-docker-internal

| Scénario | Où tourne Playwright ? | `E2E_EXTERNAL_WEB` | `E2E_BASE_URL` | `E2E_API_ORIGIN` | `E2E_EDGE_ORIGIN` | `CI` |
|---|---|---:|---|---|---|---:|
| Local | Dans `e2e-playwright` | `1` | `http://host.docker.internal:3000` | `http://host.docker.internal:8071` | `http://host.docker.internal:8083` | `0` |
| CI — GitHub Actions (Linux) | Dans `e2e-playwright` | `1` | `http://host.docker.internal:3000` | `http://host.docker.internal:8071` | `http://host.docker.internal:8083` | `1` |

⚠️ Risques/points bloquants connus (repo actuel) :
- **Keycloak** : le realm dev whitelist `http://localhost:3000/*` et `http://192.168.10.123:3000`, pas `http://host.docker.internal:3000/*` → login E2E susceptible d’échouer tant que ce n’est pas ajouté.
- **Media / CORS** (edge `:8083`) : les endpoints `/media/*` whitelistent `localhost:3000`/`192.168.10.123:3000`. `host.docker.internal:3000` devra être ajouté si les tests touchent aux previews/media.
- **Uploads S3 (presigned PUT)** : en dev, le backend signe souvent sur `http://localhost:9000` (via `AWS_S3_DOMAIN_REPLACE`). Depuis un conteneur, `localhost:9000` pointe vers le conteneur → il faut soit ajuster `AWS_S3_DOMAIN_REPLACE` (ex: `http://host.docker.internal:9000`), soit garder un proxy loopback `localhost:9000`.

## 4) Variables d’auth (si vos tests font un vrai login UI)

Ces variables ne sont nécessaires **que** si certains tests passent par l’UI Keycloak avec mot de passe.

| Variable | Local | CI GitHub-hosted | CI self-hosted |
|---|---|---|---|
| `E2E_TEST_USER_EMAIL` | une valeur de test (ex: `e2e@example.com`) | idem | idem |
| `E2E_TEST_USER_PASSWORD` | optionnel | via secret CI (ne jamais logger) | via secret runner (ne jamais logger) |

Si vos tests utilisent l’endpoint E2E backend de login (ex: `POST /api/v1.0/e2e/user-auth/`), vous pouvez souvent éviter le mot de passe.

---

## 5) Checklist CI (GitHub Actions vs self-hosted)

### GitHub Actions (runner GitHub-hosted)
1) Démarrer la stack (compose) dans le job:
   - `docker compose up -d ...` (au minimum `app-dev`, `nginx`, `frontend-dev` + deps)
2) Attendre la disponibilité des endpoints upstream (selon le mode):
   - Mode COMPOSE: `http://frontend-dev:3000`, `http://app-dev:8000`, `http://nginx:8083`
   - Mode HOST (LAN): `http://192.168.10.123:3000`, `http://192.168.10.123:8071`, `http://192.168.10.123:8083`
3) Lancer Playwright via `docker compose run --rm e2e-playwright ...` avec les env de la table (COMPOSE ou HOST).
4) Uploader les artifacts Playwright (`playwright-report/`, `test-results/`).

### Runner self-hosted
Même logique, avec 2 points d’attention:
- éviter les conflits de ports si la machine héberge déjà des services sur `3000/8071/8083`
- s’assurer que Docker est récent (support `host-gateway`) et que le runner a les droits pour lancer compose

---

## 6) Où configurer ces variables dans GitHub Actions

Dans un workflow GitHub Actions, vous fixez généralement ces variables:
- soit au niveau `env:` du job
- soit au niveau des secrets (uniquement pour mots de passe)

Exemple (indicatif) d’`env:`:

```yaml
env:
  E2E_EXTERNAL_WEB: "1"
  # Défaut (COMPOSE + loopback proxies) :
  E2E_BASE_URL: "http://localhost:3000"
  E2E_API_ORIGIN: "http://localhost:8071"
  E2E_EDGE_ORIGIN: "http://localhost:8083"
  CI: "1"
```

Pour HOST (fallback), remplacer les origins par `http://host.docker.internal:*`.

---

## 7) Note importante (LAN)

Si vous lancez `make run-tests-e2e-from-scratch` sur votre machine, la stack backend est démarrée avec `ENV_OVERRIDE=e2e` (donc des endpoints `localhost:*`).

Pour revenir à une stack dev accessible sur le LAN (`192.168.10.123:*`) sans tout re-bootstrap :

```bash
ENV_OVERRIDE=local docker compose up -d --force-recreate app-dev nginx celery-dev celery-beat-dev
```
