# Git + GitHub CLI process (Apoze/drive)

Goal: when implementation/debugging is done and reviewed locally, execute this process end-to-end so the result is **tested**, **PR-ready**, and **merged** without breaking repo rules.

Scope: `git` + `gh` only. No product behavior changes.

## Non-negotiables

- 1 branch = 1 PR.
- No `rebase`, no `reset --hard`, no `cherry-pick`, no `force push`.
- No commits on `main` directly (PRs only).
- Never commit or print secrets/tokens/auth headers/signed URLs (mask as `***`).
- CI gates must pass on the PR:
  - `Main Workflow / lint-git`
  - `Main Workflow / check-changelog` (unless PR has `noChangeLog`)
  - `Main Workflow / lint-changelog`
  - `Frontend Workflow / test-e2e` (matrix: chromium, webkit, firefox)

## One-time repository setup (fork hygiene)

These are not PR gates, but can fail on `push` to `main` after merge in some repos/forks:

- **Update crowdin sources / synchronize-with-crowdin** (`.github/workflows/crowdin_upload.yml`): runs on `push` to `main`.
  - If you don’t want it, disable it once on the repo:
    - `gh workflow disable crowdin_upload.yml`
- **Docker Hub Workflow** (`.github/workflows/docker-hub.yml`): in upstream it’s guarded by `if: github.repository == 'suitenumerique/drive'`.
  - On forks it usually won’t run; confirm before relying on it.

## Verify CI rules (always do before pushing)

The repo is the source of truth for what CI enforces:

```bash
cat .gitlint
sed -n '1,200p' gitlint/gitlint_emoji.py
sed -n '1,140p' .github/workflows/drive.yml
sed -n '1,120p' CONTRIBUTING.md
```

Key enforced rules (current state):

- CI rejects any `fixup!` commit.
- CI rejects any `print(` introduced under `src/backend`.
- CI runs: `gitlint --commits origin/<base>..HEAD`
- CI requires `CHANGELOG.md` changed unless PR has label `noChangeLog`.
- CI rejects any `CHANGELOG.md` line with length `>= 80` (ignoring GitHub ref-link lines).

## PR content policy (split “upload fixes”)

If there are “upload fixes” that must ship in a separate PR:

1) Identify files that belong to the separate PR:

```bash
git diff --name-only origin/main...HEAD
```

2) Stash them (targeted):

```bash
git stash push -m "upload-fixes-wip" -- <path1> <path2> ...
git stash list | head
```

## End-to-end procedure (coding is finished)

### 0) Sanity: correct branch, clean state, correct upstream

```bash
git status --porcelain=v1
git branch --show-current
git remote -v

git fetch origin --prune
git merge-base --is-ancestor origin/main HEAD
```

### 1) Secrets hygiene (fail-fast)

Scan modified files for obvious secrets patterns (stop if anything is found):

```bash
files=$(git diff --name-only origin/main...HEAD)
rg -n "(BEGIN (RSA|OPENSSH) PRIVATE KEY|AKIA[0-9A-Z]{16}|xox[baprs]-|ghp_[A-Za-z0-9]{30,}|github_pat_|Bearer\\s+[A-Za-z0-9\\-\\._~\\+\\/]+=*|Authorization:\\s*Bearer)" -S $files || true
```

Check that tracked env files keep tokens empty (mask any value as `***` in output):

```bash
git diff -- env.d/development/common env.d/development/common.e2e
```

### 2) Changelog gate (must pass unless label `noChangeLog`)

Confirm `CHANGELOG.md` is modified:

```bash
git diff --name-only origin/main..HEAD | rg "^CHANGELOG\\.md$"
```

Confirm CI line length rule:

```bash
max_line_length=$(cat CHANGELOG.md | grep -Ev "^\\[.*\\]: https://github.com" | wc -L)
test "$max_line_length" -lt 80
```

Required: add 1 changelog line aligned with the PR scope and < 80 chars.

Template (edit later, add PR number once known):

- `- 🔧(backend) storage guidelines + mount hardening + wopi streaming #NNN`

### 3) lint-git gate (local equivalent)

```bash
! git log | rg "fixup!"
! git diff origin/main..HEAD -- src/backend | rg "print\\("
gitlint --commits origin/main..HEAD
```

### 4) Tests (must be green locally before push)

Backend:

```bash
make test-back
```

E2E CI-like (run the same “from scratch” target as CI, all 3 browsers):

```bash
export DJANGO_SERVER_TO_SERVER_API_TOKENS=*** E2E_S2S_TOKEN=*** CI=1

ENV_OVERRIDE=e2e make run-tests-e2e-from-scratch -- --project chromium
ENV_OVERRIDE=e2e make run-tests-e2e-from-scratch -- --project webkit
ENV_OVERRIDE=e2e make run-tests-e2e-from-scratch -- --project firefox
```

### 5) Commit(s) (must satisfy gitlint + DCO signoff)

Review, stage, commit:

```bash
git diff --stat origin/main...HEAD
git diff origin/main...HEAD

git add -A
git status --porcelain=v1

git commit --signoff
# (optional but recommended) sign commits: git commit -S --signoff
```

Commit message requirements (repo policy):

- Title must match: `<gitmoji>(<scope>) <subject>`
- Title must not contain `wip`
- Body must be present (non-empty)

### 6) Push (no force) + PR create/update

```bash
git push -u origin HEAD
```

Provide PR metadata (English, no secrets):

- `{PR_TITLE}`: concise, scope-aligned
- `{PR_BODY}`: purpose + summary + tests executed + risks/notes

Create PR (if none exists):

```bash
gh pr view --head "$(git branch --show-current)" --json number,url,state 2>/dev/null || true
gh pr create --base main --head "$(git branch --show-current)" --title "{PR_TITLE}" --body "{PR_BODY}"
```

### 7) Wait for PR checks + merge

```bash
gh pr checks --watch
```

Confirm allowed merge method(s) (avoid guessing):

```bash
gh repo view --json mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed
```

Merge without rewriting history:

```bash
# Prefer --merge if allowed, else --squash (never rebase-merge here).
gh pr merge --merge --delete-branch
```

### 8) Post-merge cleanup

```bash
git switch main
git pull --ff-only origin main
git branch -d <branch_name>
```

## Follow-up: PR for “upload fixes” (if stashed)

```bash
git switch -c <branch_upload_fixes>
git stash pop
```

Then re-run the same end-to-end procedure above.

