# Technical Research: Per-Media-Type Source & Destination Routing

**Feature Branch**: `009-media-source-destination-routing`
**Date**: 2026-10-07
**Spec**: [spec.md](spec.md)

---

## 1. Declarative Configuration Architecture & Distributed YAML Schema

### Decision
Embed `sources`, `destination`, and optional `transfer_mode` directly inside existing media configuration sections (`music:`, `books:`, `audiobook:`, and `video.movies` / `video.tv`), while preserving global `paths:` and `general:` settings as fallback defaults. Support structured environment variables (e.g., `MEDIA_CRON_MUSIC_DESTINATION_PATH`, `MEDIA_CRON_VIDEO_MOVIES_SOURCES`) for containerized deployments.

### Rationale
- **User Alignment**: In clarification Session 2026-10-07 (Q5), the operator explicitly chose distributed sections over a separate top-level `media_routing:` mapping.
- **Cohesion**: Keeps each media domain's ingestion, naming templates, workflow mode, and destination localized within its dedicated domain block.
- **Backward Compatibility**: Existing fields like `paths.source_dir`, `paths.destination_dir`, `video.spool_dir`, and `music.spool_dir` remain fully operational and serve as base fallbacks if explicit routing blocks are omitted.

### Alternatives Considered
- *Consolidated top-level `media_routing:` block*: Evaluated and rejected in Q5 to maintain alignment with user preference and existing domain configuration conventions.
- *Overloading `paths:` with arbitrary strings*: Rejected because media types require distinct source types (directories, torrent categories), client profile references, and destination operational modes (`library` vs `spool`) that exceed flat path string attributes.

---

## 2. Source Ingestion & Multi-Source Aggregation Engine

### Decision
Implement a unified `MediaRoutingEngine` and `RouteResolver` that resolves an active routing plan for each media type (`music`, `audiobooks`, `books`, `movies`, `tv`). For sources, support:
1. `type: "directory"`: Ingests via `DirectoryScannerInput` with a target filesystem path.
2. `type: "torrent"`: Ingests via `TorrentInputPlugin` with optional `client_profile` (from `torrent_clients`), category filter, tag filter, and exclusion lists.
Multiple sources configured for a single media type are aggregated into a unified candidate queue. Discovered items are stamped with their originating `source_media_type` and unique filesystem identity (inode/resolved path) to prevent redundant scanning.

### Rationale
- **Extensible intake**: Accommodates heterogeneous acquisition channels (e.g., automated download folders, torrent labels, manual drop folders).
- **Client decoupling**: Allows different media types to interface with different torrent clients (e.g. private tracker client for music vs public client for video) or share a single active client, per user clarification (Q3).
- **Deduplication**: Resolving inodes and paths upfront prevents race conditions or duplicate operations when overlapping directories are declared.

### Alternatives Considered
- *Sequential independent pipelines*: Running completely separate pipeline instances per media type. Rejected because it complicates cross-media locking (`StagingLock`), duplicates lockfile contention, and prevents consolidated batch summaries.
- *Global directory scan with post-hoc filtering*: Scanning only `paths.source_dir` and filtering files by extension. Rejected because it fails to satisfy the requirement of reading from distinct, physically separated source locations per media type.

---

## 3. Strict Source Isolation & Review Staging Heuristics

### Decision
When an item is discovered from a media-specific source (a source assigned specifically to e.g. `music`), the pipeline enforces strict type matching against the identified `MediaCategory`. If an item does not match the designated media type (e.g. an `.mkv` video found in an audiobooks folder):
1. It is **never** routed to other libraries or drop folders.
2. It is quarantined into `review_dir` (or left in place if review is disabled) via `OperationType.REVIEW_STAGE`.
3. An operational warning is emitted in logs and batch telemetry.

### Rationale
- **User Alignment**: Clarification Q1 established strict isolation as the mandatory policy.
- **Data Integrity**: Prevents accidental pollution of media libraries caused by mislabeled or stray downloads in dedicated folders.
- **Safety**: Unintended files are isolated in the review queue where operators can inspect them with `media-cron review list` without data loss.

### Alternatives Considered
- *Dynamic cross-routing*: Identifying the stray file and organizing it into whichever library matches its extension. Rejected during clarification because users expect dedicated folders to retain strict ownership over their contents.
- *Silent skip*: Leaving the file in the source directory without notification. Rejected because the operator would not know why files were left unorganized in incoming folders.

---

## 4. Mount Point Safety & Destination Root Pre-Existence Validation

### Decision
Before planning or executing file transfers, the `RouteResolver` validates that every configured destination root directory exists on disk.
- If a destination root directory does not exist, operations for that specific media type are aborted immediately with a non-fatal error code and clear warning.
- Other media types whose destination directories exist continue processing normally.
- Once a destination root exists, the system continues to dynamically create child subdirectories (artist, album, season, year) as needed.

### Rationale
- **User Alignment**: Clarification Q4 confirmed that mount safety is paramount for homelab NAS setups.
- **Storage Protection**: In Linux environments, if `/mnt/movies` or `/mnt/music` is an unmounted network share or detached drive, running `mkdir -p` writes media files directly to the host operating system's root partition (`/`), quickly exhausting disk space and crashing OS services.

### Alternatives Considered
- *Unconditional `mkdir -p`*: Standard in simple scripts, but hazardous in NAS/server deployments. Rejected.
- *Strict requirement that all leaf directories exist*: Requiring the user to pre-create every artist and season folder manually. Rejected because dynamic organizational templating is a core feature of media-cron.

---

## 5. Per-Media-Type Transfer Modes & Fallback Hierarchy

### Decision
Allow each media routing rule to optionally specify `transfer_mode`: `"hardlink" | "copy" | "move"`.
The effective transfer mode resolves hierarchically:
1. Per-media rule `transfer_mode` (if defined).
2. Global `general.mode` (default: `"hardlink"`).
3. If cross-device filesystem boundary is detected during hardlinking, fall back automatically to copy (respecting existing copy-fallback policies).

### Rationale
- **User Alignment**: Clarification Q2 confirmed per-media transfer mode overrides.
- **Workload Specialization**: Allows users to configure `hardlink` for torrent-seeded videos to preserve ratios while configuring `move` or `copy` for books and music located on separate filesystems.

### Alternatives Considered
- *Coupling transfer mode strictly to endpoint type*: E.g., hardlink for libraries, move for spools. Rejected because some operators run drop folders on the same filesystem and prefer hardlinks to avoid IO overhead.

---

## 6. Observability & Telemetry Integration

### Decision
Extend `BatchSummary` with a structured `routing_summary: dict[str, MediaRouteSummary]` field, detailing for each media type (`music`, `audiobooks`, `books`, `movies`, `tv`):
- `source_endpoints`: Count and types of sources queried.
- `destination_endpoint`: Resolved destination path and type.
- `transfer_mode`: Resolved transfer mode used.
- `scanned_count`: Items discovered from that media type's sources.
- `processed_count`: Items successfully organized or spooled.
- `review_staged_count`: Items isolated due to type mismatch or unrecognized status.
- `skipped_count`: Items skipped due to collisions or missing targets.
- `error_count`: Errors encountered during processing.

### Rationale
- Fulfills Constitution Principle IV (Structured Observability).
- Provides instant visibility into multi-endpoint operations during both dry-run simulations and unattended cron runs.
