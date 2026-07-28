# Doc Audit Checklist

Use this checklist during repository documentation audits.

## Inventory

- root and nested `AGENTS.md` or override files;
- README and contribution docs;
- architecture and environment docs;
- workflow runbooks;
- issue, finding, and migration ledgers;
- repo skills under `.agents/skills`;
- ignored markdown files and local-only notes.

## Quality Checks

- Is there exactly one canonical starting point?
- Are task-specific docs reachable from that starting point?
- Do duplicate "read this first" lists disagree?
- Are stale manual handoff instructions still present?
- Are generated, temporary, or legacy directories excluded from normal search?
- Are canonical docs hidden by `.gitignore`, `.git/info/exclude`, or local
  tooling?
- Are docs too large for always-loaded instruction budgets?
- Do docs instruct agents to print secrets, tokens, cookies, or file contents?
- For deep repo-skill reviews, use `skill-creator` as the quality standard
  when it is available.

## Output

Classify findings as:

- fix now;
- propose only;
- needs owner decision;
- local-only cleanup;
- not a problem.

Include concrete file paths and validation steps for each proposed change.
