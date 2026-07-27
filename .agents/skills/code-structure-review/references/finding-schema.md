# Finding Schema

Use findings that are concrete enough for an implementation agent to act on.

## Required Fields

- `id`: stable identifier, such as `CSR-001`.
- `title`: short behavior-oriented title.
- `severity`: blocker, high, medium, low.
- `status`: proposed, accepted, in-progress, fixed, deferred, rejected.
- `area`: subsystem, workflow, or module.
- `evidence`: file and line references.
- `problem`: what is structurally wrong.
- `impact`: correctness, security, performance, maintenance, or UX risk.
- `recommendation`: concrete shape of the fix.
- `validation`: tests or checks needed after the fix.

## Severity Guide

- `blocker`: active correctness, security, data loss, or release-blocking risk.
- `high`: likely defect or expensive coupling in a critical path.
- `medium`: real duplication or boundary problem with contained blast radius.
- `low`: cleanup opportunity that should wait behind higher-risk work.

## Evidence Rules

- Prefer file/line references over broad claims.
- Show at least two call sites for duplication findings unless one site is
  already too large or in the wrong layer.
- Separate observed facts from inferred risk.
- Do not include secrets or sensitive data from local files.

## Status Rules

Do not mark a finding fixed until the implementation and validation evidence are
available. Use `deferred` when the issue is real but not worth changing now.
