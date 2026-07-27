# Agent Storage Contract

This is the long-form storage, MountProvider, streaming, WOPI, and archive
extraction contract for agents working in the Apoze Drive fork.

`AGENTS.md` keeps only the short version so Codex project instructions stay
under the default discovery budget.

## Storage Families

S3 and MountProvider are separate storage families:

- S3-backed regular Drive items use Django Storage and S3/S3-compatible APIs.
- MountProvider exposes filesystem-like providers such as SMB, localfs, and
  future providers.
- S3 is not a MountProvider backend.

Any feature or fix touching files must remain compatible with both families
when safe and supportable:

- read/write
- preview/viewers
- conversion
- archive/extract
- search
- upload/download
- WOPI/editing

## No Local Path Assumption

Django Storage backends may not implement `path()`. Object storage often does
not expose local paths.

Rules:

- Prefer Storage API methods: `open`, `save`, `exists`, and related APIs.
- Do not call `storage.path()` unless an explicit `fs.local_path` capability is
  true for that backend.
- Do not assume `storage.url()` is supported or directly usable. It may raise
  `NotImplementedError` or require signed URLs.
- Frontend code should prefer application endpoints that enforce auth,
  streaming, and caps uniformly.

## S3-Specific APIs

Low-level S3/boto usage is S3-only, for example:

- `default_storage.connection.meta.client`
- direct boto client calls
- S3 signed URL internals

Rules:

- Encapsulate S3-specific logic in a dedicated S3 service.
- Never require S3 internals from a path intended to work with MountProvider.
- Shared user-visible features must go through Storage API for regular items or
  Provider API for mounts.

## MountProvider Transparency

Backend and frontend behavior must not depend on the provider brand behind
MountProvider.

Allowed:

- capability checks
- mount config flags
- provider-agnostic API contracts
- controlled degradation when a capability is missing

Forbidden:

- branching on "SMB vs other provider"
- provider-specific user-facing messages
- dangerous fallbacks that make unsupported features appear to work
- unbounded full downloads into RAM

Provider-specific operational details belong in admin docs, not end-user
messages.

## Capability Contract

Capabilities are the source of truth for backend decisions and UI abilities.
Keep names consistent:

- `io.read_stream`
- `io.write_stream`
- `io.range_read`
- `io.listdir`
- `fs.local_path`
- `fs.atomic_rename`
- `security.safe_for_archive_extract`
- `wopi.putfile_streaming`

Current mount capabilities may come from:

- mount config flags such as `mount.upload`, `mount.preview`, `mount.wopi`,
  `mount.share_link`
- provider method support such as `open_read`, `open_write`, `rename`,
  `remove`, or range-read support

Target direction:

- centralize capability resolution
- derive UI-facing abilities from the resolver
- progressively replace scattered `hasattr()`/duck-typing decisions

## Functional Parity Rule

If an upstream or local change is a real user-visible file capability
improvement for regular Drive items, explicitly assess MountProvider parity.

Expected outcomes:

- implement equivalent MountProvider support when safe and capability-backed
- or hide/disable/degrade the feature through capabilities
- or record an explicit orchestrator/user decision to defer parity

Do not consider a feature lot complete just because regular item/S3 behavior is
implemented if MountProvider parity is feasible and expected.

## Streaming And Memory

Rules:

- Avoid loading entire files into memory.
- Prefer streaming reads and writes.
- Keep large zip/unzip/conversion operations server-side and async where
  needed.
- Frontend preview should avoid `response.blob()` for file display. Prefer a
  direct `src` pointing to a streaming URL.
- Archive viewer must require range support or strict caps. Do not fall back to
  unbounded full-archive downloads.

## WOPI PutFile

WOPI PutFile must stream the request body in chunks.

Mandatory rules:

- Do not use `request.body`.
- Do not trigger DRF parsing through `request.data` or `request.POST`.
- Read the request stream only once.
- Tests should prove that `request.body` is not required, there is no
  double-read, and DRF parsers are not invoked.

Django/DRF pitfall:

- reading the stream and then accessing `request.body` can raise
  `RawPostDataException`

## Mount Archive Extraction Hardening

Server-side archive extraction to MountProvider filesystem-like backends is
allowed only when the backend is hardened against path traversal, symlink
escape, or reparse-point escape.

Global safety gate:

- refuse extraction unless `MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT=true`
- S3/object storage is not affected by this env var

Refusal message:

- `Mount is not hardened for archive extraction (hardening required)`

Stable backend error code:

- `MOUNT_ARCHIVE_EXTRACT_UNSAFE`

Recommended structured error fields:

- `status`
- `title`
- `detail`
- `error_code`
- `request_id`

Recommended header:

- `X-Error-Code: MOUNT_ARCHIVE_EXTRACT_UNSAFE`

Frontend display:

- `Extraction not allowed: the mount is not safe for archive extraction.`
- support/admin line:
  `Reference: MOUNT_ARCHIVE_EXTRACT_UNSAFE - Request-ID: <id>`

The frontend must read `error_code` and `request_id` from the backend. It must
not invent or remap codes.

## SMB Hardening Example

SMB/Samba/TrueNAS is only the current example. The rule is provider-agnostic.

Required Samba/TrueNAS hardened profile:

- share:
  - `follow symlinks = no`
  - `wide links = no`
- global:
  - `allow insecure wide links = no`

Do not enable `allow insecure wide links` for mounts intended for extraction.
If symlink traversal is required for a share, that share is not eligible for
server-side archive extraction in Drive.

## Testing Expectation

For file features, cover both storage families when possible:

- regular items/S3 object storage with no local path assumption
- MountProvider filesystem semantics

If full automated coverage is not feasible, document a focused manual test
plan and the capability/degradation reasoning.
