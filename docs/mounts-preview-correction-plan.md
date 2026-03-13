# Mounts Preview Correction Plan

## Goal

Make `/explorer/mounts` use the same preview UX as regular Drive items
without leaking storage-specific behavior into the user experience.

This plan is intentionally complete, not minimal. The current issues are
caused by contract mismatches between:

- the shared preview modal and viewers,
- the mount browse payload,
- the mount backend preview endpoints.

## Current confirmed failures

1. WOPI mount preview crashes in React before reaching the backend editor.
   Source: [MountFilesPreview.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/mounts/components/MountFilesPreview.tsx#L49)

2. Archive preview still calls item APIs with fake mount ids.
   Source: [ArchiveViewer.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/archive-viewer/ArchiveViewer.tsx#L179)

3. PDF preview is fed with a mount API stream URL that is not equivalent to
   the normal item media preview contract.
   Sources:
   [PreviewPdf.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/pdf-preview/PreviewPdf.tsx#L29)
   [mountExplorerItems.ts](/root/Apoze/drive/src/frontend/apps/drive/src/features/mounts/utils/mountExplorerItems.ts#L116)
   [serializers.py](/root/Apoze/drive/src/backend/core/api/serializers.py#L352)
   [viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py#L4396)

4. Text preview incorrectly fetches the generic mount preview stream instead of
   using a dedicated text contract.
   Sources:
   [MountFilesPreview.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/mounts/components/MountFilesPreview.tsx#L168)
   [viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py#L4187)
   [viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py#L2644)

5. Viewer choice for mounts is currently driven by frontend MIME guessing,
   while backend previewability is decided later from real file content.
   Sources:
   [mountExplorerItems.ts](/root/Apoze/drive/src/frontend/apps/drive/src/features/mounts/utils/mountExplorerItems.ts#L58)
   [viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py#L4023)
   [viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py#L4475)

## WOPI verification

After the mount wrapper fix, there should not be another hidden `item.id`
problem in the WOPI branch, as long as we keep using the custom mount WOPI
renderer.

Why:

- the shared modal calls `renderWopiEditor(...)` before the standard
  `WopiEditor` path,
  see [FilesPreview.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/files-preview/FilesPreview.tsx#L251)
- the standard `WopiEditor` is the part that depends on `item.id`,
  see [WopiEditor.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/wopi/WopiEditor.tsx#L41)
- the current mount wrapper already calls `getMountWopiInfo({ mountId, path })`
  directly,
  see [MountFilesPreview.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/mounts/components/MountFilesPreview.tsx#L57)

So the real WOPI risk is not `item.id`; it is wrapper quality and parity with
the standard WOPI UX.

## Recommended correction order

The order below is sorted by impact first, then implementation risk.

### 1. Introduce a real mount preview resolution contract

Impact: very high
Risk: medium
Status: foundation implemented on 2026-03-11

What is now in place:

- a dedicated `preview-info` mount endpoint resolves the current file before
  viewer dispatch;
- the mount modal now consumes that resolution instead of relying only on the
  extension-based MIME guess;
- the mount modal now waits for that resolution before entering the text branch,
  so text-like extensions no longer leak into the generic mount preview stream;
- unsupported mount viewer types now fall back to the unsupported preview path
  instead of blindly entering a broken viewer branch.

Still deferred to later phases:

- mount WOPI wrapper parity;
- mount text endpoint and save path;
- inline PDF/media parity;
- archive mount mode.

Do not let the mount preview modal decide viewer type from
`guessMountMimeType()` anymore.

Instead, add a mount preview resolution step for one file at a time. That
resolution must return the real preview strategy for the selected mount file.

Recommended backend shape:

- `GET /api/v1.0/mounts/{mount_id}/preview-info/?path=...`

Recommended payload fields:

- `mimetype`
- `preview_kind`
- `is_wopi_supported`
- `can_download`
- `can_edit_text`
- `text_supported`
- `archive_supported`
- `inline_url` when iframe/media embedding is valid
- `download_url` when direct download is the only safe source

`preview_kind` should be explicit, for example:

- `image`
- `video`
- `audio`
- `pdf`
- `text`
- `archive`
- `wopi`
- `unsupported`

Why this must come first:

- it removes the current split-brain between frontend extension guessing and
  backend MIME detection;
- it prevents false positives in the UI;
- it gives every later viewer a stable source of truth.

### 2. Rebuild the mount WOPI wrapper to mirror the standard WOPI component

Impact: high
Risk: low to medium
Status: wrapper implemented on 2026-03-11

What is now in place:

- stable hook order in the mount WOPI wrapper;
- shared-style loading and retry phases for both WOPI info and iframe load;
- mount WOPI form submission only after the mount WOPI payload is ready;
- the mount WOPI branch still resolves data through `getMountWopiInfo({ mountId, path })`,
  so it stays independent from item APIs and `item.id`.

What remains outside this phase:

- mount rename semantics from WOPI postMessage events;
- any backend-side WOPI issue unrelated to the wrapper itself.

Replace the current lightweight `MountWopiEditor` with a mount-aware variant
that mirrors the structure of the shared `WopiEditor`.

Required changes:

- keep hook order stable;
- keep loading, retry, and iframe readiness states;
- keep time-bounded loading behavior aligned with the standard editor;
- submit the mount WOPI form only after data is ready;
- keep the WOPI branch completely independent from `item.id`.

Important note:

- this branch does not need item APIs after the wrapper is fixed;
- rename notifications are a separate concern.

If rename from the WOPI editor must behave like normal items, add it only if
mount rename semantics and APIs are already defined. Otherwise keep rename out
of scope and make that divergence explicit.

### 3. Add a dedicated mount text endpoint and text save path

Impact: high
Risk: medium
Status: endpoint and frontend plumbing implemented on 2026-03-11

What is now in place:

- `GET /api/v1.0/mounts/{mount_id}/text/?path=...`
- `PUT /api/v1.0/mounts/{mount_id}/text/?path=...`
- mount preview resolution can now return `preview_kind = text`
- the `preview-info` text branch now resolves correctly for markdown-like files
  without crashing on an undefined provider I/O capability lookup
- the shared preview policy is now aligned between mounts and items:
  `.txt` prefers WOPI when available, while other text files stay on the
  shared text viewer
- mount text previews no longer depend on the generic mount preview stream
- the shared preview modal can now save mount text through a mount-specific
  save hook instead of forcing `saveItemText(itemId)`

Current contract:

- text eligibility mirrors the item text rules closely;
- decoding, truncation, read-only flags and `ETag` are returned in the same
  payload shape as item text;
- editing is enabled only when the mount provider supports `open_write` and the
  file encoding is safely editable.

The current mount text preview uses the generic mount preview stream, which is
the wrong contract.

Add a dedicated endpoint similar to item text:

- `GET /api/v1.0/mounts/{mount_id}/text/?path=...`
- `PUT /api/v1.0/mounts/{mount_id}/text/?path=...` if mount text editing must
  match normal item UX

It should mirror the item text behavior in
[viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py#L2335):

- text eligibility rules;
- bounded sniffing for generic MIME types;
- encoding detection;
- truncation;
- read-only vs editable state;
- `ETag` and `If-Match` for safe writes.

Frontend follow-up:

- stop using `url_preview` for mount text;
- add a mount-specific save hook/path, not just a mount-specific fetch hook;
- remove the remaining `saveItemText(itemId)` assumption in the shared modal,
  see [FilesPreview.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/files-preview/FilesPreview.tsx#L183)
- make the cache key and save path fully pluggable for mount text.

Without that last point, read-only text may work, but full parity will still be
broken when editing is introduced.

### 4. Provide a proper inline preview surface for mount PDF and media

Impact: high
Risk: medium to high
Status: inline preview surface implemented on 2026-03-11

Do not iframe the generic DRF mount preview action directly for PDF.

The normal item preview path uses a media preview URL, not the API action
directly:
[serializers.py](/root/Apoze/drive/src/backend/core/api/serializers.py#L352)

For mounts, create a dedicated inline preview surface with the same class of
contract as normal item previews:

- embeddable in iframe when needed;
- compatible with the browser PDF viewer;
- correct security headers for inline rendering;
- optional `Range` support for large files if needed.

Good practice options:

1. Preferred: create a media-like mount preview URL and return it from
   `preview-info`.
2. Acceptable fallback: fetch the PDF bytes client-side and render a `blob:`
   URL, but this is weaker for large files and should not be the long-term
   contract.

What is now in place:

- mounts expose a dedicated `inline-preview` action for iframe/media
  consumption;
- `preview-info` now returns that URL for image, audio, video and PDF;
- the inline endpoint keeps `Range` support when the provider exposes it;
- PDF no longer depends on the old generic API preview route that was not safe
  to iframe.

This phase now covers image/audio/video/PDF consistency so every mount media
viewer uses the same contract family.

### 5. Make archive preview storage-aware

Impact: medium
Risk: medium
Status: transitional mount-aware archive preview implemented on 2026-03-11

`ArchiveViewer` is not item-agnostic today. It mixes:

- archive file access by URL,
- item metadata loading by `item.id`,
- archive extraction actions that target item APIs.

For mount archives:

- keep client-side listing/preview from the file URL;
- remove or bypass `useItem(fakeId)`;
- hide extraction actions until there is a true mount archive extraction
  contract;
- do not call the current item extraction API with mount ids.

What is now in place:

- mount `preview-info` can now resolve ZIP/TAR-like files as `archive`;
- mounts reuse the shared `ArchiveViewer` for client-side listing/preview;
- mounts now force the downloaded/libarchive archive backend instead of the
  ZIP range backend used by item media URLs;
- fake `item.id` lookups are bypassed for mount archives;
- extraction actions are hidden for mounts until a real source-mount archive
  extraction contract exists.
- the mount API CORS contract now exposes `Range`/`Content-Range` style headers,
  but the archive preview still deliberately uses the downloaded backend for
  mounts because the item media path and the mount API path do not behave
  equivalently enough for reliable ZIP-range browsing.

This phase fixes correctness and UX continuity, but it is explicitly not the
final large-archive architecture for mounts.

Important architecture note:

The existing mount archive extraction endpoint in
[viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py#L4751)
extracts a regular Drive item archive into a mount destination. It does not
extract an archive that itself lives on the mount.

So if full parity is required for mount zip extraction, a new backend contract
is needed, for example:

- `POST /api/v1.0/mounts/{mount_id}/archive-extractions/`
  with source `path` and destination `path`

That is a separate feature, not a frontend-only fix.

### 6. Introduce a browser-grade mount streaming contract

Impact: very high
Risk: medium to high
Status: planned

Current problem:

- the current mount API endpoints are good enough for normal downloads and
  basic inline preview;
- they are not equivalent to the item media pipeline used by `my-files`;
- large ZIP preview on mounts still falls back to full download because the
  browser-facing contract is not stable enough for ZIP range readers.

This must be solved at the storage integration layer, not by adding more
frontend workarounds.

Target outcome:

- a stable URL dedicated to browser streaming;
- `HEAD`, `GET`, and `Range` requests supported explicitly;
- strict `206` and `416` behavior;
- the right response headers exposed to the browser;
- short-lived auth that works with iframes, media tags, workers, and direct
  browser fetches;
- the same class of contract for every mount provider, even if their internal
  storage mechanics differ.

Best-practice architecture:

- keep `MountProvider` responsible for storage access primitives and metadata;
- keep browser auth, HTTP semantics, and caching policy in a core streaming
  layer above providers;
- allow providers to optionally expose a native browser-stream target later,
  but make the default contract work through a generic proxy stream path.
- prefer a same-origin delivery path in deployed environments when possible,
  while still keeping the contract valid in split-origin development setups.

Recommended backend shape:

- `POST /api/v1.0/mounts/{mount_id}/stream-tickets/`
  or a deterministic equivalent, with at least:
  - `path`
  - `disposition` (`inline` or `attachment`)
  - `purpose` (`preview`, `download`, `archive`)
- response payload:
  - `stream_url`
  - `expires_at`
  - `etag`
  - `content_type`
  - `content_length`
  - `supports_range`

- `HEAD|GET /api/v1.0/mount-stream/{token}`
  as a dedicated browser-stream endpoint.

Recommended token contents:

- `mount_id`
- `normalized_path`
- `user`
- `version` (for example `compute_mount_entry_version(entry)`)
- `disposition`
- `purpose`
- expiry timestamp

Why a tokenized stream URL is the right design:

- browser primitives like iframe, media tags, and web workers need a stable URL;
- session-bound DRF actions are a poor fit for this usage pattern;
- short-lived tokens avoid exposing long-lived session cookies to every
  browser-side fetch path;
- binding the token to a file version prevents stale preview/download streams
  after a file changes.
- an opaque ticket modeled after the existing WOPI access-token pattern fits the
  current backend architecture better than leaking provider-native credentials
  to the browser.

HTTP contract requirements:

- `HEAD` returns accurate `Content-Length`, `Content-Type`, `ETag`,
  `Last-Modified`, and `Accept-Ranges` when available;
- the `GET + Range` path must be sufficient on its own for archive browsing,
  because the current ZIP worker is already capable of avoiding an explicit
  `HEAD` request;
- `GET` without `Range` returns `200`;
- `GET` with valid `Range` returns `206` with `Content-Range`;
- invalid or unsatisfiable ranges return `416` deterministically;
- the initial contract only needs to guarantee single byte-range requests
  correctly; multipart byteranges can stay out of scope until a real client
  requires them;
- `Content-Disposition` is controlled by the ticket (`inline` vs `attachment`);
- stream responses must preserve byte identity for ranged reads:
  no on-the-fly gzip/transcoding/content rewriting on the streamed payload;
- CORS must allow `Range` and expose:
  - `Accept-Ranges`
  - `Content-Range`
  - `Content-Length`
  - `Content-Disposition`
  - `ETag`
- inline responses must not be blocked by clickjacking middleware when they are
  intentionally embedded in the product UI.
- invalid, expired, or revoked tickets must fail with deterministic non-HTML
  responses; never redirect a browser stream request to a login page.
- cache policy should be explicit and conservative for bearer-style stream URLs,
  for example `Cache-Control: private, no-store, no-transform`, unless a future
  product requirement justifies a different cache model.

Operational constraints:

- ticket creation must normalize the mount path before signing or caching any
  access context;
- the stream endpoint should re-check that the user still has access to the
  mount and path, not just trust that ticket issuance happened earlier;
- token TTL should be short enough for browser usage and revocation risk, but
  long enough to survive normal preview sessions and range re-requests;
- logs and analytics must avoid storing raw bearer tokens in clear text.

MountProvider evolution (recommended `v2` contract direction):

- formalize browser-streaming capability instead of relying only on the ad hoc
  `supports_range_reads(...)` helper;
- keep `stat(...)` and `open_read(...)` as the baseline generic interface;
- require that providers declaring browser-stream support expose a seekable read
  surface suitable for deterministic ranged reads;
- optionally add a provider hook for native streaming when a backend can mint
  its own short-lived URL efficiently.

Recommended provider capability model:

- `browser_stream_mode = "proxy" | "native" | "none"`
- `supports_random_access = true | false`
- `supports_head_metadata = true | false`
- `supports_stable_version = true | false`

How this maps to providers:

- SMB should use the generic proxy browser-stream path backed by seekable reads;
- `localfs` should use the same proxy path by default;
- a future object-storage mount provider may choose `native` and return a
  short-lived signed URL instead of proxying through Django.

Acceptance criteria for this phase:

- a large ZIP under `/explorer/mounts` opens through the ZIP range backend
  without falling back to full file download;
- browser traces show `206` responses for range reads on mount stream URLs;
- `HEAD` on a mount stream URL returns stable metadata for the current file
  version;
- expired tickets fail cleanly without HTML redirects;
- a changed file version invalidates the old ticket deterministically and forces
  the UI to refresh preview metadata;
- PDF, image, audio, and video previews all consume the same `stream_url`
  contract family.

Explicit non-goals for this phase:

- exposing SMB credentials or provider-native secrets to the browser;
- forcing every provider to implement its own browser HTTP surface on day one;
- keeping the current full-download archive fallback as the long-term design.

Frontend follow-up after this phase:

- `preview-info` should return `stream_url` for previewable binary/media files;
- mount archive preview should go back to the ZIP range backend when
  `stream_url` is available and trustworthy;
- mount download buttons should eventually use the same browser-stream contract
  instead of the current session API route;
- the forced downloaded/libarchive mount archive fallback should then be
  removed.
- worker/browser consumers should be able to use the stream URL without relying
  on session cookies; if the current code still sends `credentials: include`,
  it should remain compatible during migration but stop being a hard
  requirement.
- the ZIP worker path should be updated to prefer ticketed stream URLs while
  keeping its current `single-range` request pattern.

Migration strategy:

1. Introduce a `MountStreamAccessService`, mirroring the WOPI mount access
   token pattern.
2. Implement a dedicated browser-stream endpoint above the provider layer.
3. Wire `preview-info` to return `stream_url` from that service.
4. Migrate PDF/media viewers to `stream_url`.
5. Switch mount archive preview back to ZIP range mode when `stream_url`
   advertises strict range support.
6. Keep the current download/inline-preview actions for compatibility during
   migration, then deprecate their use in the preview UI.

Concrete implementation breakdown for this phase:

1. Backend access-token service
   Files:
   [access.py](/root/Apoze/drive/src/backend/wopi/services/access.py)
   New file to add alongside it, preferably under
   `src/backend/core/services/mount_stream_access.py`

   Work:
   - create a dedicated access-context dataclass for browser streams:
     `mount_id`, `normalized_path`, `user`, `version`, `disposition`,
     `purpose`, expiry;
   - mirror the WOPI token lifecycle, but keep it in `core` because this is not
     WOPI-specific;
   - centralize path normalization and ticket serialization there;
   - keep token generation opaque and short-lived.

2. Provider contract evolution
   Files:
   [base.py](/root/Apoze/drive/src/backend/core/mounts/providers/base.py)
   [smb.py](/root/Apoze/drive/src/backend/core/mounts/providers/smb.py)
   [localfs.py](/root/Apoze/drive/src/backend/core/mounts/providers/localfs.py)
   [static.py](/root/Apoze/drive/src/backend/core/mounts/providers/static.py)
   [registry.py](/root/Apoze/drive/src/backend/core/mounts/registry.py)

   Work:
   - replace the ad hoc `supports_range_reads(...)`-style capability probing
     with an explicit capability surface or helper returning:
     `browser_stream_mode`, `supports_random_access`,
     `supports_head_metadata`, `supports_stable_version`;
   - keep `open_read(...)` as the baseline generic proxy-stream primitive;
   - require proxy-stream-capable providers to expose a seekable file handle;
   - let `static` default to `none` or to a deterministic test-only mode;
   - keep the registry-level provider contract backward-compatible during the
     migration if needed through adapter helpers.

3. Mount stream endpoint and serializers
   Files:
   [serializers_mounts.py](/root/Apoze/drive/src/backend/core/api/serializers_mounts.py)
   [viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py)
   [urls.py](/root/Apoze/drive/src/backend/core/urls.py)

   Work:
   - add a request/response serializer for stream ticket creation;
   - add a serializer shape for the ticket payload returned to the frontend;
   - expose `POST /api/v1.0/mounts/{mount_id}/stream-tickets/`;
   - expose a dedicated tokenized route such as
     `HEAD|GET /api/v1.0/mount-stream/{token}/`;
   - prefer implementing `mount-stream/{token}` as a dedicated view route in
     [urls.py](/root/Apoze/drive/src/backend/core/urls.py), not as an action on
     `MountViewSet`, because it is no longer scoped by mount id in the URL and
     must behave like a stable browser resource;
   - move the strict `Range` parsing/`206`/`416` logic into shared helpers so it
     is not duplicated again across `inline-preview`, `download`, and the new
     stream endpoint.

4. Viewset/service integration
   Files:
   [viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py)
   [mount_security.py](/root/Apoze/drive/src/backend/core/services/mount_security.py)

   Work:
   - issue stream tickets only after mount existence, capability, and file
     checks pass;
   - resolve the provider and current entry metadata at ticket issuance time;
   - bind the ticket to `compute_mount_entry_version(entry)` so file mutations
     invalidate old tickets;
   - on stream consumption, re-check mount availability and user access before
     reading bytes;
   - return deterministic JSON/API errors for ticket issuance failures and
     deterministic non-HTML responses for stream-consumption failures.

5. `preview-info` contract migration
   Files:
   [serializers_mounts.py](/root/Apoze/drive/src/backend/core/api/serializers_mounts.py)
   [viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py)
   [types.ts](/root/Apoze/drive/src/frontend/apps/drive/src/features/drivers/types.ts)

   Work:
   - extend `MountPreviewInfo` with `stream_url` and eventually
     `stream_expires_at`;
   - keep `inline_url` and `download_url` during migration, but treat them as
     compatibility fields;
   - make `preview-info` return `stream_url` for PDF, image, audio, video, and
     archive candidates once the backend contract is ready.

6. Frontend driver plumbing
   Files:
   [Driver.ts](/root/Apoze/drive/src/frontend/apps/drive/src/features/drivers/Driver.ts)
   [StandardDriver.ts](/root/Apoze/drive/src/frontend/apps/drive/src/features/drivers/implementations/StandardDriver.ts)
   [types.ts](/root/Apoze/drive/src/frontend/apps/drive/src/features/drivers/types.ts)

   Work:
   - add typed support for `stream_url` in the driver contracts;
   - optionally add a dedicated `createMountStreamTicket(...)` driver method if
     ticket minting is not folded into `preview-info`;
   - keep the frontend insulated from provider-specific streaming differences.

7. Shared preview consumers
   Files:
   [MountFilesPreview.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/mounts/components/MountFilesPreview.tsx)
   [FilesPreview.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/files-preview/FilesPreview.tsx)
   [PreviewPdf.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/pdf-preview/PreviewPdf.tsx)
   [AudioPlayer.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/audio-player/AudioPlayer.tsx)
   [VideoPlayer.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/video-player/VideoPlayer.tsx)
   [ImageViewer.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/image-viewer/ImageViewer.tsx)

   Work:
   - prefer `stream_url` over `inline_url` for mount binary/media previews;
   - keep viewer components storage-agnostic by passing them a final resolved
     URL, not mount-specific branching logic;
   - make sure iframe/media/embed consumers work with bearer-style token URLs
     and do not rely on redirects or cookie-only auth.

8. Archive preview migration back to true range
   Files:
   [ArchiveViewer.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/archive-viewer/ArchiveViewer.tsx)
   [zip.worker.ts](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/archive-viewer/workers/zip.worker.ts)
   [MountFilesPreview.tsx](/root/Apoze/drive/src/frontend/apps/drive/src/features/mounts/components/MountFilesPreview.tsx)

   Work:
   - switch mount archives from the downloaded/libarchive backend back to the
     ZIP `HttpRangeReader` backend when `stream_url` is present;
   - keep the worker aligned with the real contract it needs today:
     `single-range` reads with no mandatory `HEAD`;
   - remove the current mount-specific archive fallback only after large ZIPs
     prove reliable on the ticketed stream path.

9. CORS, headers, and clickjacking policy
   Files:
   [settings.py](/root/Apoze/drive/src/backend/drive/settings.py)
   [viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py)

   Work:
   - expose the browser-visible headers needed by media tags and range readers;
   - ensure stream responses are not compressed or transformed in a way that
     breaks byte-accurate range reads;
   - keep inline embedding explicitly exempted only on the dedicated browser
     stream surface, not more broadly than necessary.

10. Test breakdown
    Files:
    `src/backend/core/tests/mounts/` new focused tests for stream tickets and
    stream responses
    [previewRules.test.ts](/root/Apoze/drive/src/frontend/apps/drive/src/features/ui/preview/files-preview/__tests__/previewRules.test.ts)
    E2E specs under `src/frontend/apps/e2e/__tests__/app-drive/`

    Work:
    - backend:
      ticket issuance, token expiry, version invalidation, `HEAD`, `GET`,
      `Range`, `206`, `416`, no HTML redirects;
    - frontend:
      preview contract typing and URL selection;
    - E2E:
      large ZIP from mount opens through the range backend and does not trigger
      a full-file archive download path.

### 7. Refactor the shared modal API around preview strategies

Impact: medium
Risk: medium
Status: `PreviewSource` refactor and adapter cleanup implemented on 2026-03-11

The shared modal has already grown mount-specific escape hatches:

- `fetchTextContent`
- `getTextQueryKey`
- `renderWopiEditor`

That works for bootstrapping, but it will fragment as soon as PDF, archive, and
text save need custom behavior too.

Recommended direction:

- define a `PreviewStrategy` or `PreviewSource` object for the current file;
- let shared viewers consume a normalized contract instead of ad hoc props;
- keep the modal shell shared;
- keep storage-specific behavior behind resolvers/adapters.

What is now in place:

- the shared `FilePreview` now consumes a single `source` contract instead of
  multiple mount-specific escape hatches;
- the default item preview path uses a standard preview source;
- the mount preview path now plugs in a mount preview source responsible for
  text fetch/save, preview resolution, WOPI rendering, and archive rendering;
- resolved preview caching and `stream_url` reuse now live in a dedicated shared
  hook instead of being open-coded inside the modal body;
- the mount-specific preview adapter now lives in its own module instead of
  keeping WOPI/text/archive strategy code inside the mount page component;
- `stream_url` reuse policy stays inside the shared preview layer instead of
  being reimplemented per storage integration.

This refactor should happen before adding more one-off mount props.

### 8. Tighten browse/preview capability semantics

Impact: medium
Risk: low to medium
Status: browse-level preview semantics tightened on 2026-03-11

The current browse payload advertises `preview` for any readable file when the
mount preview capability is enabled:
[viewsets.py](/root/Apoze/drive/src/backend/core/api/viewsets.py#L4023)

That is too coarse for UX parity because the file may still fail later after
MIME detection.

Best practice:

- keep browse abilities coarse if provider cost makes per-file detection too
  expensive;
- but let `preview-info` become the final source of truth before a viewer is
  chosen;
- surface unsupported states inside the modal in a controlled way, not as raw
  network failures.

What is now in place:

- mount browse abilities no longer advertise `preview` for obviously
  non-previewable binary filenames;
- cheap filename-level heuristics now keep preview available for obvious text,
  media, PDF, archive, and WOPI-backed files without doing provider-content
  sniffing during browse;
- mounts UI actions now respect `abilities.preview` instead of showing a
  preview action unconditionally.

## Test and verification plan

Do not rely on a single mount E2E once this is implemented. Cover the contract
by layer.

### Frontend

- unit tests for mount preview strategy resolution;
- component tests for mount WOPI, text, PDF, and archive branches;
- regression test that mount WOPI never calls item APIs.

### Backend

- tests for `preview-info`;
- tests for mount text `GET` and `PUT`;
- tests for inline PDF/media preview headers and allowed rendering behavior;
- tests for browser-stream tickets and token expiry;
- tests for `HEAD`, `GET`, `Range`, `206`, and `416` on the browser-stream
  endpoint;
- tests that the browser-stream endpoint never redirects to HTML auth flows;
- tests that version-bound tickets fail after the underlying file changes;
- tests for unsupported mount file handling with deterministic error codes.

### E2E

Targeted Chromium scenarios are enough for the feature pass:

- open image preview from mount;
- open WOPI file from mount;
- open PDF from mount;
- open text file from mount and scroll;
- open zip from mount and browse entries;
- open a large zip from mount and verify that the browser-stream contract is
  used instead of a full archive download fallback;
- verify no navigation away from `/explorer/mounts/[mount_id]`.

## Recommended implementation sequence

1. Mount preview resolution contract
2. WOPI wrapper rebuild
3. Mount text endpoint plus frontend save/fetch plumbing
4. Inline PDF/media preview contract
5. Archive viewer mount mode (transitional workaround)
6. Browser-grade mount streaming contract
7. Shared modal strategy refactor
8. Coverage and regression locks

This sequence reduces rework. If phases 2 to 5 are done before phase 1, the
same preview-routing mistakes are likely to come back in a different form.
