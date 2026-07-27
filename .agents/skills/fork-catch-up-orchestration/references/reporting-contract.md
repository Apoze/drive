# Reporting Contract

Use this shape for status reports, handoffs, and final answers.

## Required Summary

Include:

- repository and branch identities with full remote URLs when relevant;
- mode used: audit, execution, or publication;
- source range or target being caught up;
- lots completed, pending, skipped, blocked, or deferred;
- files changed by this agent;
- validation run and results;
- risks, residual gaps, and next decision needed.

## Execution Report

For each executed lot, include:

- lot identifier and source commits;
- local commits or files changed;
- conflict resolutions;
- validation evidence;
- ledger updates;
- follow-up QA or review needs.

## Blocked Report

When blocked, state:

- exact blocking condition;
- what was verified before stopping;
- safest next action;
- what must not happen until the block is resolved.

## Publication Report

Before push, pull request, ready-for-review, or merge, restate:

- fetch/push remote URL and role;
- base repository and branch;
- head repository and branch;
- pull request URL when present;
- required gates and their status;
- merge method constraints if ancestry matters.
