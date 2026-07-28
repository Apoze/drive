---
name: repo-docs-hygiene
description: Audit and maintain repository guidance, AGENTS.md routing, documentation discoverability, context-budget hygiene, stale or duplicated docs, ignored canonical files, and agent-facing project instructions. Use when Codex is asked to inspect, optimize, reorganize, or apply best practices to repo docs and agent instruction files.
---

# Repo Docs Hygiene

Use this skill to keep repository guidance useful for agents without bloating
their context. The default behavior is inspect and propose; edit only when the
user authorizes changes.

## Workflow

1. Read local `AGENTS.md` guidance first when present.
2. Run the inventory script when shell access is available:
   `python3 <skill-dir>/scripts/doc_inventory.py --root <repo-root>`.
3. Identify instruction files, large docs, ignored or undiscoverable docs,
   duplicated onboarding paths, stale coordination instructions, and local-only
   artifacts that should not become durable guidance.
4. Decide the right surface for each rule: prompt, `AGENTS.md`, nested
   `AGENTS.md`, skill, config, hook, test, or ordinary documentation.
5. Prefer a small routing table in `AGENTS.md` that points to deeper docs
   instead of copying the deeper contracts into `AGENTS.md`.
6. Keep canonical docs visible to normal repo search unless they are truly
   local-only or sensitive.
7. If editing is authorized, make narrow documentation and ignore-file changes,
   then validate discoverability and formatting.

## Resources

- Read `references/agents-md-routing.md` before changing `AGENTS.md`.
- Read `references/doc-audit-checklist.md` for inspection passes.
- Read `references/discovery-and-ignore-hygiene.md` before changing ignore
  rules or classifying local-only docs.
- Read `references/surface-selection.md` when deciding where a rule belongs.
- Read `references/change-report-template.md` before final reporting.

## Boundaries

- Do not embed project-specific rules in this skill. Load them from the target
  repository.
- Do not delete docs just because they are large. Route, split, archive, or
  summarize only when the repository owner approves.
- Do not expose secrets or sensitive file contents while auditing docs.
- Do not treat ignored files as disposable; first decide whether they are
  canonical, generated, local-only, or sensitive.
