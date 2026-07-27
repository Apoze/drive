# Ledger Schema

Use a ledger when catch-up work spans multiple commits, agents, days, or pull
requests. The ledger is the durable source of truth for what happened to each
source commit.

## Minimum Fields

Use these fields in a table or structured document:

- `source`: source commit SHA or stable source identifier.
- `title`: short upstream commit title or change summary.
- `status`: one of the status values below.
- `target`: local commit SHA, pull request, branch, or "none".
- `method`: cherry-pick, manual port, already present, skipped, reverted, or
  deferred.
- `validation`: commands or checks run for this item or lot.
- `notes`: conflicts, equivalence evidence, or reason for deferral.

## Status Values

- `pending`: not yet audited or applied.
- `in-progress`: currently being handled.
- `applied`: source change exists locally with traceable target.
- `equivalent`: behavior is already present by another change.
- `skipped`: intentionally not applied with a recorded reason.
- `blocked`: cannot proceed without a decision or external fix.
- `deferred`: postponed by plan, risk, or dependency.

## Ledger Rules

- Record equivalence evidence. Do not mark a commit equivalent because a title
  looks similar.
- Keep skipped and deferred entries explicit. Silent omissions make later
  behind/ahead reports unreliable.
- Update the ledger after each lot, not only at the end of a long run.
- If a platform behind count is ancestry-based, track code coverage and ancestry
  separately. A manual port can satisfy code coverage while leaving ancestry
  unchanged.

## Lot Summary

For each lot, record:

- scope and source commit range;
- intended files or subsystem;
- validation plan;
- actual result;
- follow-up decisions or QA requests.
