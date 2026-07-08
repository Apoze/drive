# PLANS_catchup_commits.md — Upstream catch-up (ultra safe)
Repo: `Apoze/drive` (fork) catching up with upstream `suitenumerique/drive`

## Purpose
Bring the fork back up-to-date (behind -> 0) without breaking Apoze’s solution by integrating missing upstream commits in small, validated batches.

Important completion rule:
- The goal is not only "no more actionable upstream commits".
- GitHub's `behind` value is ancestry-based, not content-based. Manual or
  fork-aware ports can integrate the product change while GitHub still shows the
  fork as behind.
- Completion requires both:
  - every actionable upstream commit through the audited target is recorded in
    the ledger as applied, redundant, skipped, or explicitly deferred
  - the audited upstream target is made an ancestor of the fork branch through
    an approved final ancestry-sync operation
- If content is integrated but the audited target is not an ancestor, a final
  ancestry sync remains mandatory before publication.
- If upstream advanced after the last audited checkpoint, audit those commits
  first or explicitly choose and report a narrower ancestry-sync target.

## Non-negotiable rules
Source of truth: `AGENTS.md` (read and follow strictly).
- Never leak secrets/tokens/headers/cookies/signed URLs; mask with `***`.
- Storage rules (no local paths, streaming/bounded ops) apply to any code touched.
- Viewer routing rules must remain intact (archive allowlists; text viewer eligibility via `/items/<id>/text/`; frontend must not spam `/text/`).
- Security: mount archive extract remains fail-closed and provider-agnostic.
- WOPI PutFile must stream and never use `request.body`.
- Playwright: stabilize via locators/web-first assertions (no sleeps); traces on first retry.

## MountProvider parity rule for functional improvements
- If an upstream/fork change is a **real user-visible file capability
  improvement**, do not assume the fork can stop at the regular
  item/object-storage path only.
- Default fork expectation:
  - provide equivalent MountProvider support too when it is safe/capable
  - otherwise gate/degrade it explicitly through capabilities
- An upstream S3/object-storage-first implementation may still be executed
  first **only if** PREP concludes that MountProvider parity can follow
  immediately and cleanly as a separate fork-only lot.
- In that case, the overall feature lot is **not DONE** after the upstream
  batch alone; completion requires:
  - the immediate MountProvider parity follow-up,
  - or an explicit orchestrator/user decision to defer parity knowingly.
- The orchestrator must therefore treat "feature green for regular items only"
  as insufficient completion when this rule applies.

## Upstream is FETCH-ONLY (absolute)
- Allowed: `git fetch upstream ...`
- Forbidden: any push/PR/merge/commit to `upstream` (`suitenumerique/drive`).

## Artifacts workspace (source of truth)
All catch-up artifacts MUST be organized under:
- `tmp/GetToBehind0TaskTemp/`

Canonical meta files:
- `tmp/GetToBehind0TaskTemp/00_meta/index.md`
- `tmp/GetToBehind0TaskTemp/00_meta/ledger.tsv`
- `tmp/GetToBehind0TaskTemp/00_meta/missing_list.txt`
- `tmp/GetToBehind0TaskTemp/00_meta/missing_head40.txt`
- `tmp/GetToBehind0TaskTemp/00_meta/hotspots_paths.md`
- `tmp/GetToBehind0TaskTemp/00_meta/validation_matrix.md`

## Workflow modes
### Mode A — PREP ONLY (default; no code changes)
Allowed:
- Create a local-only working branch.
- Fetch remotes.
- Inspect commits/diffs and classify risk/hotspots.
- Generate PREP artifacts (classification.tsv, proposal_batches.md, decisions_needed.md).
Not allowed:
- `git cherry-pick` (even with `--no-commit`) unless explicitly authorized.
- Any commit/push/PR.

### Mode B — EXECUTE (requires explicit “GO” from the user)
Hard gates:
- Worktree must be clean before applying any batch (`git status --porcelain=v1` empty).
- Upstream remains fetch-only.
- Batch commit must be upstream-only; any fixes must be a separate fork-only commit after the batch.
- Decision-required hotspots: if a conflict touches UX/capability contract hotspots (Driver/StandardDriver, ExplorerTree/Actions, routing/breadcrumbs core, translations/i18n), STOP and write a decision report before continuing.
- Do not treat "effective divergence only" or "acceptable residuals" as done if
  GitHub would still show the fork behind `upstream/main`.
- Do not use an ancestry-sync merge for unaudited upstream commits. An
  ancestry-sync target is valid only when every upstream commit through that
  target is covered by the ledger.

### Final ancestry sync (local fork only)

When all commits through an audited upstream target are accounted for and
validation is green, record ancestry with a local no-content merge:

```bash
git merge -s ours --no-ff --no-commit <audited-upstream-target>
```

Required before committing:

- verify the index and worktree content are unchanged relative to the first
  parent
- verify no upstream tree content was copied by the merge
- record the audited upstream target SHA in the commit message and artifacts
- record before/after `git rev-list --left-right --count` values

Required after committing:

- `git diff HEAD^1..HEAD` must be empty except for merge metadata
- `git rev-list --left-right --count HEAD...<audited-upstream-target>` must
  have right side `0`
- if the target is not latest `upstream/main`, also report
  `HEAD...upstream/main` and the deferred right-side count

This operation is never allowed to push, PR, publish, or write to
`https://github.com/suitenumerique/drive.git`.

### Mode B orchestration / dev-agent autonomy
When Mode B is executed through an orchestrator + separate Codex "dev"
conversation, use this default rule:
- The orchestrator must provide a strong prompt:
  - current branch / SHA context
  - invariants to preserve
  - forbidden actions
  - commit separation rules
  - validation targets
  - reporting contract
- But the orchestrator should **not** force the dev agent to stop after every
  intermediate validation failure.
- Default expectation:
  - a Mode B execution prompt should target completion of the **current batch**
    or **current validation lot**
  - not merely investigation of the very next blocker
- In other words, when the scope is still safe and in-family, the dev agent is
  expected to keep going until the batch is green, not bounce back after each
  newly exposed failure.
- The dev agent is expected to continue autonomously through multiple
  corrective iterations **within the same run** while all of the following stay
  true:
  - the first current blocker is outside upstream-only application logic
  - the blocker is an E2E / validation / frontend stabilization issue
  - the fix is minimal and safe
  - each corrective stabilization can remain a separate fork-only commit
- After each successful corrective stabilization:
  - create a separate fork-only commit
  - rerun the required validation
  - continue if the next first blocker is still in the allowed scope above
- During such a run, the orchestrator should only expect a return when:
  - the batch is `DONE`
  - or a true hard-stop condition is reached
- A newly exposed non-hotspot test failure inside the same validation family is
  **not** by itself a hard-stop condition.
- Stop only when:
  - validation becomes green
  - or the current batch is complete and can be reported as `DONE`
  - or the first remaining blocker becomes out-of-scope
  - or the root cause is ambiguous
  - or a mandatory STOP rule elsewhere in this file applies
- The final execution report for such a chained run must include, for each new
  fork-only fix:
  - failing symptom
  - chosen root cause
  - files changed
  - targeted validation result
  - resulting full-gate outcome
- During such chained validation work, test changes must never be used as a
  bypass for real product bugs.
- Preferred order:
  1) fix the product/helper/runtime cause when the app behavior is wrong
  2) change tests only when the evidence shows the app behavior is already
     correct and the test/helper/fixture is the real defect
- Forbidden:
  - weakening assertions just to get green
  - removing scenario coverage for the exposed regression
  - changing expected outcomes to match a behavior that is known to be wrong

Artifacts per batch MUST follow:
- `tmp/GetToBehind0TaskTemp/batches/<BATCH_ID>/`
  - `00_preflight/`
  - `01_selection/` (selected_commits.txt, impact.md)
  - `02_apply/`
  - `03_validate/`
  - `04_report/` (exec_report.md, decision_report.md if needed)

Final ancestry reports must include remote identities, audited upstream target,
ledger coverage, no-content proof, and before/after divergence counts.

After each batch, update:
- `tmp/GetToBehind0TaskTemp/00_meta/ledger.tsv`
- `tmp/GetToBehind0TaskTemp/00_meta/index.md`

## Pre-flight checklist (run every time)
1) Clean worktree:
- `git status --porcelain=v1 -b` must be clean.

2) Remotes and fetch:
- Ensure `origin` (fork) and `upstream` (suitenumerique) exist.
- `git fetch origin --prune`
- `git fetch upstream --prune --tags`

2b) Upstream fetch-only safety (required)
- `git remote -v` must show `upstream ... (push) DISABLE` (or `no_push`).
  - If not: `git remote set-url --push upstream DISABLE`
- `git config --get remote.pushDefault` must be `origin` (set it if needed).
- Local `pre-push` hook must exist and refuse pushes to `upstream` / `suitenumerique/drive` (hook is local-only, never committed).

3) Record baseline SHAs (for the final report):
- `git rev-parse HEAD`
- `git rev-parse origin/main upstream/main`
- `git merge-base upstream/main origin/main`

4) Refresh missing upstream list (do NOT assume a fixed count)
- Divergence counts:
  - `git rev-list --left-right --count upstream/main...HEAD > tmp/GetToBehind0TaskTemp/00_meta/divergence_counts_upstream_vs_head.txt`
  - `git rev-list --left-right --count upstream/main...origin/main > tmp/GetToBehind0TaskTemp/00_meta/divergence_counts_upstream_vs_originmain.txt`
- Missing list from current HEAD (source of truth for planning):
  - `git rev-list --reverse HEAD..upstream/main > tmp/GetToBehind0TaskTemp/00_meta/missing_list.txt`
- Readable head list (first 40):
  - `head -n 40 tmp/GetToBehind0TaskTemp/00_meta/missing_list.txt | while read -r sha; do git show -s --date=short --format="%H %ad %s" "$sha"; done > tmp/GetToBehind0TaskTemp/00_meta/missing_head40.txt`

5) Impact review (required in Mode B)
Before applying any batch, write an impact note:
- For each commit in the batch: touched files + current fork behavior + expected change + regression risks + mitigation plan.
- Output (canonical):
  - `tmp/GetToBehind0TaskTemp/batches/<BATCH_ID>/01_selection/impact.md`
  - `tmp/GetToBehind0TaskTemp/batches/<BATCH_ID>/01_selection/selected_commits.txt`

## Conflict handling rules
### Decision-required hotspots (STOP)
If any conflict touches:
- Driver/StandardDriver
- ExplorerTree/Actions
- routing/breadcrumbs core
- translations/i18n
Then:
- STOP resolution
- Write `decision_report.md` and ask the user to choose
- Do NOT run `git cherry-pick --continue`

### Safe-file auto-resolve (do NOT STOP)
These files are high-likelihood overlap but do not require UX decisions:

A) CHANGELOG.md conflict
- Goal: keep BOTH sides' entries (union merge), remove conflict markers, keep line length <= 80 chars (except link-only lines).
Steps:
1) Save both sides for evidence:
   - `git show :2:CHANGELOG.md > <batch>/02_apply/CHANGELOG_ours.md`
   - `git show :3:CHANGELOG.md > <batch>/02_apply/CHANGELOG_theirs.md`
2) Edit `CHANGELOG.md` to include both sets of entries, then remove all conflict markers.
3) Validate no markers remain:
   - `grep -n '<<<<<<<\|=======\|>>>>>>>' CHANGELOG.md` must return nothing.
4) Stage + continue:
   - `git add CHANGELOG.md`
   - `git cherry-pick --continue`

B) AGENTS.md conflict
- Goal: OURS wins (fork-controlled contracts); keep THEIRS as evidence only.
Steps:
1) Save THEIRS:
   - `git show :3:AGENTS.md > <batch>/02_apply/AGENTS_theirs.md || true`
2) Keep OURS:
   - `git checkout --ours AGENTS.md`
   - `git add AGENTS.md`
3) Continue:
   - `git cherry-pick --continue`


C) Dockerfile conflict (analysis-first; NOT a safe auto-merge)
Dockerfile changes can impact base images, installed libs, build stages, runtime behavior, and security.
When Dockerfile is unmerged (UU Dockerfile), do NOT default to "OURS wholesale".

Steps (mandatory):
1) Capture evidence:
   - `git show :2:Dockerfile > <batch>/02_apply/Dockerfile_ours`
   - `git show :3:Dockerfile > <batch>/02_apply/Dockerfile_theirs`
   - `diff -u <batch>/02_apply/Dockerfile_ours <batch>/02_apply/Dockerfile_theirs > <batch>/02_apply/Dockerfile_ours_vs_theirs.diff || true`
   - Save upstream intent (for the current SHA being cherry-picked):
     - `git show --stat --name-status <sha> > <batch>/02_apply/upstream_<sha>_stat.txt`
     - `git show <sha> -- Dockerfile > <batch>/02_apply/upstream_<sha>_dockerfile.patch || true`

2) Analyze and classify changes (write `<batch>/02_apply/dockerfile_conflict_analysis.md`):
   - FROM / ARG / image tag changes (base images, stage images)
   - RUN install changes (apt/apk/pip/node libs, OS packages)
   - COPY/ADD changes (configs, mime.types, certs, entrypoints)
   - USER / permissions changes
   - ENV / build args / ports changes

   For each category: describe WHAT changed and WHY it likely changed (based on the upstream patch + local context).

3) Look-ahead (future necessity):
   - Search remaining missing commits for Dockerfile touches (best-effort):
     - `grep -RIn "Dockerfile" tmp/GetToBehind0TaskTemp/prep/*/missing_all_name_status.md > <batch>/02_apply/future_dockerfile_touches.txt || true`
   - If future commits touch Dockerfile, note whether taking THEIRS now might reduce future conflicts.

4) Decision rule:
   - Auto-resolve is allowed ONLY if changes are minimal and clearly scoped (e.g., ONLY adding a custom mime.types COPY/ADD line + related file),
     with NO base image bumps, NO new packages, NO stage refactors, NO entrypoint/USER/env changes.
     In that case: keep OURS baseline and apply only the minimal required hunk(s) from THEIRS.
   - Otherwise: STOP and write `decision_report.md` (OURS vs THEIRS vs HYBRID) because Dockerfile changes can have broad impact.

5) After resolution:
   - Ensure no conflict markers remain.
   - `git add Dockerfile` (and any new files introduced by the commit)
   - `git cherry-pick --continue`



### Any other non-hotspot conflict (excluding Dockerfile)
- Resolve conservatively, preserving fork invariants, then:
  - `git add -A`
  - `git cherry-pick --continue`
- If uncertain: `git cherry-pick --abort` and STOP with a report.

## Validation levels (risk-based)
Use validation levels defined in:
- `tmp/GetToBehind0TaskTemp/00_meta/validation_matrix.md`

Levels:
- L0: fast gates (lint/format/typecheck)
- L1: targeted unit/integration tests (backend and/or frontend) + L0
- L2: E2E smoke (single browser) when supported + L1
- L3: deterministic full E2E matrix (chromium + webkit + firefox) + L1:
  - from scratch: `bash run_env_e2e.sh --from-scratch`
  - on an existing E2E stack: `bash run_env_e2e.sh --reuse`

Rule:
- Required level for a batch is the MAX level over all touched files (by pattern),
  then escalate to L3 for any hotspot or user-flow change.
- Best practice during normal implementation is to stay on L0/L1 first.
- Reserve the full from-scratch L3 pass mainly for pre-PR validation, or for explicit
  end-to-end confidence checks after major user-flow work.
- Prefer unit/integration tests in the `ENV_OVERRIDE=e2e` environment when relevant,
  unless the user explicitly asks to validate on the LAN/local environment.

## Batches (dynamic)
Batches are derived from the current missing list during PREP and recorded in:
- `tmp/GetToBehind0TaskTemp/prep/prep_run_YYYYMMDD_HHMM/proposal_batches.md`
- `tmp/GetToBehind0TaskTemp/00_meta/index.md`
- `tmp/GetToBehind0TaskTemp/00_meta/ledger.tsv`

Do not maintain static batch commit lists inside `PLANS_catchup_commits.md`.

## Publication completion rule
- A catch-up cycle is complete only when both are true:
  - there are no remaining upstream commits that still need action
  - GitHub would show the fork `behind=0` versus `upstream/main`
- If residual SHAs are all classified as already integrated / redundant /
  acceptable but they are not yet ancestors of the publication branch, perform a
  final ancestry sync before publishing.
- That final ancestry sync may be a pure ancestry merge with no tree change if
  the content was already integrated earlier through batches or hybrid
  resolutions.
