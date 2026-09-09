# Feature Specification: Music Library Organization and Drop-Folder Ingestion

**Feature Branch**: `005-music-organization`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "music: Automatic identification should be supported but not required. Dumping media to a folder to be consumed by  a music library manager, such as beets, that handles identification and organization is also a valid work flow."

## Clarifications

### Session 2026-09-09
- Q: How should media-cron structure music releases and companion assets when depositing files into the external manager's drop directory? (FR-002) → A: Preserve release folder hierarchy, placing each album release in its own subdirectory containing tracks and companion assets (artwork, .cue, .log).
- Q: Should media-cron support executing an optional post-ingest command (such as beet import) after depositing media into the drop directory, or strictly perform filesystem handoff? (FR-015) → A: Support an optional post-ingest command hook (e.g. beet import {release_path}) executed after successful release drop, defaulting to pure filesystem drop handoff when unconfigured.
- Q: How should media-cron determine whether to route music to the external drop directory (spool mode) versus organizing it directly into the music library (direct mode)? (FR-001) → A: Support an explicit configuration flag (--music-mode spool|direct|hybrid) that automatically defaults to spool mode whenever a drop directory (--music-spool-dir) is provided, and direct otherwise.
- Q: How should media-cron prevent external managers (such as beets watchers) from reading partially transferred files during drop-folder deposition? (FR-012) → A: Atomic directory staging: transfer release into a hidden temporary folder (.incoming_name), atomically renaming it to the final release path upon full completion.
- Q: Which external music catalog provider should media-cron integrate for optional online music identification? (FR-008) → A: Multi-provider cascade with MusicBrainz as the default keyless open catalog provider and Discogs as an optional configured fallback (when credentials are provided).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Drop-Folder Ingestion for External Music Library Managers (Priority: P1)

A music collector or automated media downloader uses an external, dedicated music management tool (such as `beets`, `Lidarr`, or `MusicBrainz Picard`) to handle music tagging, acoustic fingerprinting, and organization. When media-cron downloads or discovers music files, the user wants the system to route and deposit the music into a designated drop/spool directory. The system preserves multi-track album folder hierarchies and bundles companion release assets (such as album cover art, `.cue` sheets, and `.log` files) so that the downstream manager receives a complete, uncorrupted album release ready for autonomous or supervised import.

**Why this priority**: Depositing media into a downstream library manager's drop folder represents a fundamental workflow for users who prefer specialized tools like `beets` for music curation. Delivering clean drop-folder ingestion provides an immediate, standalone, and independently testable MVP that requires zero external network lookups or complex tag matching.

**Independent Test**: Place an album release directory containing audio tracks and cover art into the input staging area; run the music processor configured in drop-folder (spool) mode; verify that the complete release folder structure and accompanying assets are relocated or linked into the designated external drop folder without modifications to the audio files.

**Acceptance Scenarios**:

1. **Given** a music release containing audio tracks (e.g. `.mp3`, `.flac`, `.m4a`) in staging and a configured drop folder path, **When** processed in drop-folder mode, **Then** the release is deposited into the drop folder with release directory hierarchy intact.
2. **Given** a music release containing non-audio companion files (such as `cover.jpg`, `album.cue`, or checksum logs), **When** routed to the drop folder, **Then** all companion files are preserved alongside the audio tracks in the destination directory.
3. **Given** an ingest mode configured for hardlinking, **When** files are routed to the drop folder, **Then** hardlinks are created so that active torrent seeding remains undisturbed at the source location while the downstream manager consumes the files.
4. **Given** an optional post-ingest command is configured (e.g. `beet import {release_path}`), **When** a release is deposited into the drop folder, **Then** the command is executed with the release path and its output is captured in structured logs without failing the batch on external tool errors.

---

### User Story 2 - Automated Embedded Metadata Extraction and Library Organization (Priority: P2)

A user who does not run an external music manager wants media-cron to organize incoming music directly into their organized library (e.g., `Music/<Album Artist>/<Album> (<Year>)/<Track#> - <Title>.<ext>`). When direct organization mode is selected, the system automatically inspects internal audio tags (ID3, Vorbis Comments, FLAC blocks, MP4 tags), extracts artist, album, track title, track number, disc number, and release year, sanitizes filenames, and places each track into a standardized library directory structure.

**Why this priority**: Users seeking an all-in-one media automation pipeline need internal organization capability without depending on third-party daemon processes or external tools.

**Independent Test**: Provide tagged audio tracks with mixed or unstructured filenames (e.g., `track01.flac`, `artist - song.mp3`); process in direct organization mode; verify the tracks are correctly sorted into standard Artist/Album directories and formatted with canonical track numbers and titles based on embedded tags.

**Acceptance Scenarios**:

1. **Given** audio files with standard embedded metadata tags, **When** processed in direct organization mode, **Then** the system reads artist, album, track title, track number, and year, and organizes the files into standardized destination paths.
2. **Given** a multi-disc album release with disc numbers in embedded tags or folder cues (`Disc 1`, `Disc 2`), **When** organized directly, **Then** tracks are sorted into appropriate disc subdirectories or prefixed with disc numbers (e.g., `1-01 - Title.mp3`).
3. **Given** a release with compilation or various artists tags, **When** organized directly, **Then** the album is grouped under the designated Album Artist or a "Various Artists" directory rather than fragmenting tracks across multiple artist folders.

---

### User Story 3 - Optional External Catalog Identification and Disambiguation (Priority: P3)

A user with incomplete, mistagged, or stripped audio files wants the option to automatically identify releases using an external music catalog (such as MusicBrainz). When automatic external identification is enabled, the system queries the catalog using release-level and track-level metadata hints (album artist, album title, track counts, track titles), computes match confidence scores, resolves canonical release information, and enriches the asset metadata before routing.

**Why this priority**: External identification enhances metadata quality for untagged or poorly tagged music, fulfilling the requirement that automatic identification is supported as an optional, non-blocking feature.

**Independent Test**: Provide an album with missing track titles or incomplete year metadata; execute with external lookup enabled; verify the system queries the catalog, receives canonical release data, and populates missing metadata fields.

**Acceptance Scenarios**:

1. **Given** an album with partial tags and external identification enabled, **When** processed, **Then** the system queries the external catalog and retrieves canonical release details, recording match confidence and source.
2. **Given** external identification is disabled or external services are unreachable, **When** processing music, **Then** the system operates purely on local embedded tags and filename heuristics without failure.
3. **Given** candidate matches from an external catalog fall below the confidence threshold (e.g., <85%), **When** evaluated, **Then** local embedded tags are strictly preserved and the match is flagged as low confidence or unverified.

---

### User Story 4 - Non-Destructive Simulation, Retention, and Operational Safety (Priority: P4)

A system administrator or user running automated scheduled cron jobs requires safe execution guarantees. The system supports dry-run simulation mode (reporting proposed drop-folder relocations, identified tags, or target paths without altering the filesystem) and ensures atomic file transfers and failure recovery so that partial copy operations never leave inconsistent album states in drop or library folders.

**Why this priority**: Scheduled media automation mandates safety, idempotency, and non-destructive defaults to prevent data loss or corrupt imports.

**Independent Test**: Execute the music organization pipeline with `--dry-run`; verify that the system logs all planned drop-folder placements or library relocations without moving, modifying, or creating any files on disk.

**Acceptance Scenarios**:

1. **Given** a music collection processed with `--dry-run`, **When** executed, **Then** the system outputs a complete plan of proposed drop-folder relocations or library organizational paths with zero disk mutations.
2. **Given** an unexpected error or interruption during file transfer to the drop folder or library, **When** the error occurs, **Then** partial files are cleaned up and original source files remain intact.
3. **Given** already processed music in the drop or destination folder, **When** re-processed, **Then** the system identifies existing items idempotently without creating redundant duplicate copies.

---

### Edge Cases

- **Multi-Disc Releases**: Releases split across subdirectories (e.g., `CD1/`, `CD2/` or `Disc 1/`, `Disc 2/`); the system must recognize them as parts of a single unified release bundle in both drop-folder and direct modes.
- **Mixed Formats in Single Release**: An album containing both MP3 and FLAC tracks, or audio tracks mixed with PDF booklets, videos, or `.nfo` files; the system must group relevant companion files with the release while filtering out irrelevant junk.
- **Missing or Corrupt Audio Tags**: Files with corrupted ID3/Vorbis headers or zero embedded tags (e.g., `track_01.wav`); in drop-folder mode, these are passed through to the downstream manager; in direct mode, filename heuristics extract available artist/title info or route to an `Unknown Artist` quarantine path.
- **Various Artists and Soundtracks**: Compilations where every track has a different artist; the system must inspect `albumartist` or `compilation` flags to prevent splitting the album into dozens of disparate artist directories.
- **Downstream Manager Drop-Folder Ingestion Lock**: The downstream manager (e.g., `beets import`) may actively scan the drop folder; media-cron MUST write files into a hidden temporary directory (`.incoming_<release_name>`) on the drop filesystem and atomically rename the completed folder so the manager never consumes partially transferred files.
- **Special Characters and Deep Paths**: Track titles and artist names containing slashes, colons, emojis, or non-ASCII characters; the system must sanitize paths safely across Linux and network filesystem (NFS/SMB) boundaries.
- **Seeding and Link Safety**: When media originates from an active torrent, hardlinking MUST be used whenever source and destination reside on the same filesystem to allow simultaneous seeding and drop-folder consumption.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support configurable music workflow modes (`--music-mode` / `workflow_mode`): `spool` (dump release bundles to an external music manager's drop folder), `direct` (extract metadata and organize into a structured music library), and `hybrid` (enrich metadata then deposit into the drop folder), automatically defaulting to `spool` whenever a drop directory (`--music-spool-dir`) is provided, and `direct` otherwise.
- **FR-002**: In `spool` mode, system MUST deposit incoming music files into a configurable drop/spool directory while preserving the release's folder hierarchy, placing each album release in its own subdirectory containing tracks and companion assets.
- **FR-003**: In `spool` mode, system MUST bundle companion release files (including album artwork, `.cue` sheets, `.log` files, and playlist files) alongside audio files so downstream managers have full release context.
- **FR-004**: System MUST extract embedded metadata (artist, album artist, album title, track title, track number, disc number, release year, and genre) from standard audio formats (including `.mp3`, `.flac`, `.m4a`, `.ogg`, `.opus`, `.wav`, `.alac`, and `.aiff`) without requiring external network dependencies.
- **FR-005**: In `direct` mode, system MUST organize processed audio files into a standardized directory structure (e.g., `Music/<Artist>/<Album> (<Year>)/<Track#> - <Title>.<ext>`) using sanitized path naming.
- **FR-006**: In `direct` mode, system MUST properly handle multi-disc releases by sorting tracks into disc-specific folders or applying disc-track numbering prefixes.
- **FR-007**: In `direct` mode, system MUST detect compilation and "Various Artists" releases to group tracks under the album artist rather than fragmenting tracks across multiple artist folders.
- **FR-008**: System MUST support optional external catalog lookup using a multi-provider cascade: querying MusicBrainz as the default keyless open catalog provider and falling back to Discogs when optional API credentials are provided.
- **FR-009**: When external catalog lookup is enabled, system MUST compute a match confidence score and require a strict threshold (≥85%) before external metadata may override local embedded tags; below threshold, local embedded tags MUST be preserved.
- **FR-010**: System MUST provide a local-first offline fallback: if external lookup is disabled, timed out, or unreachable, processing MUST proceed seamlessly using embedded tags and filename heuristics.
- **FR-011**: System MUST support dry-run simulation mode (`--dry-run`), outputting planned drop-folder relocations or library organizational paths with zero filesystem modifications.
- **FR-012**: System MUST perform drop-folder transfers atomically by staging each complete release bundle into a hidden temporary folder (`.incoming_<release_name>`) on the drop filesystem and renaming to the final directory path only upon successful transfer of all tracks and companion assets, preventing inotify watchers from triggering on partial files.
- **FR-013**: System MUST support hardlinking when transferring files across compatible filesystems to preserve continuous seeding for torrent-managed downloads.
- **FR-014**: System MUST cache external catalog query results in a persistent local cache with configurable time-to-live (TTL) to avoid redundant network lookups.
- **FR-015**: System MUST provide CLI options and configuration settings to configure music mode (`--music-mode`), drop folder destination (`--music-spool-dir`), external lookup toggle (`--music-lookup / --no-music-lookup`), optional post-ingest command hook (`--music-post-command`), and diagnostic inspection commands.
- **FR-016**: System MUST record structured telemetry and execution summaries detailing the number of tracks processed, releases bundled, drop-folder transfers, and identification confidence.
- **FR-017**: When an optional post-ingest command is configured, system MUST execute the command template upon successful drop-folder placement with configurable timeout and error handling, logging subprocess output without interrupting subsequent releases on command failure.

### Key Entities *(include if feature involves data)*

- **MusicTrack**: Represents an individual audio file, containing file path, format, duration, bitrate, embedded tags (artist, album artist, album, track title, track number, disc number, year, genre, MusicBrainz IDs), and validation status.
- **MusicReleaseBundle**: Represents a cohesive album, EP, single, or multi-disc release consisting of a collection of `MusicTrack` items and associated companion assets (cover art, cue sheet, rip logs).
- **MusicWorkflowMode**: Represents the selected operational pipeline mode: `spool` (dump to external manager), `direct` (internal organization), or `hybrid` (enrich tags then spool).
- **MusicCatalogMatch**: Represents candidate release metadata retrieved from an external music catalog, including canonical artist, release title, release year, track list, catalog identifier, and confidence score.
- **MusicSpoolTarget**: Represents the configured external drop/spool location, transfer strategy (copy, hardlink, move), and atomic staging rules for handoff to tools like `beets`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In `spool` mode, 100% of audio files and valid companion assets (artwork, cue sheets, logs) in a release bundle are deposited into the designated drop folder with directory hierarchy preserved.
- **SC-002**: In `direct` mode, at least 95% of standard audio tracks with valid embedded tags are accurately organized into the proper Artist/Album hierarchy without manual intervention.
- **SC-003**: 100% of multi-disc releases are organized without track collision or fragmentation across separate album folders.
- **SC-004**: In dry-run mode, 100% of planned file operations (drop-folder routing or library placement) are reported accurately with zero disk writes, renames, or deletions.
- **SC-005**: Zero partial or corrupted files are left in the drop folder or library upon process interruption; atomic staging guarantees all-or-nothing transfer for complete releases.
- **SC-006**: When external lookup is enabled, cached catalog responses resolve in under 50 milliseconds from the local persistent cache.
- **SC-007**: 100% of external catalog network timeouts or connection failures fall back gracefully to local embedded tags without halting the ingestion batch.

## Assumptions

- **Workflow Mode Default**: If a drop/spool folder path is configured, the system defaults to `spool` mode; otherwise, if a general destination library is configured, it defaults to `direct` mode.
- **External Managers**: Downstream music managers (such as `beets`, `Lidarr`, or `Picard`) operate independently as external tools; media-cron's responsibility in `spool` mode is safe, atomic handoff to the manager's import drop directory.
- **Audio Tag Extraction**: Embedded metadata extraction relies on pure Python standard library parsing or lightweight existing project dependencies without requiring heavyweight external runtimes.
- **Companion File Filter**: Common album companion files recognized for bundle preservation include `.jpg`, `.jpeg`, `.png`, `.cue`, `.log`, `.m3u`, and `.m3u8`.
- **Seeding Integrity**: Torrent downloads processed via hardlink mode will retain active seeding in the torrent client while simultaneously making files available in the drop folder or music library.
- **External Catalog Choice**: If external lookup is enabled, MusicBrainz is the primary keyless open catalog provider, with Discogs supported as an optional authenticated secondary provider, both adhering to rate limits and persistent caching.
