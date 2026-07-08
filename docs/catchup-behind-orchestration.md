# Catch-Up Behind Orchestration

This document contains the long-form orchestration rules for catching the
Apoze fork back up to `suitenumerique/drive`.

It complements `AGENTS.md`, `PLANS_catchup_commits.md`, and
`docs/agent-thread-coordination-protocol.md`.

## Dedicated Threads

- Dev agent:
  `codex://threads/019f32a2-7ba5-7492-8446-abb1b058d929`
- Orchestrator agent:
  `codex://threads/019f329f-a5db-7003-b9cf-0d4ccdfc1589`
- Browser QA agent:
  `codex://threads/019f32af-aa7d-74e0-953c-0d980ae1e348`

Before restarting catch-up execution, test that the orchestrator can message
the dev thread and that the dev thread can message back.

The QA thread should also be tested when a browser/manual-vision validation lot
needs it, but QA reachability is best effort and non-blocking.

All thread-to-thread messages must use
`docs/agent-thread-coordination-protocol.md`.

## Roles

The orchestrator does not directly execute the catch-up implementation work
unless the user explicitly changes the operating model.

The orchestrator:

- verifies real Git state before planning
- writes one complete operational prompt at a time in `PROMPT.md`
- sends operational instructions directly to dev/QA threads when no user
  decision is needed
- treats each sent instruction as a handoff point and enters the matching
  waiting state instead of polling the recipient thread
- never asks the user to copy/paste prompts between agents
- inspects the dev return and repository state
- decides the next single step
- preserves fork invariants and catch-up safety gates

The dev agent:

- executes the prompt in `PROMPT.md`
- updates the required artifacts
- reports `DONE`, `BLOCKED`, or `NEEDS_DECISION`
- may request QA evidence directly for approved in-scope browser checks, while
  notifying the orchestrator with the same correlation id
- does not push, PR, or publish unless explicitly instructed

The QA agent:

- runs on the user's local macOS host in the Codex app
- has access to the Codex integrated browser, DevTools, screenshots, and other
  human-vision browser tooling when available
- is used for deeper visual/browser QA that the remote SSH orchestrator cannot
  perform directly
- receives focused QA prompts from the orchestrator
- reports evidence, screenshots, console/network observations, and clear
  pass/fail notes
- may report concrete failures directly to dev when no user decision is needed,
  while notifying the orchestrator with the same correlation id
- does not modify product code unless explicitly asked
- may be unavailable when the local Mac/Codex app is offline or disconnected

## Hard Boundaries

- `upstream` is fetch-only forever.
- Allowed: `git fetch upstream --prune --tags`.
- Forbidden: push, PR, merge, or publication to upstream.
- Publication, if requested, can only target `origin`.
- Upstream-only commits and fork-only fixes must stay separated.
- Never rewrite published history without explicit user instruction.
- Never weaken tests to hide a real product bug.
- Never use test-only edits to bypass wrong app behavior.
- QA unavailability is not a hard blocker for orchestrator/dev execution.
  Record such QA work as `PENDING_QA_RETRY` and retry when the QA thread is
  reachable.

## Completion And Ancestry

GitHub's `behind` count is ancestry-based, not content-based. Manual or
fork-aware ports can be correct product-wise and still leave every upstream
commit visible as "behind" until an audited upstream target is made an ancestor
of the fork branch.

Catch-up completion therefore requires both conditions:

1. Every actionable upstream commit through the chosen target is recorded in the
   ledger as applied, redundant, skipped, or explicitly deferred.
2. The chosen audited upstream target is recorded as an ancestor of the fork
   branch through an approved local ancestry-sync operation.

Do not target unaudited upstream commits in an ancestry sync. If upstream has
advanced beyond the last audited checkpoint, first audit and account for those
commits, or explicitly choose a narrower audited target and report the remaining
right-side count as deferred.

The approved no-content ancestry-sync pattern is local/fork-side only:

```bash
git merge -s ours --no-ff --no-commit <audited-upstream-target>
```

After that command, verify the tree and index are unchanged relative to the
first parent, then commit with a message that names the audited upstream target.
This records ancestry without copying upstream tree content. It must never be
used to mask unaudited commits, and it must never write to
`https://github.com/suitenumerique/drive.git`.

Required proofs for final ancestry reports:

- full remote identities and roles
- audited upstream target SHA
- before/after `git rev-list --left-right --count` values
- ledger coverage for every upstream commit through the target
- no-content tree/index proof for the ancestry-sync commit
- validation gates and any remaining right-side/behind count

### Publication Merge Method

An ancestry-sync PR into `Apoze/drive:main` must be published with GitHub's
`Create a merge commit` option, or an equivalent normal merge commit. Do not
use squash merge or rebase merge for the ancestry-sync PR.

Squash and rebase publication recreate commits and drop the no-content
ancestry-sync commit's upstream second parent. That leaves
`Apoze/drive:main` without the audited upstream ancestry, so GitHub can still
show the fork as behind even when the tree content is identical.

If repository settings or maintainer workflow would force squash or rebase for
the ancestry-sync PR, stop and escalate before publication. Do not claim the
catch-up is complete under that merge policy.

Before marking publication complete, fetch both remotes and verify the merged
`Apoze/drive:main` branch has right-side count `0` against the audited upstream
target. If the audited target is latest `suitenumerique/drive:main`, this
post-merge proof is:

```bash
git fetch origin --prune
git fetch upstream --prune --tags
git rev-list --left-right --count origin/main...upstream/main
```

Reports must continue to name the full repositories and roles. `origin`
(`https://github.com/Apoze/drive.git`) is the fork publication remote, and
`upstream` (`https://github.com/suitenumerique/drive.git`) remains fetch/read
only with push disabled.

## Modes

### Mode A - PREP ONLY

Default mode for a restarted catch-up cycle.

Allowed:

- create a local-only branch
- fetch remotes
- inspect current Git state
- regenerate missing commit lists
- classify risk/hotspots
- propose executable lots/batches
- update PREP artifacts

Forbidden:

- cherry-pick, even with `--no-commit`
- commit
- push
- PR

### Mode B - EXECUTE

Requires explicit user `GO`.

Rules:

- worktree must be clean before applying any batch
- batch commit must contain upstream-only changes
- fork-only corrections must be separate commits
- decision-required hotspots stop for an orchestrator/user decision
- validation level follows `tmp/GetToBehind0TaskTemp/00_meta/validation_matrix.md`
- completion requires both no actionable upstream commits and GitHub-visible
  `behind=0`
- if `behind` remains nonzero because the audited upstream target is not an
  ancestor, the next action is an audited ancestry-sync step, not a completed
  catch-up report

## Restart Procedure

For a new catch-up cycle, do not trust old artifacts blindly. They are history
and evidence, not automatically current planning data.

First dev prompt should be PREP ONLY and ask the dev agent to:

1. read `AGENTS.md`, `PLANS_catchup_commits.md`, and this file
2. verify `docker compose ps`
3. verify branch, worktree, remotes, push safety, and current SHAs
4. run:
   - `git fetch origin --prune`
   - `git fetch upstream --prune --tags`
5. enforce upstream fetch-only safety:
   - `git remote set-url --push upstream DISABLE` if needed
   - `git config remote.pushDefault origin` if needed
   - local pre-push hook refuses upstream pushes
6. record divergence counts:
   - `upstream/main...HEAD`
   - `upstream/main...origin/main`
7. regenerate canonical meta:
   - `tmp/GetToBehind0TaskTemp/00_meta/missing_list.txt`
   - `tmp/GetToBehind0TaskTemp/00_meta/missing_head40.txt`
   - index/ledger updates
8. create a new prep run under:
   `tmp/GetToBehind0TaskTemp/prep/prep_run_YYYYMMDD_HHMM/`
9. classify missing commits by risk, hotspot, and validation need
10. propose lots/batches and decision points
11. stop with a report and no code changes

After the orchestrator sends this PREP prompt to dev, the orchestrator must
wait for a dev `AGENT_MSG`/`DEV_REPORT` or a new user instruction. It must not
poll the dev thread in a loop while dev is working.

## Artifacts

Canonical meta files:

- `tmp/GetToBehind0TaskTemp/00_meta/index.md`
- `tmp/GetToBehind0TaskTemp/00_meta/ledger.tsv`
- `tmp/GetToBehind0TaskTemp/00_meta/missing_list.txt`
- `tmp/GetToBehind0TaskTemp/00_meta/missing_head40.txt`
- `tmp/GetToBehind0TaskTemp/00_meta/hotspots_paths.md`
- `tmp/GetToBehind0TaskTemp/00_meta/validation_matrix.md`

Per-batch structure:

- `tmp/GetToBehind0TaskTemp/batches/<BATCH_ID>/00_preflight/`
- `tmp/GetToBehind0TaskTemp/batches/<BATCH_ID>/01_selection/`
- `tmp/GetToBehind0TaskTemp/batches/<BATCH_ID>/02_apply/`
- `tmp/GetToBehind0TaskTemp/batches/<BATCH_ID>/03_validate/`
- `tmp/GetToBehind0TaskTemp/batches/<BATCH_ID>/04_report/`

Required selection files:

- `selected_commits.txt`
- `impact.md`

Required reports:

- `exec_report.md`
- `decision_report.md` when a decision gate is hit

## Decision-Required Hotspots

If a conflict touches these areas, stop and write a decision report before
continuing:

- Driver/StandardDriver contracts
- ExplorerTree/Actions
- routing/breadcrumbs core
- translations/i18n
- WOPI, mount, storage, archive, or permission security boundaries when the
  correct resolution is not obvious

Known safe-file rules remain in `PLANS_catchup_commits.md`, especially for
`CHANGELOG.md`, `AGENTS.md`, and Dockerfile conflicts.

## Dev-Agent Autonomy

Do not over-constrain the dev agent into stopping after every intermediate
validation failure.

Use lot-level prompts. The dev agent should continue through multiple
in-scope corrective iterations while all conditions stay true:

- the blocker is in validation, E2E, or frontend stabilization space
- the blocker is outside upstream-only application logic under validation
- the root cause is clear
- the fix is minimal and safe
- corrective commits can remain fork-only and separate

The dev agent must stop when:

- required validation is green and the batch/lot is done
- the first remaining blocker leaves scope
- root cause is ambiguous
- a decision-required hotspot is hit
- publication/upstream safety could be compromised

When dev stops, it must route its status to orchestrator before becoming idle.
The report must be sent through the orchestrator Codex thread when tools are
available. A local final answer in the dev thread is not enough if the
orchestrator must act. Dev must not decide that no further thread action is
needed; it reports to orchestrator and waits.

When orchestrator receives a completed dev/QA report and no user decision is
needed, orchestrator owns the next handoff: send the next dev or QA request, or
state explicitly why the workflow is intentionally waiting. Orchestrator may
stop without sending a new prompt only when the user must decide or when all
approved work is fully complete.

## Validation Cadence

Full three-browser L3 is a confidence checkpoint, not the default exit loop for
every lot.

Use this order by default:

1. Static gates and lint for the touched area.
2. Targeted unit/integration tests.
3. Focused E2E for changed user workflows, usually Chromium first.
4. Focused cross-browser E2E only when the risk is browser-sensitive or helper
   changes are shared.
5. Full L3 at planned checkpoints: broad dependency/runtime changes, shared
   auth/navigation/explorer-shell or preview/storage/WOPI/mount changes, a
   grouped visible-workflow cluster, or pre-publication readiness.

If a full L3 attempt exposes a failure clearly outside the current lot, do not
keep re-running the full matrix as a loop. Stabilize with focused reproduction
and focused reruns, then either schedule the next full L3 checkpoint or mark the
lot `L3_BLOCKED_OUT_OF_SCOPE` for orchestrator handling.

When the dev agent delegates browser evidence to QA, that delegation is also a
handoff point. Dev should not poll QA continuously; it should continue only with
unrelated safe work, or wait for `QA_REPORT` / `PENDING_QA_RETRY`.

## QA Coordination

Use QA for browser work that benefits from a local integrated browser and a
human-like visual pass, for example:

- preview/viewer visual regressions
- explorer layout, menus, modals, and focus behavior
- DevTools console/network inspection
- screenshot comparisons and responsive checks
- reproductions that need manual browser observation

Default QA flow:

1. Orchestrator or dev sends `QA_REQUEST`.
2. For LAN browser QA, the sender first runs `make qa-lan-ready` and includes
   the sanitized LAN auth preflight result in the request. If the preflight
   fails, the sender records the QA item as pending instead of sending QA into a
   known-bad auth flow.
3. For authenticated LAN browser QA, the sender also runs
   `make qa-lan-authenticated-ready` and includes the fixed browser bootstrap
   URL plus regular/mount fixture URLs from the sanitized output. The bootstrap
   uses debug-only E2E dummy users and must not expose cookies, tokens,
   passwords, auth headers, signed URLs, or real credentials.
4. The sender enters `WAITING_QA` for that QA chain and stops polling QA.
5. QA confirms local instructions and runs browser checks from the Mac-local
   context.
6. QA returns `QA_REPORT`.
7. If `QA_FAIL` clearly maps to an in-scope dev fix, QA may send the same
   `QA_REPORT` to dev and notify orchestrator.
8. Orchestrator decides whether the flow is complete, needs dev, needs QA
   retry, or needs the user.

If QA cannot be reached:

- do not block PREP or dev execution
- add a pending note to the relevant report or orchestrator todo
- retry later when the local Mac QA thread is available

## Reporting Contract

Use `DEV_REPORT` and `QA_REPORT` from
`docs/agent-thread-coordination-protocol.md`.

The orchestrator response to the user should stay short:

- very brief inspection/decision summary
- direct confirmation of any agent-to-agent messages already sent
- decision options only when `user_decision_needed: yes`
- no prompt for the user to forward to another agent

The next prompt must replace `PROMPT.md` completely.
