---
name: fork-catch-up-orchestration
description: Safe orchestration for bringing a fork or long-lived branch up to date with an upstream repository. Use when Codex is asked to audit ahead/behind state, plan catch-up lots, port upstream commits, manage cherry-picks, maintain a commit ledger, coordinate execution/review/QA agents, or reason about ancestry-based completion and publication gates.
---

# Fork Catch-Up Orchestration

Use this skill to make fork catch-up work explicit, reversible, and auditable.
Keep project-specific rules in the repository docs; this skill provides the
generic operating model.

## Core Workflow

1. Identify the repositories, remotes, base branch, working branch, and current
   worktree state. Name full remote URLs when reporting.
2. Read local guidance only when present: `AGENTS.md`, catch-up plans, release
   policy, CI policy, and contribution rules.
3. Default to audit/planning mode unless the user has explicitly authorized
   execution. Do not cherry-pick, commit, push, or publish from an ambiguous
   request.
4. Build a commit inventory from git history and any existing ledger. Separate
   already-applied, equivalent, skipped, conflicted, and pending commits.
5. Propose small lots ordered by dependency, blast radius, and validation cost.
6. Execute only after authorization, one lot at a time, with focused validation
   and a ledger update after each completed lot.
7. Finish with status, remaining work, validation, risks, and any decision that
   still needs a human.

## Mode Selector

- Use audit mode for inspection, planning, inventory, or lot proposals.
- Use execution mode only after explicit approval to apply changes.
- Use publication mode only after explicit approval to push, open a pull
  request, mark work ready, or merge.

## Resources

- Read `references/workflow-modes.md` when executing work, publishing work, or
  resolving ambiguous mode boundaries.
- Read `references/ledger-schema.md` before creating or updating a catch-up
  ledger.
- Read `references/conflict-policy.md` before applying commits or resolving
  conflicts.
- Read `references/coordination.md` before delegating catch-up work to another
  agent, reviewer, QA agent, or parallel worker.
- Read `references/reporting-contract.md` before handing off or producing final
  status.

## Boundaries

- Do not encode project names, thread IDs, private URLs, branch names, or
  product-specific rules in this skill.
- Do not use destructive git commands unless the user explicitly requests that
  exact operation and the repository guidance allows it.
- Do not reduce a catch-up to a raw behind count. Verify code equivalence,
  ledger coverage, and ancestry requirements separately.
- Preserve user work in dirty worktrees. If unrelated changes exist, leave them
  alone and report the boundary.
