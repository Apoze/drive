# AGENTS.md Routing

Use `AGENTS.md` for durable repo rules that should affect every agent run.
Keep it short enough to load reliably and route to deeper docs by task area.

## Keep In AGENTS.md

- repository purpose and major stack;
- non-negotiable safety rules;
- build, test, and validation commands;
- task-to-document routing;
- git and publication policy;
- secrets handling;
- completion report expectations.

## Move Out Of AGENTS.md

- long design docs;
- historical investigations;
- detailed runbooks used only for one workflow;
- issue ledgers and finding inventories;
- environment-specific fixture details;
- verbose examples that are not needed on every task.

## Routing Table Pattern

Use a compact table or list:

- task area;
- read next;
- avoid unless relevant;
- missing-doc behavior when a canonical doc is absent.

## Conflict Rule

When docs disagree, the more specific and more local instruction normally wins.
If the conflict affects safety, security, publication, or user-visible product
behavior, stop and ask for a decision instead of guessing.

## Nested Instructions

Use nested `AGENTS.md` files for subtree-specific conventions. Do not put a
specialized subsystem contract in the root file when only one directory needs
it.
