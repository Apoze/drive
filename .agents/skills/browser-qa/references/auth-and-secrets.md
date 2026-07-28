# Auth And Secrets

Authenticated QA must prove behavior without leaking credentials or user data.

## Secret Handling

- Never print cookies, bearer tokens, signed URLs, passwords, API keys, or auth
  headers.
- Do not paste secret file contents into prompts or reports.
- Mask accidental sensitive output with `***`.
- Prefer documented bootstrap URLs, storage state files, or test fixtures over
  manual credential entry.
- Store screenshots only when they do not expose sensitive data, or crop/redact
  them before reporting.

## Session Setup

Use the repository's documented auth bootstrap when available. If none exists,
prefer a fresh test account in a local or staging environment. Confirm which
identity is active before exercising the flow.

## Reporting Auth Issues

When auth blocks QA, report:

- the non-sensitive setup method attempted;
- the URL origin, not private tokens or full signed URLs;
- the visible error;
- whether the failure is environment setup, app behavior, or missing input.

## Production Safety

Avoid write actions in production-like environments. If the user explicitly
requires production verification, ask for written confirmation of the exact
action and data scope before proceeding.
