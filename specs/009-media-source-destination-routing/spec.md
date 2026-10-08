# Feature Specification: Configurable Per-Media-Type Sources, Destinations, and Multi-Type Routing

**Feature Branch**: `009-media-source-destination-routing`

**Created**: 2026-10-07

**Status**: Ready

**Input**: User description: "Source and destination should be configurable per media type ( music, audiobooks, books, movies, tv ) and work with multiple source and detination types."

## Clarifications

### Session 2026-10-07
- Q: How should media-cron handle files discovered in a media-specific source that do not match that source's designated media type? (FR-004) → A: Strict filtering: only ingest matching media types; leave or stage mismatched files in review without routing to other libraries.
- Q: Should each media type allow configuring its own file transfer mode (hardlink, copy, move) independently, or should transfer mode remain strictly global? (FR-001) → A: Per-media override: each media type can define its own transfer mode (hardlink, copy, move), defaulting to global general.mode.
- Q: Can different media types connect to different torrent clients, or should all media types share the single configured active torrent client? (FR-002) → A: Per-media client selection: each media type can optionally designate a specific client profile from torrent_clients, falling back to the active client if unspecified.
- Q: How should media-cron behave if a media type's configured destination root directory does not exist on disk when a job runs? (FR-008) → A: Mount safety: require destination root path to pre-exist; abort that media type if missing, but auto-create child subdirectories.
- Q: Where in the YAML configuration hierarchy should per-media-type routing rules be declared? (FR-007) → A: Distributed sections: embed sources and destination directly inside existing media blocks (music, video, books, audiobook) in configuration.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dedicated Per-Media-Type Destination Routing (Priority: P1) 🎯 MVP

A media collector maintains distinct storage locations (e.g., separate disks, storage pools, or directory trees) for different media formats: music, audiobooks, books, movies, and TV shows. When media-cron runs, the user wants each media type routed and organized directly into its designated destination rather than forcing all media into subdirectories of a single shared destination root.

**Why this priority**: Core requirement delivering immediate value. Enables users with partitioned storage or dedicated mount points to organize files directly into their respective media libraries without manual post-processing.

**Independent Test**: Configure a dedicated destination path for music and a distinct destination path for movies; process a batch containing both audio and video files; verify that organized music files are placed in the music destination and movie files are placed in the movie destination with correct organizational templates.

**Acceptance Scenarios**:

1. **Given** configured destination paths specific to `music`, `audiobooks`, `books`, `movies`, and `tv`, **When** media-cron processes identified assets for each category, **Then** each asset is placed into its respective category destination.
2. **Given** a media type without a dedicated destination configuration, **When** media-cron processes assets of that type, **Then** the system falls back to the global destination directory if configured.
3. **Given** an execution in dry-run mode, **When** per-media destination paths are configured, **Then** the planned file operations accurately display the type-specific destination paths without modifying the filesystem.

---

### User Story 2 - Per-Media-Type Ingestion from Multiple Source Types (Priority: P2)

A user ingests media through different channels depending on the media type. For example, movies and TV shows are sourced from specific torrent client categories or download directories, while books and audiobooks arrive through dedicated incoming watch folders or manual drop directories. The user wants each media type to define its own source(s) and source type (such as local filesystem directories or torrent client categories/tags), aggregating inputs when multiple sources are declared for a single media type.

**Why this priority**: Solves the intake bottleneck where different acquisition workflows produce files in different locations and formats. Allows targeted ingestion per media type.

**Independent Test**: Configure a local directory source for books and a torrent client category source for movies; trigger ingestion; verify that book files are discovered and ingested from the local directory while movie files are discovered and filtered from the torrent client, ignoring torrents from other categories.

**Acceptance Scenarios**:

1. **Given** a local directory source configured for `books` and a torrent client source (with category/tag filter) configured for `movies`, **When** media-cron runs, **Then** books are discovered from the specified directory and movies are discovered from matching torrents.
2. **Given** multiple sources configured for a single media type (e.g., both a local incoming folder and a torrent category for `music`), **When** media-cron runs, **Then** the system aggregates discovered items across all configured sources for that media type into a unified processing queue.
3. **Given** a media type configured with a source that contains no new files, **When** media-cron executes, **Then** the system processes other configured media types normally without failing the overall run.
4. **Given** a source location that is inaccessible or missing, **When** media-cron scans sources, **Then** the system reports a descriptive diagnostic error for that source and continues processing healthy sources where possible.

---

### User Story 3 - Configurable Destination Operational Types per Media Type (Priority: P3)

Different media types require different operational outcomes upon processing. For instance, movies and TV shows may need to be deposited into a drop/spool folder for consumption by an external library manager (such as an *arr stack application), whereas music, audiobooks, and books are organized directly into structured, permanent libraries. Furthermore, active torrent downloads may need client relocation to a dedicated seeding directory. The user needs the destination type (e.g., direct structured library, drop/spool folder, or torrent seeding relocation) to be configurable per media type.

**Why this priority**: Accommodates heterogeneous downstream tooling across media categories, supporting direct library management for some types and handoff to external managers for others.

**Independent Test**: Configure `movies` with a spool/drop-folder destination type and `music` with a direct structured library destination type; process incoming files for both types; verify movies are deposited into the spool folder preserving folder structure while music files are renamed and structured into the music library.

**Acceptance Scenarios**:

1. **Given** a media type configured with a `spool` destination type and target path, **When** releases of that type are processed, **Then** the release bundle is deposited atomically into the configured drop folder.
2. **Given** a media type configured with a `library` destination type and target path, **When** assets of that type are processed, **Then** files are organized into structured directories according to category templates.
3. **Given** a media type configured with torrent seeding rules, **When** processing completes, **Then** seeding files are preserved or relocated according to the media type's seeding configuration.

---

### User Story 4 - Backward Compatibility, Global Fallbacks & Observability (Priority: P4)

A user with an existing media-cron configuration using global `paths.source_dir` and `paths.destination_dir` upgrades their installation. The user expects existing configurations to function without modification. Additionally, administrators running scheduled jobs require comprehensive dry-run preview and structured reporting of media discovered, processed, and routed per media type.

**Why this priority**: Prevents breaking changes for existing users and fulfills Constitution Principles III (Idempotency) and IV (Observability).

**Independent Test**: Run media-cron with legacy global source/destination settings and no per-media-type routing; verify all media types are processed using global defaults; run with partial overrides (e.g., only `music` overridden) and verify only music uses the custom path while other media uses global defaults.

**Acceptance Scenarios**:

1. **Given** a configuration specifying only global source and destination paths, **When** media-cron runs, **Then** all recognized media types are ingested and organized under the global paths matching legacy behavior.
2. **Given** a configuration specifying global paths and an override for `audiobooks`, **When** media-cron runs, **Then** audiobooks use the overridden paths while other media types use the global paths.
3. **Given** a dry-run execution, **When** operations are planned, **Then** the output summary reports the resolved source, destination, and endpoint type for each planned operation.

---

### Edge Cases

- **Cross-Device / Cross-Filesystem Transfers**: What happens when a per-media destination resides on a different filesystem or mount point than the staging directory? The system must automatically detect hardlink inability across devices and fall back to copy or move according to configured transfer mode policies without corrupting files.
- **Multiple Sources Containing the Same Asset**: How does the system handle an asset found in both a local directory source and a torrent client source? The system must identify duplicate paths or identical files, prevent redundant processing, and record deduplication in telemetry.
- **Missing or Unmounted Destination Storage**: How does the system respond if the dedicated drive or mount point for a specific media type (e.g., `/mnt/movies`) is unmounted or unreachable? The system enforces mount safety: it requires the configured destination root directory to pre-exist. If missing, processing for that media type is aborted safely to avoid writing orphan files to the host root filesystem, while allowing other healthy media types to proceed. Child subdirectories (e.g. artist, season) within a valid root continue to be created automatically.
- **Unrecognized Media Ingestion**: What happens to files discovered in a per-media-type source that do not match the expected media category (e.g., an ebook found in a music source folder)? The system enforces strict source isolation: mismatched files are never routed to other media libraries; they are staged into the review queue (or left in-place) with a diagnostic warning to the operator.
- **Colliding Destination Paths Across Media Types**: What happens if an operator mistakenly configures overlapping destination directories for two different media types? The system must validate configuration on startup and emit a warning if destination roots conflict unexpectedly.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support independent source and destination configuration for each recognized media type: `music`, `audiobooks`, `books`, `movies`, and `tv`.
- **FR-002**: The system MUST support multiple source types per media type, specifically local filesystem directories (`directory`) and torrent client categories/tags (`torrent`).
- **FR-003**: The system MUST support multiple destination types per media type, specifically direct structured library organization (`library`) and drop/spool folders for external managers (`spool`).
- **FR-004**: The system MUST support multi-source aggregation for each media type (allowing a media type to ingest concurrently from one or more local directories and/or torrent categories) while routing to a single primary destination (structured library or spool folder) per media type.
- **FR-005**: The system MUST implement hierarchical fallback: if a media type does not define explicit sources or destinations, it MUST inherit the global `paths.source_dir` and `paths.destination_dir` settings.
- **FR-006**: The system MUST preserve 100% backward compatibility with legacy global source and destination path settings when per-media-type settings are omitted.
- **FR-007**: The system MUST support declarative configuration by embedding `sources` and `destination` endpoints directly within each media category's existing configuration block (`music`, `video`, `books`, `audiobook`), alongside environment variable overrides for all per-media endpoints.
- **FR-008**: The system MUST validate that configured destination root directories exist on disk before initiating file transfers; if a destination root is missing, the system MUST abort operations for that specific media type to prevent writing to unmounted mount points, while auto-creating necessary child subdirectories within existing roots.
- **FR-009**: The system MUST support dry-run simulation mode (`--dry-run`) displaying the exact source, destination, and transfer operation planned for each media asset across all configured media types.
- **FR-010**: The system MUST emit structured execution summaries and telemetry detailing files discovered, processed, skipped, or failed broken down by media type and endpoint.
- **FR-011**: The system MUST enforce strict type filtering on media-specific sources; files discovered within a type-specific source that do not match that source's designated media type MUST NOT be routed to other media libraries and MUST be staged into the review queue (or left in-place) with a diagnostic warning.
- **FR-012**: The system MUST allow each media type to optionally configure its own transfer mode (`hardlink`, `copy`, or `move`), falling back to the global `general.mode` when not specified.
- **FR-013**: The system MUST allow each media type's torrent source to optionally specify a named client profile from `torrent_clients`, falling back to the primary `active_torrent_client` if not specified.

---

### Key Entities *(include if feature involves data)*

- **MediaType**: The classification of content being handled: `music`, `audiobooks`, `books`, `movies`, or `tv`.
- **SourceEndpoint**: Represents a location and mechanism from which media is ingested. Attributes include:
  - `endpoint_type`: The mechanism used to discover files (`directory` or `torrent`).
  - `location`: The filesystem path or torrent client category/tag filter.
  - `client_profile`: Optional name of the torrent client profile from `torrent_clients` when `endpoint_type` is `torrent`.
  - `filters`: Optional category, tag, or extension filters applied to the source.
- **DestinationEndpoint**: Represents a target where media is organized or handed off. Attributes include:
  - `endpoint_type`: The target handling mode (`library` or `spool`).
  - `target_path`: The base filesystem path where content is delivered.
  - `template`: Optional naming and hierarchy template overriding default patterns for that media type.
- **MediaRoutingRule**: The association binding a `MediaType` (configured within its respective media block: `music`, `video.movies`, `video.tv`, `books`, `audiobook`) to its list of `SourceEndpoint`s and single primary `DestinationEndpoint`, along with an optional per-media transfer mode preference (`hardlink`, `copy`, `move`) overriding the global setting.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can configure distinct source and destination paths for all 5 media types (`music`, `audiobooks`, `books`, `movies`, `tv`) and process mixed-media workloads in a single execution without cross-contamination.
- **SC-002**: 100% of existing configurations without per-media-type routing continue to execute with identical behavior (zero breaking changes for legacy configurations).
- **SC-003**: In dry-run mode, 100% of planned operations accurately report the resolved source endpoint, destination endpoint, and endpoint type for each asset prior to any filesystem modification.
- **SC-004**: When an individual media type's destination path is unmounted or missing, the system aborts operations for that media type in under 1 second without writing orphan files to root filesystems, while safely completing healthy media types.
- **SC-005**: Batch summary telemetry explicitly itemizes processed counts, errors, and destinations grouped by media type.

---

## Assumptions

- **Recognized Media Categories**: The media categories are aligned with the existing system types: `music`, `audiobooks`, `books`, `movies`, and `tv`.
- **Transfer Heuristics**: The existing atomic transfer, hardlink-with-copy-fallback, and collision detection heuristics apply uniformly across all destination endpoints unless explicitly overridden.
- **Configuration Hierarchy**: Global path configurations serve as base defaults that can be selectively overridden by media-type-specific configurations.
- **Single-Host Filesystem Access**: All directory endpoints represent paths directly accessible on the host filesystem (e.g., local storage or mounted network shares).
- **Scheduler Independence**: Media routing operates during regular pipeline execution, whether triggered interactively via CLI or unattended via cron/containers.
