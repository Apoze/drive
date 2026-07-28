# Change Report Template

Use this shape after a docs hygiene pass.

## Summary

- inspection-only or edits applied;
- files changed;
- docs made more discoverable;
- docs intentionally left local-only;
- rules moved between surfaces.

## Validation

Include checks such as:

- `git status --short`;
- `rg --files` for canonical docs;
- `git check-ignore -v` for docs that should or should not be ignored;
- markdown formatting or link checks when available;
- size check for always-loaded instruction files.

## Risk

Mention:

- docs that remain large;
- missing canonical docs;
- local-only files that future agents may not see;
- any behavior policy that was clarified but not enforced by tests or hooks.

## Follow-Up

List follow-ups separately from completed work. Do not bury required user
decisions inside the summary.
