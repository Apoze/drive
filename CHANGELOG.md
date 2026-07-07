# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- ✨(frontend) add contextual CTAs on public file and folder previews
- ✨(backend) add regular folder export as streaming ZIP archives
- ✨(backend) manage reconciliation requests for user accounts
- ✨(frontend) make uploads abortable and preserve empty folder drops
- ✨(backend) add entitlements usage metrics and upload disclaimers
- ✨(frontend) add explicit legacy Office conversion flow
- ✨(frontend) open WOPI previews in a dedicated tab
- ✨(frontend) add search filters by location, type, contact and date
- ✨(frontend) add configurable help menu in the left panel

### Removed

- 🔥(backend) remove mirroring feature
- 🔥(backend) drop deprecated numchild columns from item

### Changed

- 🧪(qa) add LAN auth readiness preflight before browser QA
- 🔧(nginx) serve `.mjs` frontend assets with JavaScript MIME type
- 🔧(scalingo) compile translation files at deploy time
- 🔧(project) add `DJANGO_EMAIL_URL_APP` for invitation email links
- ♻️(frontend) refresh preview controls and WOPI routing

### Fixed

- 🐛(frontend) fix "+ New" menu in read-only folders and virtual tabs
- 🐛(frontend) prevent range selection freezes on large folders
- 🐛(docker) fix Collabora healthcheck without curl

## [v0.16.0] - 2026-04-09

### Added

- ✨(frontend) add PDF viewer with thumbnail sidebar, zoom and page
  navigation
- ✨(frontend) integrate PDF viewer into file preview modal
- ✨(global) add custom columns feature with configurable grid columns
- ✨(frontend) add duplicate action and duplicating item state
- ✨(backend) add delayed purge command and cron for deleted items
- ✨(frontend) add the v0.16.0 release note
- 📝(docs) add local network setup documentation

### Changed

- 🧪(e2e) support a local gitignored token file for E2E commands
- ✨(backend) allow ordering items by size and creator full name
- 🧪(ci) add Phase 5 Chromium PR control and experiment workflow paths
- 🧪(e2e) promote local CI-like E2E default to workers=4
- 📝(docs) add the current E2E execution contract
- ✨(mounts) align the mounts explorer with the standard Drive explorer UX
- ✨(backend) new action to duplicate a file item
- 🏷️(sdk) update Item interface by adding URL fields
- 🔧(backend) allow extra CSRF origins via env variable
- 🏗️(ds-proxy) upgrade to 2.0.0-alpha.4
- 🌐(frontend) localize file size units
- ✨(frontend) display file extensions in file type columns
- 🔖(global) bump release metadata to 0.16.0

### Fixed

- 🐛(backend) fix hard delete of files created by other users
- 🐛(backend) handle race condition on concurrent LinkTrace creation
- 🐛(frontend) fix React SVG attributes in AddFolderButton
- 🐛(frontend) refresh trash rows after hard delete
- 🐛(frontend) prevent trash clicks from opening deleted content
- 🐛(frontend) keep current-folder delete from refetching deleted children
- 🐛(frontend) fix hard delete modal count and informational variant
- 🐛(mounts) align mount previews with standard viewers and streaming delivery
- 🐛(preview) keep mount previews closed after manual dismiss
- 🐛(explorer) keep item folder navigation synced with routes
- 🐛(explorer) handle partial delete, restore, hard delete, and move flows
- 🐛(mounts) converge mount and item context-menu browse actions
- 🐛(explorer) prevent desktop breadcrumb overflow in LAN browse flows
- 🧪(backend) align mount preview regression tests with current contracts
- 🧪(e2e) harden local workers=4 explorer and share stability
- 🧪(e2e) harden from-scratch readiness checks and session bootstrap
- 🐛(frontend) fix explorer and text preview scrolling
- 🐛(backend) fix hard delete of files created by other users
- 🐛(backend) handle concurrent LinkTrace creation races
- 🐛(frontend) fix toasts appearing above modals
- 🐛(frontend) match ANCT theme variants in Gaufre limits

### Security

- 🔒️(ci) restrict drive-frontend workflow token permissions
- ⬆️(backend) update requests to 2.33.0

## [v0.15.0] - 2026-03-16

### Added

- 🌐(frontend) update Dutch translation for create label
- ✨(frontend) add create folder and import file actions
- 🐛(frontend) app stabilization

### Changed

- ⚡️(CI) optimize Docker Hub workflow
- ♻️(frontend) replace WorkspaceIcon with FolderIcon in breadcrumbs
- ✨(backend) exclude pending items from listing views
- ✨(frontend) scale upload progress to 90% before completion

### Fixed

- 🐛(frontend) add action menu to mobile breadcrumbs
- 🐛(backend) allow inviting external person on item with no direct access
- 🐛(backend) stop storing numchild in database use annotation instead
- 🐛(backend) sanitize filename to be compatible with filesystems

### Removed

- 🔥(backend) remove unused ServerToServerAuthentication backend

## [v0.14.0] - 2026-02-25

### Added

- 👷(docker) add arm64 platform support for image builds
- ✨(global) add create file from template feature
- ✨(global) add FRONTEND_CSS_URL and FRONTEND_JS_URL settings
- ✨(backend) add a download action returning the media url
- ✨(frontend) add right click feature
- ✨(backend) allow customization of wopi parameters
- ✨(backend) expose DATA_UPLOAD_MAX_MEMORY_SIZE in the config endpoint
- ✨(frontend) stop upload if file higher than DATA_UPLOAD_MAX_MEMORY_SIZE
- ✨(backend) reject uploaded file higher than DATA_UPLOAD_MAX_MEMORY_SIZE

### Changed

- ✨(backend) allow root item creation on the external API by default
- ♻️(backend) set item read only in the mirror item admin detail

### Fixed

- ✨(frontend) sync backend user language to browser on load
- 🐛(frontend) fix 401 page infinite redirect loop after login
- 🐛(backend) fix OIDC redirect allowed hosts format in dev config
- 🐛(backend) fix WOPI PutFile to check stored file size
- 🐛(global) update ui when renaming file from wopi editor
- 🐛(frontend) fix clipboard copy-paste in WOPI editor iframe

## [v0.13.0] - 2026-02-18

### Added

- 🧪(e2e) ensure e2e user-auth creates a deterministic main workspace
- 🔧(ci) inject e2e s2s token via GitHub secret (DRIVE_E2E_S2S_TOKEN)
- 🧪(ci) migrate e2e to dedicated playwright runner #141
- ✨(explorer) display file extensions in lists and preview
- ✨(explorer) add zip/unzip actions (server-side)
- ✨(preview) add CodeMirror text viewer/editor for eligible text files
- ✨(explorer) unify new file creation flow (modal + OOXML editnew) #121
- ✨(archives) add archive viewer (ZIP range + multi-format) + extraction
- ✨(wopi) add "New document" actions (odt/ods/odp) in explorer
- ✨(backend) allow configuring celery task routes via `CELERY_TASK_ROUTES`
- ✨(global) implement advanced shared management system
- 📝(docs) add Docker-first self-host edge contract docs
- 📝(docs) document deterministic failure reporting schema
- 📝(docs) add Docker-first upgrade/rollback runbooks + smoke checklist updates
- 🧪(ci) add gates workflow (v1 gates wired; non-blocking on PRs)
- 🧪(ci) enforce BMAD strict mirror fingerprint check
- ✨(backend) add deterministic config_preflight edge validations
- ✨(backend) validate S3 TransferConfig multipart sizing preflight
- ✨(uploads) deterministic recovery patterns (pending TTL + retry)
- ✨(share) expose canonical public share URLs (DRIVE_PUBLIC_URL)
- ✨(share) open token-enforced public share links without auth
- ✨(wopi) add safe-by-default enablement configuration + health checks
- ✨(wopi) gate WOPI support by backend capability
- ✨(wopi) make launch flow reverse-proxy friendly (short-lived tokens)
- ✨(mounts) add validated mounts registry + enabled-only discovery
- ✨(mounts) add mounts discovery capabilities API + UI entry point
- ✨(mounts) validate SMB mount configuration schema (refs-only secrets)
- ✨(mounts) add centralized refs-only secret resolver (bounded refresh)
- ✨(mounts) prevent stale session reuse across secret rotation
  (version-bound pool)
- ✨(mounts) browse mount paths with deterministic ordering and pagination
- ✨(mounts) implement SMB MountProvider browse (stat/list)
- ✨(mounts) stream SMB mount uploads with deterministic finalize
- ✨(mounts) stream SMB mount downloads (Range supported)
- ✨(mounts) capability-gate mount action endpoints (preview/upload/wopi)
- ✨(mounts) add SMB mount preview support (capability-driven)
- ✨(mounts) create share links for mount virtual entries
- ✨(mounts) enable WOPI for mount-backed files (version/locks/streaming saves)
- ✨(wopi) disable WOPI when S3 bucket versioning is disabled
- ✨(global) add release notes
- ✨(front) show root page in breadcrumbs when navigating
- ✨(front) filter recent items to only show files
- 📈(backend) add posthog tracking to item actions
- 📈(front) add posthog tracking to share modal
- ✅(front) add e2e tests for posthog share events

### Changed

- 🚸(oidc) ignore case when fallback on email #535

### Fixed

- 🐛(oidc) align e2e OIDC issuer for backchannel calls behind nginx
- 🐛(mounts) fix mount upload Content-Type and wire mount WOPI driver calls
- 🐛(explorer) preserve file extension on rename
- 🐛(preview) align viewer routing (text/archive/unavailable)
- 🐛(preview) decode UTF-16 text previews as read-only (avoid �)
- 🐛(backend) manage ole2 compound document format
- ♻️(backend) increase user short_name field length
- 🐛(helm) reverse liveness and readiness for backend deployment
- 🐛(docker) avoid downloading mime.types at build time (CI stability)
- 🐛(docker) stabilize wopisrc base for onlyoffice in dev compose
- 🔧(media) support Range downloads via /media edge
- 🐛(wopi) fix editor launch URLs in LAN dev compose (avoid localhost)
- 🐛(mounts) enforce deterministic public mount share-link 404/410 semantics
- 🧪(uploads) add regression coverage for upload file-type allowlist edge cases

### Security

- 🔒️(backend) enforce HTTPS-only public surfaces in production
  (dev-only HTTP override)
- 🔒️(archives) protect extraction against zip-slip/path traversal
- 🔐(backend) derive split allowlists from DRIVE_PUBLIC_URL (no wildcards)
- 🔒️(nginx) internalize /media-auth and forward SigV4 headers for /media*
- 🔒️(mounts) enforce refs-only mount secret fields (config_preflight)

### Removed

- 🔥(global) remove notion of workspace
- ⚰️(scalingo) remove scalingo pgdump

### Removed

- 🔥(global) remove notion of workspace
- ⚰️(scalingo) remove scalingo pgdump

## [v0.12.0] - 2026-02-06

### Added

- 🏗️(ds_proxy) introduce how to use ds_proxy with Drive
- ✨(global) implement silent login feature and configuration integration
- ✨(global) implement external home URL redirect

### Changed

- 🔥(backend) remove usage of atomic transaction for item creation
- ♻️(backend) use sub claim instead of internal id for external anct APIs

### Fixed

- 🐛(backend) correctly configure celery beat to run wopi configuration
- 🐛(backend) fix files with # in filename causing SignatureDoesNotMatch
- 🐛(global) fix wrong language used in WOPI editor for new users

### Security

- 🔒️(backend) prevent mismatch mimetype between object storage and application

## [v0.11.1] - 2026-01-13

### Fixed

- 📌(backend) pin celery to version<5.6.0
- 🐛(backend) make extension checking case insensitive

## [v0.11.0] - 2026-01-12

### Added

- ✨(backend) add async indexation of items on save (or access save)
- ✨(backend) add throttle mechanism to limit indexation job
- 🌐(front) set html lang attribute on language change
- ✨(front) add download and preview events
- ✨(backend) add an allowed file extension list

### Changed

- ✨(api) modify items/search endpoint to use indexed items in Find
- 🐛(email) avoid trying to send emails if no provider is configured
- ♻️(backend) improve mimetype detection
- ♻️(backend) remove N+1 query patterns on items children view

### Fixed

- 🐛(scalingo) fix deploy scalingo with yarn
- 🐛(front) fix responsive gaufre
- 🐛(docker-hub) fix mistake in docker user
- 🐛(backend) stop renaming file when no title is provided
- 🐛(front) fix delete item label

## [v0.10.1] - 2025-12-05

### Security

- ⬆️(dependencies) update next to v15.4.8

## [v0.10.0] - 2025-12-04

### Added

- ✨(backend) add more info on the item detail in the admin
- ✨(backend) add an admin action to trigger new file analysis
- ✨(backend) add a command to update file_hash in malware_detection_info
- ✨(backend) enable full customization of external api

### Fixed

- 🐛(front) fix responsive item row
- 🐛(front) fix responsive tree

## [v0.9.0] - 2025-12-02

### Added

- ✨(back) add storage compute backends
- ✨(back) add claims to user
- ✨(back) add usage metrics route
- ✨(global) add entitlements
- ✨(back) add anct entitlement backend
- ✨(back) enhance items django admin

### Changed

- 🏗️(core) migrate from pip to uv

### Fixed

- 🐛(backend) manage file renaming when filename has not changed
- 🐛(backend) managed empty uploaded files
- 🐛(backend) do not allow renaming a file while not ready

## [v0.8.1] - 2025-11-24

### Fixed

- 🐛(front) fix the issue of not being able to put spaces in a folder name
- 🐛(front) heic files are not supported yet
- 🐛(front) update API error handling
- 🐛(front) enhance mimeTypes utility with known extensions and validation
- 🐛(front) fix drag leave behavior in upload zone
- 🐛(front) fix style on hover and empty grid svg
- 🐛(front) fix grid focus and keyboard navigation when a modal is open

## [v0.8.0] - 2025-11-18

### Added

- ✨(front) add disclaimer when close tab during upload
- ✨(front) add creating folder upload step
- ✨(front) update to ui-kit v2
- 🌐 add dutch translation
- ✨(back) add resource server routes
- ✨(backend) expose main workspace on /me endpoint

### Changed

- ⬆️(backend) upgrade to python 3.13

### Fixed

- 🐛(wopi) force updated_at update in the viewset
- 🐛(front) fix large uploads progress
- ♻️(back) improve uploaded ended performance
- (front) fix large uploads progress
- 🐛(front) fix upload pending items
- 🐛(back) fix search to exclude deleted child #352
- 🔧(procfile) trigger collabora configuration tasks at start #368
- 🐛(backend) filter invitation with case insensitive email
- 🐛(back) rename file on storage on renaming action
- 🐛(wopi) manage correctly renaming file operation

## [v0.7.0] - 2025-10-03

### Added

- 🔧(procfile) added celery worker on scalingo deployment #362

## [v0.6.0] - 2025-09-29

### Added

- ✨(backend) create wopi application #2
- ✨(backend) expose url_preview on item object #355
- ✨(front) add messages widget #357

### Changed

- ♻️(backend) use PUT presigned-url to upload files #345

## [v0.5.0] - 2025-09-22

### Added

- ✨(backend) search endpoint for ItemViewSet #312
- 🔧(cron) pgdump: fix restic repository #282
- 🔧(backend) support \_FILE for secret environment variables #196
- ✨(front) add search modal #326
- ✨(front) add standalone file preview #337

### Changed

- ♻️(tilt) use helm dev-backend chart
- ♻️(front) refactor tree loading #326
- ♻️(front) externalize FilePreview from EmbeddedExplorer + modalify #326

### Fixed

- 🐛(front) fix the content when opening the right panel #328
- 🐛(back) encode white spaces in item url #336

## [v0.4.0] - 2025-09-02

### Added

- ✨(back) implement lasuite.malware_detection app #212
- ✅(front) add e2e testing #317

### Changed

- 🔧(back) customize cache config #321

### Fixed

- 🐛(front) fix redirect after delete node in tree #325

## [v0.3.0] - 2025-08-25

### Added

- ✨(back) allow theme customization using a configuration file #299
- ✨(front) use theme_customization to configure the footer #299

### Fixed

- 🔧(nginx) fix trash route #309
- 🐛(front) fix workspace link react cache #310
- 🐛(backend) allow item partial update without modifying title #316
- 🌐(front) fix share item wording #315

## [v0.2.0] - 2025-08-18

### Added

- ✨(front) Add public workspaces
- ✨(front) Add 401, 403 pages
- ✨(front) Add redirect after login logic

### Changed

- ♻️(back) manage title uniqueness by generating new one if existing #296
- 🧑‍💻(docker) handle frontend development images with docker compose #298
- 🔧(project) change env.d system by using local files #298
- Bump ui-kit to remove the usage of base64 font in CSS #302

### Fixed

- 🐛(front) set the correct move icon
- 🐛(nginx) add trash route
- 💬(front) update feedback texts

## [v0.1.1] - 2025-07-30

### Fixed

- 🐛(backend) stop decreasing twice the numchild in deletion process #284
- ⚡️(backend) optimize trashbin endpoint #276
- ♻️(backend) modify sdk-relay to use DRF viewset and serializers #269

## [v0.1.0] - 2025-07-25

### Added

- 🚀 Drive, A collaborative file sharing and document management platform
- ✨(front) add move modal #213
- ✨(front) update the homepage to alpha #234
- ✨(global) add customization to feedbacks
- ✨(front) add PDF, Audio, Video, Image viewers
- ✨(front) make frontend themable
- ✨(global) Add File Picker SDK
- 🔧(cron) add pgdump cron on scalingo deployment #264
- ✨(back) implement lasuite.malware_detection app #212
- ✨(front) add grist and sqlite mimeTypes #275

### Changed

- 🐛(email) add missing email logo
- 📝(dx) fix and document how to run the project locally

### Fixed

- 🐛(i18n) fix language detection and rendering
- 🌐(front) add english translation for rename modal
- 🐛(global) fix wrong Content-Type on specific s3 implementations

[unreleased]: https://github.com/suitenumerique/drive/compare/v0.16.0...main
[v0.16.0]: https://github.com/suitenumerique/drive/releases/v0.16.0
[v0.15.0]: https://github.com/suitenumerique/drive/releases/v0.15.0
[v0.14.0]: https://github.com/suitenumerique/drive/releases/v0.13.0
[v0.13.0]: https://github.com/suitenumerique/drive/releases/v0.13.0
[v0.12.0]: https://github.com/suitenumerique/drive/releases/v0.12.0
[v0.11.1]: https://github.com/suitenumerique/drive/releases/v0.11.1
[v0.11.0]: https://github.com/suitenumerique/drive/releases/v0.11.0
[v0.10.1]: https://github.com/suitenumerique/drive/releases/v0.10.1
[v0.10.0]: https://github.com/suitenumerique/drive/releases/v0.10.0
[v0.9.0]: https://github.com/suitenumerique/drive/releases/v0.9.0
[v0.8.1]: https://github.com/suitenumerique/drive/releases/v0.8.1
[v0.8.0]: https://github.com/suitenumerique/drive/releases/v0.8.0
[v0.7.0]: https://github.com/suitenumerique/drive/releases/v0.7.0
[v0.6.0]: https://github.com/suitenumerique/drive/releases/v0.6.0
[v0.5.0]: https://github.com/suitenumerique/drive/releases/v0.5.0
[v0.4.0]: https://github.com/suitenumerique/drive/releases/v0.4.0
[v0.3.0]: https://github.com/suitenumerique/drive/releases/v0.3.0
[v0.2.0]: https://github.com/suitenumerique/drive/releases/v0.2.0
[v0.1.1]: https://github.com/suitenumerique/drive/releases/v0.1.1
[v0.1.0]: https://github.com/suitenumerique/drive/releases/v0.1.0
