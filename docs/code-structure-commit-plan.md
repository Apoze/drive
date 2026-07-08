# Code Structure Commit And Validation Plan

This plan covers the local code-structure review fixes from R1-R7.

Status before commit preparation:

- All findings are implemented locally in the dirty worktree.
- No push, PR, merge, rebase, or publication is authorized by this plan.
- Local commits are authorized by the user for this code-structure series.
- The stack is currently in E2E mode after the final consolidation checkpoint.

## Commit Groups

Use thematic commits so each change remains reviewable.

1. Safety, cache, and transient confidence
   - Dev Lot A
   - Findings: CSR-R2-001, CSR-R3-001, CSR-R6-001
   - Expected subject: `fix(code-structure): tighten safety and transient checks`

2. E2E determinism and session bootstrap
   - Dev Lots B and B2
   - Findings: CSR-R5-001, CSR-R5-002, CSR-R5-003
   - Expected subject: `test(e2e): centralize deterministic session setup`

3. Backend and mount contract safety
   - Dev Lots C and G
   - Findings: CSR-R1-001, CSR-R4-001, CSR-R4-002, CSR-R4-003
   - Expected subject: `fix(mounts): enforce cleanup and public contracts`

4. Regular and mount storage mechanics
   - Dev Lots D and E
   - Findings: CSR-R1-002, CSR-R2-002, CSR-R4-004
   - Expected subject: `refactor(storage): share copy and mount write mechanics`

5. Explorer file open resolver
   - Dev Lot F
   - Finding: CSR-R3-002
   - Expected subject: `refactor(frontend): centralize explorer file opens`

6. Entitlement and file creation contracts
   - Dev Lots H and I
   - Findings: CSR-R1-004, CSR-R1-003
   - Expected subject: `refactor(backend): structure creation and entitlement decisions`

7. Review ledger and coordination docs
   - Orchestrator-owned docs only:
     - `docs/code-structure-review-findings.md`
     - `docs/code-structure-review-lots.md`
     - this file
   - Expected subject: `docs(code-structure): record review findings and plan`

## Execution Checklist

- Confirm branch is `codex/catchup-behind-mode-b`.
- Confirm `CHERRY_PICK_HEAD` is absent.
- Confirm no generated `src/frontend/apps/e2e/tsconfig.tsbuildinfo` is present.
- Review each commit's staged diff before committing.
- Do not stage unrelated ignored or generated files.
- Do not edit the orchestrator-owned ledger except the docs commit if explicitly
  staging existing orchestrator changes.
- Create local commits only.
- Do not push, open a PR, merge, rebase, publish, reset, or checkout.

## Post-Commit Validation

Run at least:

- `git diff --check origin/main..HEAD`
- no `fixup!` commits in the PR range
- backend `print(` gate: `git grep -n "print(" -- src/backend`
- changelog line-width sanity if `CHANGELOG.md` is touched
- gitlint on `origin/main..HEAD`
- scoped or full backend validation appropriate for touched backend areas
- `make frontend-lint`
- targeted frontend Jest for touched hooks, resolver, and mount label tests
- standard loopback E2E smoke for `entitlement-disclaimers.spec.ts`

Run broader validation if the commit preparation reveals unintended coupling.
Do not run full three-browser L3 by default unless explicitly scheduled.

## Push And PR Reporting

When reporting a fetch, push, PR, or publication step, always write the complete
repository identities. Remote aliases alone are not enough.

Required fields in the final report:

- `origin`: full fetch URL and push URL
- `upstream`: full fetch URL and explicit fetch-only/push-disabled status
- pushed branch: full repository owner/name and branch
- PR base: full repository owner/name and branch
- PR head: full repository owner/name and branch
- PR URL: full `https://github.com/<owner>/<repo>/pull/<number>` URL
- tracking branch: full remote repository owner/name and branch

Example for this repository:

- `origin`: `https://github.com/Apoze/drive.git` (fetch/push)
- `upstream`: `https://github.com/suitenumerique/drive.git` (fetch-only,
  push disabled)
- pushed branch: `Apoze/drive` `codex/catchup-behind-mode-b`
- PR base: `Apoze/drive` `main`
- PR head: `Apoze/drive` `codex/catchup-behind-mode-b`
- PR URL: `https://github.com/Apoze/drive/pull/<number>`

## Browser QA

After local commits and validation pass:

- Restore LAN readiness with `make qa-lan-ready`.
- Restore authenticated LAN QA with `make qa-lan-authenticated-ready`.
- Send QA a focused request covering:
  - authenticated Drive landing through bootstrap
  - representative explorer file open behavior still uses the current WOPI/new
    tab or preview behavior
  - representative MountProvider display label uses configured display name and
    does not expose provider-branded fallback copy
- QA must use sanitized evidence only and must not print cookies, tokens,
  signed URLs, auth headers, raw storage keys, mount raw paths, or secret values.

## Stop Conditions

Stop and report to orchestrator if:

- staging cannot produce clean thematic commits without overlap risk
- validation fails outside a clearly classifiable pre-existing issue
- QA finds a user-visible regression
- a push, PR, merge, rebase, destructive Git action, or publication decision is
  needed
