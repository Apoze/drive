# Discovery And Ignore Hygiene

Agent-facing docs must be discoverable without dragging generated artifacts into
every search.

## Search Hygiene

Prefer fast repository search such as `rg` and `rg --files`. Exclude generated,
cache, dependency, build, coverage, test-output, temporary, and legacy artifact
directories unless the task is about those directories.

## Canonical Docs

A canonical doc should usually be:

- tracked or intentionally proposed for tracking;
- visible to `rg --files`;
- linked from `AGENTS.md`, README, or another reachable doc;
- free of secrets and local-only machine state.

## Local-Only Docs

Local-only docs are acceptable for:

- scratch prompts;
- private credentials instructions that do not contain secrets;
- machine-specific notes;
- generated reports;
- temporary migration workspaces.

Keep local-only docs out of durable routing unless the route clearly states they
may be absent.

## Ignore Rules

Before changing ignore rules:

1. Check whether the file is tracked.
2. Check whether the file is generated or hand-authored.
3. Check whether the file contains sensitive or machine-specific data.
4. Decide whether hiding it breaks agent discovery.
5. Prefer narrow ignore patterns over broad documentation ignores.

## Reporting

Report tracked, untracked, ignored, and local-exclude changes separately. Local
exclude files often do not appear in `git status`, so they need explicit mention
when they affect discoverability.
