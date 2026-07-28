---
name: code-structure-review
description: Lot-based code-structure and architecture review for existing codebases. Use when Codex is asked to inspect service boundaries, duplicated operational mechanics, misplaced logic across controllers/actions/handlers/jobs/views/hooks, refactor candidates, or to produce a prioritized findings ledger without immediately implementing changes.
---

# Code Structure Review

Use this skill to review architecture and code organization without drifting
into broad rewrites. The default output is a findings ledger and prioritized
plan; implementation happens only when the user asks for it.

## Workflow

1. Read local guidance only when present: `AGENTS.md`, architecture docs,
   module ownership docs, contribution rules, and existing review ledgers.
2. Define review lots by subsystem, workflow, or shared mechanic. Keep each lot
   small enough to inspect with file/line evidence.
3. For each lot, trace the user-facing operation through entry points,
   orchestration, domain logic, persistence, background work, and tests.
4. Identify duplicated mechanics, misplaced responsibilities, hidden contracts,
   leaky abstractions, and validation gaps.
5. Record findings with severity, evidence, risk, and a concrete refactor shape.
6. Prioritize fixes by correctness risk, blast radius, coupling reduction, and
   validation confidence.
7. Stop at recommendations unless the user explicitly asks to implement.

## Resources

- Read `references/review-lot-pattern.md` before planning review lots.
- Read `references/finding-schema.md` before writing or updating findings.
- Read `references/refactor-rubric.md` when deciding whether something is worth
  abstracting.
- Read `references/final-synthesis.md` before producing an implementation plan
  from multiple findings.

## Boundaries

- Do not encode project-specific module names or architecture rules in this
  skill. Load them from the target repository.
- Do not flag stylistic differences as architecture findings unless they create
  real risk, duplication, or maintenance cost.
- Do not recommend a shared abstraction only because two blocks look similar.
  Confirm the behavior, invariants, failure handling, and ownership match.
- Do not implement during a review-only request.
