---
name: browser-qa
description: Structured real-browser QA for web applications. Use when Codex must verify user flows, visual behavior, console or network errors, screenshots, authenticated browser setup, responsive layouts, accessibility smoke checks, or browser evidence after frontend, routing, preview, upload/download, auth, or UX changes.
---

# Browser QA

Use this skill to verify web behavior in a real browser and return evidence a
developer can act on. Use this tool order: repository QA contract or project
browser workflow, configured browser connector/tool, Playwright, then blocked
with the missing capability reported.

## Workflow

1. Confirm the QA request: URL, user role, credentials/bootstrap method,
   scenarios, expected behavior, and changed surface.
2. Read local guidance only when present: `AGENTS.md`, test contracts, browser
   QA docs, auth setup, and environment docs.
3. Start with a clean browser context unless the request explicitly depends on
   existing user state.
4. Open the app, capture initial page health, and watch console and network
   failures while exercising the scenario.
5. Verify the user-visible result across the requested viewport or at least one
   desktop and one mobile-sized viewport for layout-sensitive work.
6. Capture screenshots or traces only when they help prove the result or
   diagnose a failure.
7. Report verdict, evidence, reproduction steps, and developer-actionable
   defects.

## Resources

- Read `references/qa-input-contract.md` when the request does not provide all
  scenario inputs.
- Read `references/auth-and-secrets.md` before using authenticated sessions,
  fixtures, cookies, tokens, or private environments.
- Read `references/visual-checklist.md` before visual or responsive QA.
- Read `references/accessibility-smoke.md` before accessibility smoke checks.
- Read `references/qa-report-schema.md` before producing a QA report.

## Boundaries

- Do not expose cookies, tokens, auth headers, private fixture contents, or
  sensitive user data in logs, screenshots, reports, or prompts.
- Do not treat a passing unit test as browser QA. Browser QA requires rendered
  UI inspection or browser automation.
- Do not redesign the UI during QA. Report defects separately from proposed
  design improvements unless the user asked for implementation too.
- Keep project-specific URLs, accounts, and setup in the repository docs or the
  user's prompt, not in this skill.
