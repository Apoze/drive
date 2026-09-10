# Agent Storage Contract

This is the long-form storage, MountProvider, streaming, WOPI, and archive
extraction contract for agents working in the Apoze Drive fork.

`AGENTS.md` keeps only the short version so Codex project instructions stay
under the default discovery budget.

## Storage Families

Governed storage and ST homelab operations are documented in
`docs/homelab-storage-operations.md`. Quota ownership is independent of views
and NAS credentials. Keep publication journals and active reservations intact
when reconciling external changes or recovering interrupted operations.

The unified spaces, multi-S3 and web administration work is specified
in [the storage plan](plans/storage/unified-storage-spaces-plan.md).
Implementation and local qualification are complete; deployment on the
operator's persistent infrastructure remains separate.
Check the [execution status](../output/implementation/unified-storage-spaces/current-status.md)
before assuming a planned capability is complete or qualified.

Space group grants use the existing Django groups, with a stable `group:<id>`
principal. Names are display labels; renaming a group preserves its grants.
Membership is managed in Drive's user administration, independently of quota
ownership and NAS accounts. Do not infer membership from unconfigured OIDC
claims. Revalidating a user clears cached membership; Item and native grant
caches include the membership set so a revoked member cannot keep access
during a long operation. Delegates discover their own groups and groups already
granted to their space; instance administrators can search all local groups.

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

The default S3 storage also routes key-only integration reads through the
Item's explicit connection. Its registered Item reads expose an S3 stream;
callers needing seeks must stage to bounded temporary storage. Malware
reports for explicit locations carry the observed connection/key/version.
A report for replaced bytes must not change the current Item's safety state.

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

### Unified transfer source retention

After an S3 move, the logical Item and quota switch together. Original bytes
remain journaled until the configured retention period expires. Cleanup checks
current source-scope write permission, destination access, connection generations,
editing locks and the destination checksum. It deletes only the captured,
non-null S3 `VersionId`; an unversioned source remains explicitly retained.
A replacement at the former source key is never selected by a path-only delete.
The periodic storage task revisits retained transfer jobs in bounded batches.

This relies on native version-specific deletion, as documented in
[AWS DeleteObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_DeleteObject.html).
The versioned S3 fixture checks retention, revocation, replacement and loss of
the deletion response without removing the replacement or charging it twice.

### Nested S3 spaces and historical limits

A logical subtree has one accounting space (its deepest allocated root), with
all ancestor space budgets applied to its files. Access grants belong to views
and may authorize descendants whose accounting space is different. Reclassify
existing trees under maintenance before permitting writes.

ST resource policies use connection namespaces, including migrated S3 roots.
The historical `backend:s3` and user-S3 limits remain additional compatibility
ceilings; organization policies must never overwrite those shared accounts.
The repeatable migration adds namespace scopes without dropping those ceilings.


### Unified archives and document producers

- Native document creation uses the existing ODF/OOXML templates and governed
  mount writer, without creating a placeholder S3 Item.
- Native legacy Office conversion uses ONLYOFFICE, then the copy publication
  journal. Keep the source observation separate from output size and checksum.
  The converter must read WOPI before taking exclusive namespace locks.
- ZIP creation captures an authorized resource manifest; source changes or
  revoked access prevent publishing an unverified result. Metadata is bounded.
- ZIP/TAR extraction validates paths, entry counts, sizes and special-file types
  before creating the destination. The ZIP central directory is capped at
  32 MiB before stdlib allocation; TAR sizes are checked before body skipping.
  Full and selected extraction use the same authorized destination picker.
- Extracted directories and file journals resume independently in passes of
  at most 20 entries. Never adopt or overwrite an unrelated existing directory.
  An interrupted member resumes through its parent extraction.
- Native extraction still requires `MOUNTS_SAFE_FOR_ARCHIVE_EXTRACT=true` and
  the provider's protected publication methods. The API and worker enforce it.
- Folder exports use bounded metadata and streaming reads. Public exports
  recheck the current share before entry reads; direct NAS access never grants
  a public caller broader access than the shared subtree.

### Native Docs documents

An Item of type `docs` is a logical document, not a storage object. Its
`DocsBinding` points to the native Docs UUID and optionally a stable mounted
folder. Never route it through S3 upload, WOPI, binary conversion or provider
file reads. Docs owns its private Yjs/media/version bytes; Drive owns placement,
access and lifecycle. Exports are separate files using the existing publication
and quota guards. Document content must not consume a NAS connection's physical
quota merely because its logical entry appears in that connection's space.

See [ADR 0004](adr/0004-docs-drive-native-documents.md) and the
[execution plan](plans/suite/docs-drive-native-documents-integration-plan.md).
Integration is enabled on the LAN. Current validation and deployment evidence
are recorded in the plan. Document invitation acceptance requires the verified
email in the current IdP session proof, never a stale local profile. The email
does not identify or merge the durable People principal.

My Files reuses AppExplorer with the home resource collection: SQL pagination,
filters and standard item actions include authorized S3 entrances and mounted
roots. Historical S3 allocations rooted in a file remain visible as files;
folder destination pickers exclude them. Do not replace the explorer with a
separate mount catalogue or change legacy storage allocations to repair UI.
