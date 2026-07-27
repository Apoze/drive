# Review Lot Pattern

Use lots to keep architecture review bounded and reproducible.

## Lot Selection

Choose lots around one of these shapes:

- user-facing workflow, such as create, upload, export, checkout, or invite;
- backend surface, such as API handlers, jobs, commands, or integrations;
- frontend surface, such as routing, data fetching, state, or shell layout;
- cross-cutting mechanic, such as permissions, retries, logging, caching, or
  error handling;
- test architecture, such as fixtures, setup, helpers, and environment choice.

## Lot Size

A good lot can be reviewed in one pass and produces specific findings. Split a
lot when it crosses unrelated domains, needs different reviewers, or requires
different validation strategy.

## Trace Method

For each lot:

1. Identify entry points and public contracts.
2. Follow the operation through orchestration and domain decisions.
3. Check shared utilities, side effects, and error paths.
4. Compare parallel flows that should behave the same.
5. Inspect tests that claim to cover the behavior.
6. Record evidence with file and line references.

## Lot Output

End each lot with:

- findings created or updated;
- areas inspected with no finding;
- uncertain areas needing deeper review;
- suggested next lot.
