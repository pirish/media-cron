# Feature Specification: Torrent Client Integration for Ingestion and Seeding Management

**Feature Branch**: `002-torrent-client-integration`

**Created**: 2026-09-07

**Status**: Draft

**Input**: User description: "Ingest pipeline should support interacting with torrent clients (qbitorrent, transmission, deluge ) directly, as well as monitoring folders. For seeding, pipeline should support interacting with files directly as well as moving them via torrent clients. for torrent clients, focus primarily on qbittorent but others should be supportable via plugins"

## Clarifications

### Session 2026-09-07

- Q: How should media-cron transfer completed torrent files from the client download path into the staging directory during ingestion? → A: Always copy files into staging (providing maximum isolation so the original torrent payload remains completely untouched during processing).
- Q: When using torrent-client-managed relocation for seeding, what target directory should media-cron instruct the client to move the torrent payload to? → A: Configurable per client/profile (supports either a dedicated seed directory or final library path).
- Q: How should media-cron handle non-media clutter (such as .nfo, sample clips, and release text files) that is part of an active seeding torrent payload? → A: Retain clutter in client seeding storage for tracker verification; exclude clutter from the final media library.
- Q: What identifier should media-cron accept when a torrent client completion hook triggers targeted ingestion for a single torrent? → A: Accept either torrent hash or torrent name (hash preferred for uniqueness, falling back to name lookup).
- Q: By default, how should media-cron track completion status in the torrent client to ensure idempotent processing across recurring runs? → A: Dual update (applies a completion tag AND re-categorizes the torrent to a configured post-processing category).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Direct Ingestion from qBittorrent (Priority: P1)

A media automation operator wants media-cron to connect directly to their qBittorrent client, inspect downloaded torrents, identify completed media payloads matching configured categories or tags, and bring them into the staging pipeline without requiring manual file exports or external staging scripts.

**Why this priority**: Core ingestion capability. Connecting directly to the primary torrent client (qBittorrent) allows media-cron to ingest downloads immediately upon completion while verifying that only fully completed downloads are processed.

**Independent Test**: Configure a qBittorrent connection with a completed download tagged for processing; execute media-cron ingestion; verify that the completed payload is identified, mapped to the staging area, and prepared for organization without touching incomplete torrents.

**Acceptance Scenarios**:

1. **Given** a connected qBittorrent instance containing a 100% completed torrent with the configured category or tag, **When** ingestion is triggered, **Then** media-cron identifies the torrent payload, translates its download path to the local staging path, copies the media files into the staging directory for processing, and leaves the original download payload intact for continuous seeding.
2. **Given** a connected qBittorrent instance containing active torrents with download progress under 100% (or in downloading/allocating state), **When** ingestion is triggered, **Then** the incomplete torrents are skipped and left untouched.
3. **Given** an individual torrent identifier passed via completion trigger (supporting either a unique torrent hash or a torrent name), **When** targeted ingestion is executed, **Then** media-cron resolves the target torrent (matching by hash first, with name lookup fallback) and processes only the specified torrent rather than performing a full client sweep.
4. **Given** a qBittorrent instance running inside a container or remote host where download paths differ from media-cron's filesystem paths, **When** path mapping rules are configured, **Then** media-cron correctly translates the remote save path to the accessible local storage path.

---

### User Story 2 - Torrent Client-Managed Seeding Relocation (Priority: P2)

An operator wants completed torrent files to be relocated to a permanent seeding directory directly through the torrent client's API (such as instructing qBittorrent to change the torrent's save path and move the files), so that seeding continues uninterrupted without broken file paths, missing payload errors, or manual rechecks.

**Why this priority**: Preserves user seeding obligations and tracker ratios automatically. Delegating file movement to the torrent client ensures the client's internal database stays in sync with physical file locations.

**Independent Test**: With an active completed torrent seeding in the download directory, trigger the seeding relocation step; verify that qBittorrent receives the relocation instruction, physically transfers storage to the designated seed directory, updates its internal save path, and resumes seeding without hash verification errors.

**Acceptance Scenarios**:

1. **Given** a completed torrent eligible for seeding and a configured relocation target (either a dedicated seed directory or the destination media library path), **When** torrent-client-managed seeding relocation runs, **Then** media-cron instructs the torrent client to relocate the storage path to the configured target location, the client moves the payload, and seeding continues seamlessly from the new path.
2. **Given** a configuration specifying direct filesystem seeding (bypassing client relocation API), **When** seeding runs, **Then** media-cron relocates or links the files directly on the filesystem as configured without calling the client relocation API.
3. **Given** a torrent relocation command that fails in the client (e.g. destination disk full or permission error reported by client), **When** relocation is attempted, **Then** media-cron detects the client error, halts the operation, retains the original file in place, and logs a descriptive failure.

---

### User Story 3 - Idempotent Tagging and Torrent State Lifecycle (Priority: P3)

An operator wants media-cron to mark processed torrents in the torrent client (by applying a completion tag or transitioning category) so that recurring cron executions do not repeatedly re-stage or re-process already organized downloads.

**Why this priority**: Required for unattended automation. Recurring cron jobs must run frequently without re-ingesting torrents that have already been organized.

**Independent Test**: Execute ingestion against a completed torrent; verify that upon successful staging and organization, the torrent receives the configured processed tag; execute a second run immediately and verify that the tagged torrent is detected as already processed and skipped with zero modifications.

**Acceptance Scenarios**:

1. **Given** a completed torrent that has successfully been staged and organized, **When** post-processing finalizes, **Then** media-cron performs a dual status update: applies the configured completion tag (defaulting to `media-cron-processed`) AND transitions the torrent to the configured post-processing category (defaulting to `media-cron-done`).
2. **Given** a torrent client containing torrents that already bear the completion tag or post-processing category, **When** a recurring ingestion scan executes, **Then** the tagged or re-categorized torrents are ignored and skipped.
3. **Given** a user preference to pause torrents after organization or after reaching a seed ratio target, **When** post-processing completes, **Then** the torrent client is instructed to pause or maintain the torrent according to the configured policy.

---

### User Story 4 - Hybrid Ingestion (Folders and Torrent Clients) (Priority: P4)

An operator wants to monitor local drop folders (such as manual downloads, ripping folders, or browser downloads) alongside direct torrent client monitoring in a single unified pipeline, ensuring neither source is blocked and files are not processed redundantly.

**Why this priority**: Many homelab and server environments acquire media from multiple ingestion avenues. Unified operation simplifies scheduling and avoids running conflicting standalone tools.

**Independent Test**: Place a file in a monitored local directory and complete a torrent in qBittorrent; run a single pipeline execution; verify that both sources are ingested into staging, organized, and reported in the consolidated summary.

**Acceptance Scenarios**:

1. **Given** both monitored folders and a torrent client configured as ingestion sources, **When** the pipeline runs, **Then** assets from both the monitored folder and the torrent client are scanned, staged, and processed in a single coordinated run.
2. **Given** a media file present in a monitored folder that points to the same file or content already ingested via torrent client, **When** staging deduplication evaluates the sources, **Then** duplicate staging is prevented and the asset is processed only once.

---

### User Story 5 - Pluggable Client Architecture (Transmission and Deluge Extensibility) (Priority: P5)

A developer or systems administrator wants a generic, pluggable torrent client interface so that additional torrent clients (specifically Transmission and Deluge) can be integrated with identical ingestion and seeding capabilities without modifying the core pipeline logic.

**Why this priority**: Users utilize diverse torrent clients across their environments. Decoupling client-specific communication protocols from the pipeline ensures long-term extensibility and maintainability.

**Independent Test**: Configure a mock or alternative torrent client implementation conforming to the pluggable client specification; verify that the pipeline can query completed torrents, apply path translations, relocate seeding storage, and manage tags using the identical pipeline workflow.

**Acceptance Scenarios**:

1. **Given** the pluggable client specification, **When** an integration for Transmission or Deluge is registered, **Then** it fulfills standard operations (authenticate, list completed torrents, retrieve payload file paths, relocate storage, update tags/labels) consumable by the ingestion and seeding stages.
2. **Given** an invalid or unknown torrent client provider specified in configuration, **When** the pipeline initializes, **Then** it halts with a clear error indicating the unsupported client type and listing available supported client providers.

---

### Edge Cases

- **Torrent Client Unreachable or Offline**: If the configured torrent client cannot be reached (connection timeout, server down, network partition), the system must log an explicit warning with connection details, skip torrent ingestion without crashing, allow independent folder monitoring to proceed if configured in hybrid mode, and return an appropriate non-zero exit code if torrent ingestion was exclusively requested.
- **Authentication Failure**: If credentials provided for the torrent client Web API are rejected, the system must log an authentication failure (masking sensitive passwords/tokens) and exit cleanly with configuration error status.
- **Torrent Deleted or Removed During Processing**: If a torrent is removed or purged from the client while media-cron is staging its payload, the system must detect missing files before applying modifications, abort processing for that torrent, and log the occurrence.
- **Cross-Mount / Docker Path Discrepancies**: If the torrent client reports a save path that does not exist in media-cron's filesystem (e.g. `/downloads/...` in client container vs `/mnt/storage/downloads/...` on host), the system must validate path mapping rules and alert the user with actionable instructions if a path cannot be resolved locally.
- **Partially Checked or Rechecking Torrents**: Torrents in checking, paused-incomplete, or error states must be skipped until their status returns to completed or seeding.
- **Multi-File Torrents with Mixed File Types**: For torrents containing multiple files (video files, subtitle files, sample files, and junk files), the system must retain all files intact within the torrent client's seeding storage to preserve 100% hash verification for trackers, while excluding clutter files when organizing and transferring media assets into the final media library.
- **Client Relocation Unsupported or Rejected by Client**: If the client's relocate command fails (e.g., due to target filesystem permissions or storage exhaustion), the system must not mark the torrent as processed and must report the error without corrupting the torrent state.
- **Concurrent Executions**: If a scheduled run triggers while a previous torrent ingestion run is still communicating with the torrent client, the directory lockfile must prevent concurrent processing to avoid conflicting state changes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support querying torrent clients directly to discover completed torrent downloads based on configurable criteria (completion percentage 100%, category, and/or tags).
- **FR-002**: System MUST provide built-in, first-class client integration for qBittorrent via its Web API.
- **FR-003**: System MUST provide a generic, pluggable client interface enabling additional torrent clients (including Transmission and Deluge) to implement standardized ingestion and seeding operations.
- **FR-004**: System MUST support configurable path translation mappings (e.g., replacing remote path prefixes with local mount prefixes) to reconcile discrepancies between torrent client storage paths and local filesystem paths.
- **FR-005**: System MUST verify that torrents are fully completed and in a healthy state (e.g. seeding or completed, not actively downloading, rechecking, or in error) before copying their files into the staging directory to ensure the original download is isolated and continuous seeding is never broken during processing.
- **FR-006**: System MUST support targeted single-torrent ingestion triggered by an external identifier, accepting either a unique torrent hash or torrent name (prioritizing hash matching with name-based fallback) to enable direct integration with client completion scripts/hooks.
- **FR-007**: System MUST support batch ingestion of all matching completed torrents during recurring scheduled runs.
- **FR-008**: System MUST support seeding management via torrent client APIs by commanding the client to relocate the torrent's storage path to a configured target directory (supporting either a dedicated seed directory or the final media library directory per configuration).
- **FR-009**: System MUST support direct filesystem seeding management (relocating or hardlinking files directly on the filesystem) as a configurable alternative to client-managed relocation.
- **FR-010**: System MUST update torrent status upon successful staging and organization by performing a dual update: applying a completion tag (defaulting to `media-cron-processed`) AND transitioning the torrent to a configured post-processing category (defaulting to `media-cron-done`) in the torrent client.
- **FR-011**: System MUST ensure idempotency by ignoring and skipping torrents that already possess the completion tag or target post-processing category on subsequent runs.
- **FR-012**: System MUST support hybrid ingestion mode, allowing simultaneous folder monitoring and torrent client ingestion within a single execution cycle without conflicts.
- **FR-013**: System MUST provide a non-destructive dry-run simulation mode that queries the torrent client, plans staging and relocation operations, and previews tag updates without modifying files on disk or changing torrent states in the client.
- **FR-014**: System MUST handle torrent client connectivity and authentication errors gracefully, logging structured error information and exiting with documented deterministic exit codes.
- **FR-015**: System MUST isolate and mask client authentication credentials (usernames, passwords, tokens) from logs and dry-run outputs.
- **FR-016**: System MUST coordinate with the pipeline staging lock mechanism to ensure safe single-instance execution when interacting with torrent clients.
- **FR-017**: System MUST preserve non-media clutter and metadata files within the torrent client's seeding location to ensure 100% tracker hash integrity and avoid recheck failures, while strictly filtering out clutter files when transferring media assets into the destination library.

### Key Entities *(include if feature involves data)*

- **Torrent Item**: Represents a download managed by the torrent client (attributes: unique hash/identifier, torrent name, total size, completion percentage, state [downloading, seeding, completed, paused, error], current save path, category, assigned tags, list of contained files).
- **Torrent Client Connection**: Represents connection and authentication settings for an external torrent client (attributes: client type [qbittorrent, transmission, deluge, custom], host/url, port, authentication credentials, request timeout, connection status).
- **Path Mapping Rule**: Represents translation between client-reported storage paths and local filesystem mount points (attributes: remote prefix, local prefix).
- **Ingestion Filter**: Configuration rules specifying which torrents qualify for processing (attributes: target categories, required tags, excluded tags, minimum ratio, minimum age).
- **Seeding Strategy**: Configuration governing how seeding media is maintained post-organization (attributes: mode [client-relocation, direct-filesystem, none], target relocation directory [dedicated seed directory or final library path], post-process action [continue-seeding, pause, update-category, apply-tag]).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of torrents detected as incompletely downloaded, currently checking, or in an error state are skipped without staging or modifying any partial files.
- **SC-002**: In dry-run mode, 100% of planned torrent staging, client relocations, and tag modifications are accurately simulated with zero mutations to the filesystem and zero state alterations in the torrent client.
- **SC-003**: 100% of completed torrents staged from qBittorrent with configured path mappings resolve to valid local filesystem paths without path truncation or escaping errors.
- **SC-004**: When client-managed seeding relocation is enabled, 100% of eligible torrents have their save path updated in the torrent client without incurring data corruption or broken torrent status.
- **SC-005**: 100% of successfully processed torrents receive both the completion tag and target category update, resulting in 0 duplicate ingestions on subsequent cron runs.
- **SC-006**: In hybrid mode, processing a batch containing both folder-monitored items and client-monitored torrents completes successfully without file collision or pipeline deadlock.
- **SC-007**: When the torrent client is unreachable or authentication fails, the system logs a diagnostic message and terminates within the configured network timeout without hanging indefinitely.
- **SC-008**: Querying and evaluating up to 200 torrents from a local qBittorrent instance completes the discovery phase in under 3 seconds.

## Assumptions

- qBittorrent provides its standard Web API v2 accessible over HTTP/HTTPS with username and password authentication.
- Storage paths used by the torrent client reside on filesystems accessible to the media-cron host/container (either locally or via shared mounts/volumes).
- Where path mapping is needed (e.g. containerized setups), the operator configures corresponding prefix translation rules.
- The torrent client has sufficient filesystem permissions to relocate files when client-managed relocation mode is selected.
- By default, torrents will remain in a seeding state after being tagged as processed, unless the operator explicitly configures a pause action.
- The staging directory has sufficient available disk space to accommodate full copies of incoming torrent payloads during processing.
- The existing staging directory lockfile and media organization pipeline (developed in feature 001) are reused for processing staged media assets.
