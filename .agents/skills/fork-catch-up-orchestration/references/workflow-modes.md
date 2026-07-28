# Workflow Modes

## Mode Selection

Start in audit mode unless the user has given an explicit instruction to execute
work. Treat words such as "inspect", "plan", "prepare", "propose", "audit",
or "review" as audit mode. Treat execution as authorized only when the user
clearly allows commit application, conflict resolution, branch updates, pushes,
or pull request work.

## Audit Mode

Use audit mode to gather facts and propose work:

1. Check the current branch and worktree status.
2. Identify local and upstream repositories with full URLs.
3. Fetch only when repository guidance and user permissions allow it.
4. Compare ancestry, patch equivalence, and any existing ledger.
5. Produce lots that are small enough to validate independently.
6. Stop before changing code unless the user has authorized execution.

Audit mode may create or edit planning artifacts only when the user has asked
for durable documentation changes.

## Execution Mode

Use execution mode to apply one approved lot at a time:

1. Confirm the approved lot and expected base.
2. Re-check the worktree before changing files.
3. Apply commits or equivalent changes with traceability back to the source.
4. Resolve only conflicts covered by the conflict policy or local guidance.
5. Run validation proportional to the changed surface.
6. Update the ledger immediately after a lot is complete.
7. Stop on decision-required conflicts, failed validation, or scope drift.

## Publication Mode

Use publication mode only when the user explicitly asks to push, open a pull
request, mark a pull request ready, or merge. Follow local publication gates
before any remote update. When completion depends on git ancestry, verify the
merge method preserves the needed parentage instead of assuming a platform
behind count will change after squash or rebase publication.

## Completion Criteria

A catch-up is complete only when the agreed target commits are accounted for,
validation is done or explicitly deferred, and the repository state matches the
completion definition in local guidance. If ancestry, ledger, or validation
criteria disagree, report the discrepancy rather than declaring completion.
