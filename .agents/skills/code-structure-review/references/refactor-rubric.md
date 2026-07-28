# Refactor Rubric

Use this rubric before recommending a refactor.

## Good Refactor Candidates

Recommend a refactor when it:

- removes duplicated operational mechanics with shared invariants;
- places authorization, validation, persistence, or side effects in a clearer
  owner;
- reduces inconsistent behavior across parallel flows;
- makes tests easier to write at the correct level;
- isolates external systems behind a stable boundary;
- simplifies future changes without changing product behavior.

## Weak Candidates

Avoid recommending a refactor when:

- duplication is shallow and unlikely to diverge;
- a shared abstraction would need many flags or special cases;
- local clarity would be worse than the current repetition;
- the code is scheduled for deletion or replacement;
- the finding depends on style preference rather than behavior.

## Boundary Questions

Ask:

- Which layer owns the decision?
- Which layer owns the side effect?
- What contract do callers rely on?
- What happens on error, retry, cancellation, or partial failure?
- Which tests would fail if the behavior diverged?

## Recommendation Shape

Describe the smallest viable change:

- new service, helper, adapter, hook, or test fixture;
- call sites to migrate;
- behavior that must stay unchanged;
- validation required to prove safety.
