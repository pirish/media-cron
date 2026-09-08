# Feature Specification: Standalone Media File Organizer and Cleaner CLI

**Feature Branch**: `001-media-cleaner-organizer`

**Created**: 2026-09-04

**Status**: Draft

**Input**: User description: "Standalone media file organizer and cleaner CLI tool (sanitizes filenames, removes junk files, checks integrity, and handles atomic moves/hardlinks)"

## Clarifications

### Session 2026-09-04

- Q: How should the tool handle external subtitle files (such as `.srt`, `.ass`, or `.sub`) that accompany video downloads? → A: Preserve and rename matching subtitle files alongside the video asset into the destination library.
- Q: What directory hierarchy structure should the organizer build when transferring media into the destination library? → A: Custom template-driven structure with user-definable path formatting patterns in configuration, defaulting to standard nested convention (Movies: `Movies/{title} ({year})/{title} ({year}).{ext}`, TV: `TV Shows/{show}/Season {season:02d}/{show} - S{season:02d}E{episode:02d}.{ext}`).
- Q: How should the tool handle filename collisions when a file already exists at the destination with different content and no overwrite flag is specified? → A: Quality-based upgrade: Replace the destination file if the incoming file has a higher detected resolution or bitrate; otherwise skip and preserve the existing file while logging the outcome.
- Q: What media formats are in scope for organization and cleanup in this feature? → A: All digital media (Video, Audio, and E-books/Audiobooks) with modular format-specific metadata extraction and organization rules.
- Q: How should the tool handle concurrency when a scheduled or manual execution starts while another instance is already processing the same directories? → A: Directory lockfile with immediate safe exit: Acquire a non-blocking lock file in the root staging directory; if active, log a concurrency notice and exit immediately without mutating files.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Safe Inspection and Dry-Run Simulation (Priority: P1)

A media collection administrator wants to run the tool in a non-destructive simulation mode against a downloaded folder containing mixed digital media (video, audio, and literature) so they can preview all proposed renames, junk file purges, and destination file movements before committing any changes to disk.

**Why this priority**: Essential safety baseline. Users must never risk data loss or unexpected mass file renames. Building simulation capability first establishes the planning engine before any destructive or mutating operations are permitted.

**Independent Test**: Execute the command with the simulation flag against a directory with mixed scene releases, music tracks, e-books, and junk files; verify the tool outputs a complete, structured preview of planned operations while asserting that file checksums, timestamps, and directory contents remain completely unchanged.

**Acceptance Scenarios**:

1. **Given** a directory containing mixed media files (videos, audio albums, e-books) with clutter and junk artifacts, **When** evaluated in dry-run simulation mode, **Then** the tool outputs the planned rename, cleanup, and destination paths for every recognized media type without altering or deleting any file on disk.
2. **Given** an already clean and organized media directory, **When** evaluated in dry-run simulation mode, **Then** the tool reports zero necessary actions and exits with a successful status.

---

### User Story 2 - Junk File Purging and Filename Sanitization (Priority: P2)

An automated download system or administrator wants clutter (such as `.nfo`, `.url`, `.txt` files, sample clips, track playlists, and release group spam) removed, and messy media filenames sanitized into standardized title formats suitable for media indexing across video, audio, and e-books.

**Why this priority**: Directly solves the pain of cluttered downloads and unparsed titles, transforming raw downloaded payloads into clean assets across all supported media formats.

**Independent Test**: Run cleanup and sanitization on an isolated folder containing sample files and messy filenames; verify that junk files are deleted, empty parent directories are pruned, and media files are cleanly renamed.

**Acceptance Scenarios**:

1. **Given** a download folder containing `.nfo`, `.txt`, `.url` shortcuts, and a sample clip under the size threshold, **When** cleanup is executed, **Then** the clutter files and sample clip are deleted and empty directories are pruned.
2. **Given** a video file named with scene metadata (e.g. `Movie.Name.2024.1080p.WEB-DL.DDP5.1.Atmos.H.264-FLUX.mkv`), **When** sanitization is executed, **Then** the filename is normalized to a clean standard format (e.g. `Movie Name (2024).mkv`).
3. **Given** a video file accompanied by matching subtitle files (e.g. `Movie.Name.2024.en.srt`), **When** cleanup and sanitization are executed, **Then** the subtitle file is preserved, renamed to match the sanitized video title (e.g. `Movie Name (2024).en.srt`), and kept with the video asset.
4. **Given** an audio track or e-book with release tags (e.g. `01-artist_name-track_title-2023-group.mp3` or `Author Name - Book Title (v1.0) [epub].epub`), **When** sanitization is executed, **Then** the filenames are normalized to clean standardized formats.

---

### User Story 3 - Atomic Library Organization via Moves or Hardlinks (Priority: P3)

An automated pipeline needs to transfer verified media files into an organized target library structure (such as dedicated Movie, TV Show, Music, Audiobook, or Book directories) using customizable path patterns and atomic file operations or hardlinks so that ongoing torrent seeding is preserved without duplicating storage.

**Why this priority**: Bridges the gap between download staging areas and permanent media server libraries, enabling continuous seeding while keeping libraries clean and formatted to the user's preferred layout.

**Independent Test**: Provide source files and specify a target library with hardlink mode; verify that hardlinks are created at the formatted destination path according to the configured directory template, inode numbers match on POSIX filesystems, and the source file remains untouched for seeding.

**Acceptance Scenarios**:

1. **Given** a verified media file (video, audio, or book), a configured path pattern, and a target library directory on the same filesystem, **When** hardlink mode is executed, **Then** a link is created in the destination directory matching the resolved path template while leaving the source file intact.
2. **Given** a destination file that already exists with an identical file size and checksum, **When** organization is executed, **Then** the system detects the existing match, skips re-linking or overwriting, and completes idempotently without error.
3. **Given** a destination video or audio file that already exists with lower resolution or bitrate than the incoming file, **When** organization is executed, **Then** the higher-quality file replaces the lower-quality predecessor and the upgrade is recorded in the batch summary.

---

### User Story 4 - Media Integrity Verification Prior to Relocation (Priority: P4)

A pipeline needs to confirm that a media file is complete and readable before transferring it into the primary library, preventing truncated, empty, or corrupt files from entering production collections.

**Why this priority**: Prevents bad downloads from displacing good existing files or triggering media server indexer errors across video, audio, and e-book collections.

**Independent Test**: Feed an intentionally truncated or corrupted media container (video, audio, or book) to the tool; verify that the tool detects the corruption, flags the file, halts organization for that asset, and returns a dedicated warning/failure status code.

**Acceptance Scenarios**:

1. **Given** an incomplete or corrupted media file (truncated video/audio container or malformed e-book archive), **When** integrity verification runs, **Then** the file is marked invalid, excluded from destination library relocation, and reported in the failure summary.
2. **Given** a fully intact media file, **When** integrity verification runs, **Then** the verification succeeds and the file proceeds to the organization phase.

---

### Edge Cases

- What happens when a destination filename already exists but has different content? The system compares media quality metrics (resolution/bitrate for video/audio, and edition/file size for books); if the incoming file is a higher-quality release, it replaces the destination file (safely unlinking the predecessor). If the incoming file is of equal or lower quality, the existing file is preserved and the incoming file is skipped with a collision log notice.
- What happens when the user requests hardlinks across two different filesystem mount points? The system must detect that cross-device hardlinks are unsupported, notify the user with an actionable message, and either halt or fall back to copy mode only if explicitly configured.
- What happens when a media filename contains non-standard unicode characters, emojis, or illegal filesystem symbols (`:`, `/`, `\`, `*`, `?`, `"`, `<`, `>`, `|`)? The system must sanitize or replace invalid characters safely according to the target operating system's filesystem rules while preserving the semantic title.
- What happens when an active download client is still writing to a media file? The system must detect open write handles or `.part` extensions and skip the file until downloading is finalized.
- What happens when the user or daemon lacks write permissions to the destination directory? The system must abort before performing any partial modifications, log a descriptive permission error, and exit with an error code.
- What happens when orphan subtitle files exist without an associated video file? The system must skip orphan subtitles or leave them intact rather than mistakenly purging them as clutter.
- What happens when custom path template tokens are missing in the media metadata (e.g. missing release year or album)? The system must gracefully fallback to a sanitized title without the missing token rather than producing broken paths or erroring.
- What happens when multiple audio tracks or book chapters are in a single folder? The system must identify disc/track ordering and preserve multi-part hierarchies.
- What happens when a second execution starts while a previous run is still active? The system encounters the active directory lock file, logs an informational notice that another instance is running, and exits cleanly immediately with exit code 1 to avoid race conditions and duplicated filesystem actions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a non-destructive dry-run mode that outputs all planned renames, deletions, and moves without making modifications to the filesystem.
- **FR-002**: System MUST identify, categorize, and sanitize media titles across video (movies/series), audio (music tracks/albums/audiobooks), and literature (e-books) by extracting relevant metadata (title, artist/author, year, season/episode, album, track number) and standardizing filenames.
- **FR-003**: System MUST identify and delete non-media junk files (including `.nfo`, `.txt`, `.url`, `.sfv`, `.exe`, `.m3u`) based on a configurable list of extensions, while explicitly preserving associated external subtitle files (`.srt`, `.ass`, `.sub`, `.vtt`) and embedded artwork files.
- **FR-004**: System MUST detect and remove sample video clips below a configurable duration or file size threshold (defaulting to 50 MB).
- **FR-005**: System MUST prune empty parent folders after all contained files have been processed, moved, or deleted.
- **FR-006**: System MUST perform pre-transfer integrity verification on media files (valid containers and readable stream headers for video/audio, and valid container/archive headers for e-books).
- **FR-007**: System MUST support atomic file placement into a destination hierarchy via hardlink, move, or copy operations.
- **FR-008**: System MUST operate idempotently; running the tool multiple times against the same input and target directories without new files MUST result in zero changes and a clean exit.
- **FR-009**: System MUST support quality-aware collision handling: when an incoming asset matches the destination path of an existing file, the system MUST evaluate media resolution, bitrate, or edition quality, automatically upgrading the destination if the incoming asset has higher quality, or preserving the destination and skipping if equal or lower quality.
- **FR-010**: System MUST support dual output formats: human-readable formatted text for interactive console use, and structured JSON output for script and cron automation.
- **FR-011**: System MUST exit with deterministic, documented exit codes (0 for success, 1 for partial skip/warning/locked, 2 for invalid arguments/config, 3 for filesystem/permission errors).
- **FR-012**: System MUST identify associated external subtitle files (`.srt`, `.ass`, `.sub`, `.vtt`) matching the base media name or language tag, sanitize their names to match the cleaned video title, and transfer them alongside the parent video asset into the destination library.
- **FR-013**: System MUST support user-configurable destination path templates for each media category:
  - Movies: defaults to `Movies/{title} ({year})/{title} ({year}).{ext}`
  - TV Shows: defaults to `TV Shows/{show}/Season {season:02d}/{show} - S{season:02d}E{episode:02d}.{ext}`
  - Music: defaults to `Music/{artist}/{album}/{track:02d} - {title}.{ext}`
  - Audiobooks: defaults to `Audiobooks/{author}/{title}/{track:02d} - {title}.{ext}`
  - Books: defaults to `Books/{author}/{title}.{ext}`
- **FR-014**: System MUST enforce single-instance concurrency control using a non-blocking directory lock file in the root staging directory; if an existing lock is held, the system MUST log a concurrency notification and exit immediately with exit code 1 without modifying any files.

### Key Entities *(include if feature involves data)*

- **Media Asset**: Represents a discovered media file (attributes: source path, media category [video, audio, book], discovered title, secondary metadata [artist/author/album/year/season/episode/track], quality metrics [resolution, bitrate], file extension, file size, integrity status, list of associated subtitle/asset files).
- **Operation Plan**: Represents the planned action for an item (attributes: operation type [rename, link, move, copy, delete, upgrade], source path, target path, status, rule rationale).
- **Path Template**: Represents a configurable pattern for target directory and file formatting with variable substitutions per media category.
- **Batch Summary**: Represents the aggregated outcome of an execution (attributes: total scanned, processed count, upgraded count, junk purged count, skipped count, error count, execution duration).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dry-run simulation mode accurately predicts 100% of the actual operations executed during live runs with zero disk writes.
- **SC-002**: 95% or more of standard scene release and tagged download filenames across video, audio, and books are accurately parsed and sanitized into clean library naming without manual corrections.
- **SC-003**: Corrupt or truncated media containers across all supported formats are identified and halted 100% of the time, with zero corrupt files moved into destination libraries.
- **SC-004**: A batch of 50 downloaded items is scanned, verified, and organized in under 5 seconds (excluding physical cross-disk copy transfer times).
- **SC-005**: Re-running the tool against an already organized library executes with 0 redundant writes or re-links.
- **SC-006**: 100% of matching subtitle files accompanying organized media assets are preserved and relocated with matching sanitized filenames.
- **SC-007**: 100% of valid custom path templates correctly resolve without path escaping errors or unexpanded tokens.
- **SC-008**: 100% of collision upgrades accurately replace lower-resolution/bitrate destination files with higher-quality files without leaving dangling files or half-written streams.
- **SC-009**: 100% of concurrent executions on locked staging directories exit cleanly without file modification, deadlock, or race conditions.

## Assumptions

- Source files are processed in a local or network-attached filesystem accessible via standard file path APIs.
- When hardlinking is requested, the source and destination directories reside on the same filesystem volume.
- Video files contain identifiable title and year/season/episode metadata in file or folder names; audio and e-book files contain recognizable metadata tags or formatted filenames.
- The user executing the tool has sufficient read permissions on source directories and write permissions on target directories.
