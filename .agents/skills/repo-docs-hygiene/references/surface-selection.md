# Surface Selection

Put each instruction on the smallest durable surface that matches its scope.

## Surfaces

- Prompt: one-off constraints for the current task.
- `AGENTS.md`: repo rules, commands, validation, safety, and routing.
- Nested `AGENTS.md`: subtree-specific rules.
- Skill: reusable workflow that applies across repositories or repeated task
  families.
- Config: tool behavior, model defaults, sandbox settings, or trusted local
  integrations.
- Hook or linter: mechanical enforcement that should run automatically.
- Test: behavior that must be verified, not merely remembered.
- Ordinary doc: background knowledge that agents should read only when relevant.

## Decision Questions

- Should every future agent in this repository see this?
- Does the instruction apply outside this repository?
- Can a tool enforce it better than prose?
- Is it a workflow, a rule, or background information?
- Will loading this on every task save more context than it costs?

## Migration Guidance

- Move repeated workflow detail from `AGENTS.md` to a skill or runbook.
- Move project-specific invariants from a generic skill back to repo docs.
- Move fragile mechanical rules to hooks, tests, or scripts.
- Keep examples in references unless they are essential to every invocation.
