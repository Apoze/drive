# Git / GitHub CLI — Template (1 branche, 1 PR) pour agents IA

Objectif : fournir une procédure **copier/coller** pour gérer `git` + GitHub CLI (`gh`) dans ce repo, avec un flux **sûr**, **idempotent**, et compatible avec les règles CI (gitlint / changelog / gates).

Docs connexes (à suivre aussi) :
- `docs/codex-agent-baseline.md`
- `docs/codex-review-cycle.md`
- `CONTRIBUTING.md`

---

## 0) Règles (non négociables)

- **1 seule branche de travail** (`{BRANCH_NAME}`) et **1 seul PR** associé.
- Interdit : créer une 2e branche locale (ex: `tmp/*`, `wip/*`, etc.).
- Interdit : `rebase`, `cherry-pick`, `reset --soft/--mixed/--hard`, `checkout -B`, suppression forcée de branche (`git branch -D`), `push --force*`.
- Si un “mauvais” commit est déjà poussé sur `{BRANCH_NAME}` : **STOP** et demander instruction (pas de rewrite).
- Pas de fuite : ne jamais afficher / copier des secrets (tokens, cookies, headers auth, URLs signées). Remplacer par `***`.

---

## Variables à remplir (au début)

- `{BASE_BRANCH}` : `main`
- `{BRANCH_NAME}` : ex. `chore/e2e-playwright-runner`
- `{PR_TITLE}` / `{PR_BODY}`

---

## 1) État initial (avant toute action)

```bash
git status --porcelain=v1
git branch --show-current
git log --oneline --decorate -n 10
git remote -v
```

Optionnel (GitHub) :

```bash
gh auth status
gh repo view --json nameWithOwner,url
```

---

## 2) Baseline propre (sans merge implicite)

```bash
git fetch origin --prune
git switch {BASE_BRANCH}
git pull --ff-only origin {BASE_BRANCH}
```

---

## 3) Branche unique (local + remote)

- Si déjà sur `{BRANCH_NAME}` : rester dessus.
- Sinon :

```bash
git switch -c {BRANCH_NAME}
```

Vérifier que la branche part bien de `{BASE_BRANCH}` :

```bash
git merge-base --is-ancestor origin/{BASE_BRANCH} HEAD
```

Si la branche diverge de `{BASE_BRANCH}` : **STOP**.

Après le premier push, vérifier l’upstream :

```bash
git rev-parse --abbrev-ref --symbolic-full-name @{u}
```

---

## 4) Scope check AVANT commit/push

```bash
git diff --stat origin/{BASE_BRANCH}...HEAD
git diff --name-only origin/{BASE_BRANCH}...HEAD
```

Si hors-scope : **STOP** (pas de “fix discret”).

---

## 5) Qualité AVANT premier push (commandes “officielles” du repo)

Minimum recommandé (dev) :

```bash
make lint
make frontend-lint
make test
```

Backend (options utiles) :

```bash
make test-back
make test-back-parallel
```

Tests unitaires frontend (Jest) :

```bash
docker compose run --rm -T -w /app/src/frontend/apps/drive node yarn test
```

E2E Playwright (runner Docker) :

- **Local LAN (défaut)** : utilise `http://192.168.10.123:*`

```bash
make run-tests-e2e -- --project chromium
```

⚠️ Statut actuel (repo) :
- Les E2E sont **skippés** pour le moment (en local et sur GitHub).
- Si besoin exceptionnel, le seul chemin à utiliser est `make run-tests-e2e` (ne pas utiliser d’autres variantes qui redémarrent la stack).

---

## 6) Commits (gitlint / CONTRIBUTING)

Format (obligatoire) :

```
<gitmoji>(type) titre en minuscules

body obligatoire (quoi/pourquoi), lignes <= 80 chars
```

Règles clés :
- pas d’espace entre l’emoji et `(` ; 1 espace après `)` ; pas de majuscules
- `git commit --signoff` obligatoire (`CONTRIBUTING.md`)
- pas de commit sans body
- éviter d’injecter des `\n` “littéraux” dans le message :
  - préférer plusieurs `-m` (1 titre, 1 body) ou un éditeur
  - respecter `lignes <= 80 chars` (sinon `lint-git` échoue)

---

## 7) Push (fast-forward only)

Premier push :

```bash
git push -u origin {BRANCH_NAME}
```

Ensuite :
- ajouter des commits conformes
- `git push` (jamais de force push)

---

## 8) PR unique (idempotent)

Avant de créer :

```bash
gh pr view --head {BRANCH_NAME} --json number,url,state 2>/dev/null || true
```

- Si PR existe : le réutiliser.
- Sinon :

```bash
gh pr create --base {BASE_BRANCH} --head {BRANCH_NAME} --title "{PR_TITLE}" --body "{PR_BODY}"
```

Changelog :
- **mettre à jour `CHANGELOG.md`** (sinon `check-changelog` échoue)
- le label `noChangeLog` peut exister dans le repo, mais ne pas supposer qu’il
  désactive le check `check-changelog`

Exemple :

```bash
gh pr edit --add-label noChangeLog
```

---

## 9) Checks (fail-fast)

```bash
gh pr checks --watch
```

Si échec :
- corriger, commit conforme, push
- si la correction nécessiterait rebase/reset/force : **STOP**

Note : ne pas attendre les checks explicitement “non-bloquants” (voir `docs/codex-agent-baseline.md`).

---

## 10) Mise à jour depuis main (sans rebase)

Si la branche devient en conflit :

```bash
git fetch origin
git merge origin/{BASE_BRANCH}
```

Résoudre, commit, push (pas de force push).

---

## 11) Merge + cleanup (sans commandes risquées)

Merge (si policy le permet) :

```bash
gh pr merge --squash --delete-branch
```

Si `--squash` est refusé par la policy : **STOP** et demander instruction.

Sync local :

```bash
git switch {BASE_BRANCH}
git pull --ff-only origin {BASE_BRANCH}
```

Suppression locale (non destructif) :

```bash
git branch -d {BRANCH_NAME}
```

Si refus “not fully merged” : ne pas forcer, signaler.
