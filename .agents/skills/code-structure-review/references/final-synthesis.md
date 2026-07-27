# Final Synthesis

Use synthesis when multiple lots have produced findings.

## Group Findings

Group by:

- shared behavior or duplicated mechanic;
- subsystem ownership;
- validation strategy;
- risk level;
- implementation dependency.

## Prioritize

Prefer this order:

1. correctness, security, data integrity, or release blockers;
2. fixes that unblock other findings;
3. high-churn duplicated mechanics;
4. validation infrastructure needed for safe refactors;
5. low-risk cleanup.

## Implementation Plan

For each proposed implementation group, include:

- findings addressed;
- intended files or modules;
- behavior-preserving constraints;
- migration order;
- validation commands or manual checks;
- rollback or stop condition.

## Non-Goals

List findings that should not be implemented now and why. This prevents a
review from turning into an unbounded cleanup campaign.
