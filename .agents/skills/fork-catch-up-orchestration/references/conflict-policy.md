# Conflict Policy

Resolve conflicts conservatively. The goal is to preserve local product
behavior while accounting for upstream changes.

## Stop Immediately

Stop and ask for a decision when a conflict affects:

- security, authentication, authorization, or secrets handling;
- user data migration, storage format, billing, payments, or compliance;
- public API behavior without local guidance;
- merge strategy, history rewriting, branch deletion, or destructive git work;
- product direction where both sides intentionally changed behavior.

## Usually Safe To Resolve Locally

Resolve without escalation only when the local guidance or nearby code makes
the answer clear:

- changelog or documentation line ordering;
- generated metadata that can be regenerated;
- formatting-only conflicts;
- dependency lock conflicts when the package manager can regenerate and tests
  cover the result;
- tests whose expected values clearly follow the accepted behavior.

## Required Checks

Before marking a conflict resolved:

1. Explain which side won and why.
2. Search for call sites or parallel implementations that need the same update.
3. Run focused validation for the touched behavior.
4. Record the resolution in the ledger or final report.

## Prohibited Shortcuts

- Do not use `ours` or `theirs` across a broad tree without file-by-file review.
- Do not hide unresolved conflict markers with formatting tools.
- Do not revert unrelated user changes to make a cherry-pick easier.
- Do not continue a long batch after a conflict changes the risk profile.
