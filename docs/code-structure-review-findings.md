# Code Structure Review Findings

This file is the running ledger for findings returned by the dedicated
code-structure review thread.

Review source:

- Thread: `codex://threads/019f40a2-5797-7f31-a875-1ce3331461ad`
- Skill: `/root/.codex/skills/code-structure/SKILL.md`
- Lot plan: `docs/code-structure-review-lots.md`

The orchestrator owns this ledger. Review agents report findings back to the
orchestrator and wait; they do not self-advance or edit this file unless
explicitly asked.

## Status Values

- `open`: confirmed finding, not yet routed to dev.
- `triaged`: accepted into a planned fix lot.
- `in_progress`: routed to dev and under active work.
- `fixed`: implemented and validated.
- `deferred`: deliberately postponed.
- `rejected`: reviewed and intentionally not pursued.

## Findings

### CSR-R1-001 - Stale Pending Cleanup Bypasses Purge Mechanics

- Status: `fixed`
- Severity: `P1`
- Source lot: R1 Backend API, Jobs, And Commands
- Source report: `20260708-code-structure-r1-backend`
- Fix report: `20260708-code-structure-dev-lot-c`
- Primary file: `src/backend/core/management/commands/clean_pending_items.py:34`

Impact:

The command soft-deletes pending file rows and then deletes them directly. If
an object was uploaded to S3 but never finalized, this can bypass the
hard-delete plus `process_item_purge` storage-deletion path used by newer
cleanup and API failure flows.

Evidence:

- `clean_pending_items` calls `item.soft_delete()` then `item.delete()`.
- API failure cleanup soft-deletes, hard-deletes, and queues
  `process_item_purge`.
- `core.tasks.item` CREATING cleanup uses the same hard-delete plus purge
  queue contract.
- `purge_deleted_items` queues `process_item_purge` instead of deleting rows
  directly.

Recommendation:

Extract a small stale-item cleanup/purge service, or switch
`clean_pending_items` to the same `hard_delete` plus `process_item_purge`
contract. Align the age predicate with upload-state semantics and add a
regression test with a pending item whose object exists in storage.

### CSR-R1-002 - S3 Copy Fallback Missing From Duplicate Flow

- Status: `fixed`
- Severity: `P1`
- Source lot: R1 Backend API, Jobs, And Commands
- Source report: `20260708-code-structure-r1-backend`
- Fix report: `20260708-code-structure-dev-lot-d`
- Primary file: `src/backend/core/tasks/item.py:270`

Impact:

A storage gateway that rejects `CopyObject` can still work for upload-ended
content-type repair and rename, but `duplicate_file` retries `CopyObject` until
max retries and then deletes the duplicate placeholder. The low-level copy
mechanic can drift because it is not a shared service capability.

Evidence:

- `upload_ended` catches `ClientError` from `copy_object` and streams
  `GET` to `PUT` through `stream_to_s3_object`.
- `rename_file` has a similar `CopyObject` fallback.
- `duplicate_file` calls `copy_object` directly and retries/deletes on
  provider errors.

Recommendation:

Extract a composable regular-storage helper such as
`copy_s3_object_with_streaming_fallback(...)` returning a structured result.
Keep task-level state transitions and retry policy in callers, but share the
object-copy mechanics.

### CSR-R1-003 - File And Template Creation Mechanics Are Split

- Status: `fixed`
- Severity: `P2`
- Source lot: R1 Backend API, Jobs, And Commands
- Source report: `20260708-code-structure-r1-backend`
- Fix report: `20260708-code-structure-dev-lot-i`
- Primary file: `src/backend/core/api/viewsets.py:1002`

Impact:

`ItemViewSet` owns storage writes, template payload selection, root-access
creation, cleanup, timing logs, and upload-state transitions across several
paths. ODF and template creation have multiple implementations, so fixes to
template or storage behavior can be missed in sibling flows.

Evidence:

- Legacy template creation reads local assets and writes storage in
  `_create_file_from_template`.
- `perform_create` and `children` POST use that helper.
- `new_odf` repeats item creation, root access, storage write, cleanup, and
  state updates.
- `new_file` repeats similar mechanics plus OOXML and empty-file branching.
- Payload resolution lives as a private viewset helper.

Recommendation:

Extract the repeated mechanics first: payload resolution and storage
write/cleanup into a small service with explicit inputs and structured output.
Keep request validation, entitlements, parent permission checks, and HTTP
error mapping in the viewset.

### CSR-R1-004 - Entitlement Decisions Use An Implicit Dict Contract

- Status: `fixed`
- Severity: `P2`
- Source lot: R1 Backend API, Jobs, And Commands
- Source report: `20260708-code-structure-r1-backend`
- Fix report: `20260708-code-structure-dev-lot-h`
- Primary file: `src/backend/core/entitlements/backends/base.py:16`

Impact:

Backend callers repeatedly look for `result` and `message`, but the
DeployCenter backend returns `result` and `reason`. Provider denial reasons can
be dropped in upload-denial paths, and every caller must remember the informal
dict shape.

Evidence:

- The abstract backend declares `can_upload` without a structured return
  contract.
- DeployCenter returns `{result, reason}`.
- Upload callers and mount archive extraction use
  `can_upload.get("message", default)`.

Recommendation:

Introduce an `EntitlementDecision` dataclass or normalization helper exposing
`result`, `public_message`, and optional `reason` or `code`. Convert backends
first, then replace call sites incrementally.

### CSR-R2-001 - Oversized Upload Rejection Logs Raw Storage Key

- Status: `fixed`
- Severity: `P1`
- Source lot: R2 Storage, Upload, Export, WOPI, And Conversion
- Source report: `20260708-code-structure-r2-storage`
- Fix report: `20260708-code-structure-dev-lot-a`
- Primary file: `src/backend/core/api/viewsets.py:1454`

Impact:

The oversized upload rejection path logs `item.file_key` directly, violating
the storage contract that storage keys stay out of logs. The current test
codifies the leak, so the regression suite preserves the unsafe behavior.

Evidence:

- `upload_ended` deletes the item on `DATA_UPLOAD_MAX_MEMORY_SIZE` overflow
  and logs `for file %s` with `item.file_key`.
- Nearby paths already use hashed storage-key logging through
  `safe_str_hash(item.file_key)`.
- `test_api_item_upload_ended.py` asserts the oversized path log contains the
  raw `item.file_key`, while adjacent tests assert no-leak behavior for normal
  and mimetype-denied paths.

Recommendation:

Replace the raw key in the oversized-path log with `item_id` plus
`safe_str_hash(item.file_key)`. Update the test to assert the raw key is absent
and the hash is present.

### CSR-R2-002 - Regular S3 Copy/Rename Mechanics Are Duplicated

- Status: `fixed`
- Severity: `P2`
- Source lot: R2 Storage, Upload, Export, WOPI, And Conversion
- Source report: `20260708-code-structure-r2-storage`
- Fix report: `20260708-code-structure-dev-lot-d`
- Primary file: `src/backend/core/api/viewsets.py:1521`

Impact:

Regular Drive object copy, metadata update, fallback streaming, source cleanup,
and error reporting are repeated across API, tasks, and WOPI. Some paths handle
S3 gateway `CopyObject` incompatibility while others do not, and raw provider
exception text is handled inconsistently.

Evidence:

- Upload-ended content-type repair handles `CopyObject`, falls back to
  `GET` to `PUT`, and logs hashed keys.
- `rename_file` repeats a similar fallback.
- WOPI rename performs DB save plus direct S3 copy inside a transaction with no
  streaming fallback.
- `duplicate_file` performs direct `CopyObject` only, retries provider errors,
  and can log raw provider exception text.
- `core.services.s3_streaming` centralizes streaming upload but not copy,
  move, metadata, or delete-source semantics.

Recommendation:

Add a regular-storage service such as `copy_regular_storage_object(...)` that
performs `CopyObject` with `GET` to `PUT` fallback, closes `StreamingBody`,
returns bytes/version/error class without keys, and optionally deletes a source
version after success. Convert WOPI rename and duplicate first, then fold
upload-ended repair and `rename_file` into it. Keep authorization, lock rules,
filename uniqueness, and upload-state policy in the existing orchestrators.

### CSR-R3-001 - Favorite Cache Refresh Invalidates A Nested Query Key

- Status: `fixed`
- Severity: `P1`
- Source lot: R3 Frontend Explorer Orchestration
- Source report: `20260708-code-structure-r3-frontend-explorer`
- Fix report: `20260708-code-structure-dev-lot-a`
- Primary file:
  `src/frontend/apps/drive/src/features/explorer/hooks/useRefreshItems.ts:166`

Impact:

Favoriting or unfavoriting can leave already-loaded favorite/item caches stale
because the helper passes a list of query keys as one React Query key. This is
also cache-mechanics drift: adjacent helpers invalidate multiple keys by
iterating each key, while the favorite-specific helper owns a subtly different
contract.

Evidence:

- `useRefreshFavoriteCache` builds `moreQueriesToInvalidate: QueryKey[]`.
- It then calls `queryClient.invalidateQueries({ queryKey:
  moreQueriesToInvalidate })` once.
- React Query receives a nested key shaped like
  `[["items","infinite",...],["items",itemId]]`, which does not match either
  intended query key.
- The generic mutation refresh helper and `useRefreshItemCache` already loop
  over extra keys correctly.
- The current unit test codifies the nested key shape, protecting the bug.
- Favorite mutations depend on this helper.

Recommendation:

Extract a tiny shared `invalidateQueryKeys(queryClient, keys)` helper or reuse
the existing per-key pattern. Update `useRefreshFavoriteCache` to invalidate
each intended key separately, and flip the test to assert separate invalidation
calls. Keep product policy in mutation hooks and centralize query-key
mechanics.

### CSR-R3-002 - WOPI File Opens Bypass The Preview Source Contract

- Status: `fixed`
- Severity: `P2`
- Source lot: R3 Frontend Explorer Orchestration
- Source report: `20260708-code-structure-r3-frontend-explorer`
- Fix report: `20260708-code-structure-dev-lot-f`
- Primary file:
  `src/frontend/apps/drive/src/features/explorer/components/app-view/AppExplorerGrid.tsx:47`

Impact:

Regular explorer grid clicks encode WOPI open policy in the UI shell instead
of the preview/open-action layer. That bypasses the generic
`FilePreview`/`PreviewSource` path where WOPI rendering, source overrides,
fallback UI, download wiring, and mount/custom preview parity are otherwise
modeled. Future WOPI or preview fixes can land in one path and miss the other.

Evidence:

- `AppExplorerGrid` opens every `item.is_wopi_supported` file directly with
  `openWopiInNewTab(item.id)` before calling `openPreview`.
- `searchModalHelpers` imports the same helper and repeats the active-file
  branch for WOPI-supported files.
- The search helper test codifies this direct behavior.
- Existing tests lock in that default behavior.
- The generic preview contract exposes `PreviewSource.renderWopiEditor`.
- `FilesPreview` decides WOPI rendering through the source/default WOPI
  renderer.
- `CustomFilesPreview` passes regular Drive items into `FilePreview` with
  `defaultPreviewSource`, but the grid-click path prevents WOPI-supported
  regular items from reaching it.
- Mount preview uses a custom WOPI rendering path, making direct regular-item
  entry points more likely to drift from preview-source behavior.

Recommendation:

Introduce a small open-action resolver/controller such as
`resolveExplorerFileOpenAction` or `openFileFromExplorer`. It should make the
product policy explicit, including new-tab versus preview-host behavior, while
keeping WOPI mechanics and source/fallback behavior behind the preview or
open-action layer. Migrate grid and search first.

### CSR-R4-001 - Mount Archive Hardening Uses The Wrong Unsafe Error Contract

- Status: `fixed`
- Severity: `P1`
- Source lot: R4 MountProvider Boundaries
- Source report: `20260708-code-structure-r4-mountprovider`
- Fix report: `20260708-code-structure-dev-lot-c`
- Primary file: `src/backend/core/services/mount_archive_extraction.py:95`

Impact:

Clients and support tooling cannot key on the documented fail-closed hardening
error. The public refusal text is also provider-branded, mentioning SMB even
though the hardening gate applies to all MountProvider backends.

Evidence:

- `docs/agent-storage-contract.md` defines the mount archive extraction
  fail-closed contract, including stable backend error code
  `MOUNT_ARCHIVE_EXTRACT_UNSAFE`.
- `mount_security.py` defines the public refusal message as
  `Mount non hardené pour extraction (SMB hardening requis)`.
- `mount_archive_extraction.py` raises `public_code=
  "mount.archive_extract.unsafe"` instead of the documented stable code.
- `viewsets.py` forwards only DRF `detail` and `code` from the service error;
  it does not expose the documented structured `error_code`/header contract.
- Existing service/API tests codify the lowercase code.

Recommendation:

Introduce one mount archive unsafe-error constant and response mapper at the
service/API seam. Return the documented stable code and a provider-agnostic
message, then update the existing service/API tests.

### CSR-R4-002 - Preview Info Bypasses The Mount Preview IO Guard

- Status: `fixed`
- Severity: `P1`
- Source lot: R4 MountProvider Boundaries
- Source report: `20260708-code-structure-r4-mountprovider`
- Fix report: `20260708-code-structure-dev-lot-c`
- Primary file: `src/backend/core/api/viewsets.py:6120`

Impact:

A direct `/mounts/<id>/preview-info/` call against a provider without
`open_read`, or a provider whose IO capability changes after browse, can raise
an implementation error instead of returning the same controlled capability
degradation as other preview endpoints.

Evidence:

- `mount_capabilities.py` defines `MOUNT_PREVIEW_UNAVAILABLE` with required IO
  `open_read`.
- Legacy `preview` and `inline-preview` endpoints apply that unavailable
  spec.
- `preview_info` calls `_mount_read_target_or_400` without
  `unavailable_spec`, then immediately reads metadata.
- The no-spec path resolves provider/io but does not enforce required IO.
- Metadata prefix reads call `provider.open_read(...)` directly.
- Static provider advertises no browser stream IO and does not expose
  `open_read`.
- Tests cover happy-path SMB preview-info and the old preview endpoint guard,
  but not a no-`open_read` preview-info negative case.

Recommendation:

Route `preview_info` through
`_mount_read_target_with_metadata_or_400(..., unavailable_spec=
MOUNT_PREVIEW_UNAVAILABLE)` or a dedicated preview-info resolver that returns a
structured unsupported contract before touching `open_read`. Add a
static-provider/no-`open_read` regression test.

### CSR-R4-003 - Provider-Branded Mount UI And Public Errors Leak Into Product Paths

- Status: `fixed`
- Severity: `P2`
- Source lot: R4 MountProvider Boundaries
- Source report: `20260708-code-structure-r4-mountprovider`
- Fix report: `20260708-code-structure-dev-lot-g`
- Primary file: `src/backend/core/mounts/providers/smb.py:266`

Impact:

Provider details leak into product UI/API behavior and can drift as additional
providers are added. The frontend display-name override is also a concrete UX
regression for SMB mounts.

Evidence:

- `docs/agent-storage-contract.md` says MountProvider behavior must not depend
  on provider brand and forbids provider-specific user-facing messages.
- SMB provider maps provider failures to public messages such as
  `SMB share not found.`, `SMB authentication failed.`, and
  `SMB mount is unreachable.`
- API viewset surfaces `exc.public_message` and `exc.public_code` directly.
- `mountExplorerItems.ts` branches on `provider === "smb"` and returns `SMB`,
  otherwise falling back to `provider.toUpperCase()`.
- Tests codify that a mount with display name `Finance share` and provider
  `smb` displays as `SMB`, dropping the configured display name.
- `MountBrowseExplorer` uses `SMB` as the fallback title before discovery
  resolves.

Recommendation:

Keep provider-specific `failure_class` or operator hints for logs, but
normalize public API messages/codes at the API/service boundary. On the
frontend, prefer `display_name`, then a provider-agnostic fallback such as the
mount id/title. Keep provider only as non-behavioral metadata when needed.

### CSR-R4-004 - Mount Temp-Write And Rename Mechanics Are Repeated

- Status: `fixed`
- Severity: `P2`
- Source lot: R4 MountProvider Boundaries
- Source report: `20260708-code-structure-r4-mountprovider`
- Fix report: `20260708-code-structure-dev-lot-e`
- Primary file: `src/backend/core/api/viewsets.py:4387`

Impact:

The same provider-neutral write transaction contract is maintained in API
upload, API duplicate, and async archive extraction. Fixes for temp naming,
cleanup after partial writes, timeout/size handling, or rename failure
semantics can land in one flow but not the others.

Evidence:

- `MountViewSet` upload implements temp writing, chunk limits/timeouts,
  cleanup, and final rename locally.
- Mount duplicate implements source read, temp write, cleanup, and final rename
  in a separate local path.
- `archive/extract_mount.py` repeats provider-neutral mkdir/temp
  write/rename/cleanup mechanics for archive extraction jobs.

Recommendation:

Extract a small mount write transaction/copy helper service with explicit
inputs and structured errors/results. Leave endpoint/task product policy in
the current orchestration layers. Migrate upload first, then duplicate and
archive extraction.

### CSR-R5-001 - Standard E2E Origin Selection Is Split Across Entry Points

- Status: `fixed`
- Severity: `P1`
- Source lot: R5 E2E And Test Helper Architecture
- Source report: `20260708-code-structure-r5-e2e-helpers`
- Fix report: `20260708-code-structure-dev-lot-b`
- Primary file: `Makefile:102`

Impact:

The same E2E helper surface can hit different stacks depending on entrypoint
and spec-local fallback. Targeted Make usage can run against LAN dev defaults
while the caller believes they are validating the standard loopback E2E stack,
causing false passes/failures and making direct runs drift from the documented
contract.

Evidence:

- `docs/WorkDone/e2e/test-execution-contract.md` defines standard local E2E
  as `ENV_OVERRIDE=e2e` with loopback origins on `127.0.0.1`.
- `run_env_e2e.sh` injects loopback origins explicitly.
- The `Makefile` says E2E defaults to the LAN dev stack and sets E2E origins
  to `192.168.10.123` defaults.
- Playwright config defaults browser base URL to `192.168.10.123`.
- `utils-common.ts` defaults shared E2E API origin to
  `http://192.168.10.123:8071`.
- Some specs paper over this with loopback fallbacks, while others fall back to
  LAN.

Recommendation:

Centralize origin resolution in one E2E helper/module. Make standard E2E
targets default to loopback/manual origins, or require an explicit LAN-mode
variable for LAN specs. Replace spec-local fallbacks with the shared resolver.

### CSR-R5-002 - A Product Spec Still Uses The Deprecated Global Login Helper

- Status: `fixed`
- Severity: `P1`
- Source lot: R5 E2E And Test Helper Architecture
- Source report: `20260708-code-structure-r5-e2e-helpers`
- Fix report: `20260708-code-structure-dev-lot-b`
- Primary file:
  `src/frontend/apps/e2e/__tests__/app-drive/entitlement-disclaimers.spec.ts:106`

Impact:

The entitlement disclaimers spec bypasses namespaced bootstrap,
S2S-authenticated session creation, and scoped cleanup. Under the documented
multi-worker local policy, it can mutate or depend on the shared
`drive@example.com` actor and leave state outside the deterministic E2E scope
model.

Evidence:

- Backend E2E viewsets document `user-auth` as legacy readiness-only and say
  normal product specs should use `/bootstrap-session/`.
- `utils-common.ts` marks `login` deprecated and says new specs must not call
  it.
- Readiness smoke uses legacy clear/login behind the readiness-only skip gate,
  matching the transitional contract.
- `entitlement-disclaimers.spec.ts` calls deprecated
  `login(page, "drive@example.com")` in an ordinary product spec.

Recommendation:

Migrate the entitlement spec to `fixtures/auth` with a deterministic actor
option, or add an entitlement-specific fixture using `/bootstrap-session/` and
scoped cleanup. Then remove or guard the deprecated alias so future
non-readiness specs cannot import it accidentally.

### CSR-R5-003 - Bootstrap Session Mechanics Are Duplicated Across Actor Fixtures

- Status: `fixed`
- Severity: `P2`
- Source lot: R5 E2E And Test Helper Architecture
- Source report: `20260708-code-structure-r5-e2e-helpers`
- Fix report: `20260708-code-structure-dev-lot-b2`
- Primary file:
  `src/frontend/apps/e2e/__tests__/app-drive/fixtures/actors.ts:24`

Impact:

Fixes to bootstrap failure classification, endpoint paths, `/users/me/`
validation, storage-state creation, or cleanup behavior can land in one actor
fixture stack while the others keep old mechanics. The current stacks already
differ on `/users/me/` validation and cleanup semantics.

Evidence:

- `fixtures/actors.ts` posts to `bootstrap-session`, validates the response,
  checks `/users/me/`, writes storage state, and returns the actor fixture.
- `fixtures/auth.ts` repeats bootstrap request/validation/storage-state
  mechanics, but uses a literal endpoint path and skips `/users/me/`
  verification.
- `utils-common.ts` has a third browser-context bootstrap path that reposts to
  `bootstrap-session` and validates `/users/me/` if page auth is lost.
- Cleanup semantics differ between fixture stacks: one is per-test, another is
  worker-scoped and relies on scenario cleanup.

Recommendation:

Extract one explicit `bootstrapActorSession` helper that accepts
browser/request context, actor options, worker/test scope, and cleanup mode,
and returns the existing structured `WorkerActorFixture`. Keep product-level
fixture choices in `fixtures/auth.ts`, `fixtures/actors.ts`, and
`fixtures/scenarios.ts`, but centralize reusable session mechanics.

### CSR-R6-001 - Transient Poller Consolidation Left Duplicating Tests Stale

- Status: `fixed`
- Severity: `P1`
- Source lot: R6 Cross-Cutting Mechanics
- Source report: `20260708-code-structure-r6-cross-cutting`
- Fix report: `20260708-code-structure-dev-lot-a`
- Primary file:
  `src/frontend/apps/drive/src/features/explorer/hooks/useDuplicatingItemsPoller.ts:4`

Impact:

The duplicating-specific poller is now a compatibility wrapper over the shared
transient poller, but its unit test still asserts old duplicate-only mechanics.
This can block frontend validation and leaves future transient-row changes
protected by stale expectations rather than the real shared contract.

Evidence:

- `useDuplicatingItemsPoller` delegates directly to
  `useTransientItemsPoller`.
- `useTransientItemsPoller` polls all `POLLED_UPLOAD_STATES` and uses query key
  `["items", item.id, "transient-poll"]`.
- The legacy test still renders `useDuplicatingItemsPoller` and expects
  `["items", "copy", "duplicate-poll"]`.
- The test mocks `@tanstack/react-query` with only `useQueries`, while the
  delegated implementation calls `useQueryClient`.

Recommendation:

Update coverage to target the shared `useTransientItemsPoller` contract
directly, including duplicating/converting/analyzing terminal behavior and 404
cleanup. If no production caller still imports `useDuplicatingItemsPoller`,
remove the wrapper and obsolete test; otherwise keep a tiny wrapper test that
only asserts delegation.

## Deferred Synthesis Notes

- `CSR-R1-002` and `CSR-R2-002` describe the same underlying storage-copy
  boundary problem from different review angles. They should likely become one
  implementation lot.
- `CSR-R1-001` and `CSR-R2-001` are higher-risk backend cleanup/security
  candidates and should be considered before broader maintainability work.
- `CSR-R3-001` is a focused product/cache bug and may be suitable for an early
  small fix lot.
- `CSR-R4-001` and `CSR-R4-002` are contract/capability failures in
  MountProvider preview/archive surfaces and should be considered before
  broader mount refactors.
- `CSR-R4-004` is the mount-side analogue of the regular-storage mechanics
  duplication in `CSR-R1-002`/`CSR-R2-002`.
- `CSR-R5-001` and `CSR-R5-002` can make validation evidence less
  deterministic; they should be considered before relying on narrower targeted
  E2E campaigns as publication evidence.
- `CSR-R3-002`, `CSR-R4-002`, and the R6 WOPI grouping notes point to one
  missing open/preview/source resolver contract across regular files, mount
  files, and search/grid entry points.
- `CSR-R6-001` belongs with the validation determinism group because stale
  tests can block or distort confidence in the shared transient-row behavior.
- R7 final synthesis should group these findings by risk, effort, and safe
  migration order instead of treating every entry as an independent refactor.

## Final Synthesis

Source report: `20260708-code-structure-r7-final-synthesis`.

The findings form a small refactor program, not fifteen independent issues.
The sequence below keeps blast radius low and creates better validation
confidence before larger service-boundary work.

### Recommended Sequence

1. Safety and test-confidence quick fixes:
   - `CSR-R2-001`: remove raw storage key logging from oversized upload
     rejection and update the test to assert the no-leak contract.
   - `CSR-R3-001`: fix favorite cache invalidation so intended query keys are
     invalidated separately.
   - `CSR-R6-001`: update transient poller coverage to match the shared
     `useTransientItemsPoller` contract, or keep only a tiny delegation test
     for the compatibility wrapper.

2. E2E determinism foundation:
   - `CSR-R5-001`: centralize E2E origin resolution and remove split
     loopback/LAN defaults.
   - `CSR-R5-002`: migrate the entitlement disclaimers spec away from legacy
     global login.
   - `CSR-R5-003`: extract shared actor session bootstrap mechanics after the
     first two are stable.

3. Backend and mount contract safety:
   - `CSR-R1-001`: move stale pending cleanup onto the same purge lifecycle as
     normal hard-delete.
   - `CSR-R4-001`: return the documented mount archive unsafe code and
     provider-agnostic public text.
   - `CSR-R4-002`: route mount `preview-info` through the same preview IO guard
     as the other preview endpoints.

4. Regular Drive storage mechanics:
   - Group `CSR-R1-002` and `CSR-R2-002` into one regular-storage copy/move
     helper lot. Migrate duplicate and WOPI rename first, then fold in
     upload-ended repair and rename.

5. Mount write/rename mechanics:
   - Handle `CSR-R4-004` separately from regular S3 mechanics with a provider
     transaction helper for temp write, bounded streaming, final rename,
     rollback, cleanup, and structured errors.

6. Frontend open/preview/WOPI source resolver:
   - Handle `CSR-R3-002` after the immediate cache fix. Preserve current WOPI
     new-tab behavior unless a product decision explicitly changes UX.

7. Lower-priority cleanup:
   - `CSR-R1-004`: introduce `EntitlementDecision` or a normalizer.
   - `CSR-R1-003`: extract file/template creation mechanics only near focused
     creation/upload work, without a broad `ItemViewSet` rewrite.

### Items Not Worth Broad Refactors Now

- Do not merge regular Drive storage and MountProvider into one monolithic
  storage abstraction.
- Do not treat regular S3 as a MountProvider backend.
- Do not start a global toast/error-surface refactor; concrete error work is
  already covered by mount contract findings.
- Do not merge regular share and mount share routes unless a product parity
  decision changes their domain policy.

### Current Routing

`CSR-R2-001`, `CSR-R3-001`, and `CSR-R6-001` were completed locally as Dev
Lot A in report `20260708-code-structure-dev-lot-a`.

`CSR-R5-001` and `CSR-R5-002` were completed locally as Dev Lot B in report
`20260708-code-structure-dev-lot-b`.

`CSR-R1-001`, `CSR-R4-001`, and `CSR-R4-002` were completed locally as Dev
Lot C in report `20260708-code-structure-dev-lot-c`.

`CSR-R1-002` and `CSR-R2-002` were completed locally as Dev Lot D in report
`20260708-code-structure-dev-lot-d`.

`CSR-R5-003` was completed locally as Dev Lot B2 in report
`20260708-code-structure-dev-lot-b2`.

`CSR-R4-004` was completed locally as Dev Lot E in report
`20260708-code-structure-dev-lot-e`.

`CSR-R3-002` was completed locally as Dev Lot F in report
`20260708-code-structure-dev-lot-f`.

`CSR-R4-003` was completed locally as Dev Lot G in report
`20260708-code-structure-dev-lot-g`.

`CSR-R1-004` was completed locally as Dev Lot H in report
`20260708-code-structure-dev-lot-h`.

`CSR-R1-003` was completed locally as Dev Lot I in report
`20260708-code-structure-dev-lot-i`.

All code-structure findings from R1-R7 are now locally fixed or implemented in
the dirty worktree. No code-structure review finding is currently routed.

Final consolidation checkpoint `20260708-code-structure-final-consolidation-checkpoint`
passed locally: backend targeted pytest, frontend Jest, frontend lint, scoped
backend ruff, diff/whitespace checks, deprecated-login grep, and focused
Chromium E2E entitlement-disclaimers smoke all passed. The stack was left in
E2E mode after validation; run LAN QA restore commands before Mac-local browser
QA.
