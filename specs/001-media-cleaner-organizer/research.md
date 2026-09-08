# Research: Standalone Media File Organizer and Cleaner CLI

This document captures technical evaluations, architectural decisions, and best practices for implementing the pluggable Media-Cron organizer.

---

## 1. Pluggable Architecture Strategy

### Context & Requirements
The user requires all three primary interfaces—**input**, **lookup**, and **output**—to be fully pluggable with sane out-of-the-box defaults:
- **Input plugins**: Discover and ingest raw media candidates. Sane default: `DirectoryScannerInput`.
- **Lookup plugins**: Extract and enrich metadata (title, category, year, season, episode, artist, album, resolution, bitrate). Sane defaults: `SceneRegexLookup` (video), `AudioTagLookup` (audio), `BookMetaLookup` (e-books).
- **Output plugins**: Organize and relocate verified media. Sane defaults: `LibraryOrganizerOutput` (standard target hierarchy) and `SeedRelocatorOutput` (relocate source to dedicated seeding directory).

### Decision
Implement a decoupled **Plugin Registry pattern** utilizing Python's standard `abc.ABC` and `typing.Protocol`.
- Plugins register via decorator or explicit registration in a `PluginRegistry`.
- Standard plugin lifecycles and contracts defined:
  - `InputPlugin`: `discover(source_path: Path, config: Config) -> Iterable[DiscoveredItem]`
  - `LookupPlugin`: `can_handle(item: DiscoveredItem) -> bool` and `enrich(item: DiscoveredItem) -> MediaAsset`
  - `OutputPlugin`: `execute(plan: OperationPlan, dry_run: bool) -> OperationResult`

### Rationale
- Zero heavyweight external framework dependency (like Stevedore or Pluggy), keeping Media-Cron lightweight, container-friendly, and easy to audit.
- Strict type-checking with Python 3.11 `typing.Protocol` ensures high compile-time / lint-time contract enforcement.
- Sane defaults are pre-registered built-ins, but custom plugins can be easily loaded via Python entry points or dynamic module imports.

### Alternatives Considered
- *Pluggy (pytest's plugin system)*: Powerful hook specification, but introduces overhead and complex hook calling semantics unnecessary for deterministic linear media pipelines.
- *Entry points only*: Relies on package installation metadata; less flexible for standalone scripts or lightweight Docker deployments.

---

## 2. Staging & Seeding Pipeline Workflow

### Context & Requirements
- **Staging Directory**: All incoming data must be moved to a user-configurable staging directory first so original download files/staging areas are safe from partial processing.
- **Seed Directory**: A user-configurable option to relocate source material to a seed directory (e.g. for long-term torrent seeding) while linking/moving the organized media to the target library.

### Decision
Implement a three-zone pipeline architecture:
1. **Source / Incoming**: Raw download directory (scanned by `InputPlugin`).
2. **Staging Directory (`staging_dir`)**:
   - Files are moved from Source into Staging atomically.
   - If Source must remain untouched, hardlinks from Source to Staging are used (if on the same filesystem), or files are copied.
   - Staging holds the active process lockfile (`.media-cron.lock`).
3. **Seed Directory (`seed_dir`, optional)**:
   - When configured, the original file is linked or moved to `seed_dir` with its original naming preserved so torrent clients continue seeding without interruption.
4. **Destination Library (`destination_dir`)**:
   - Clean, sanitized, organized files are created in `destination_dir` via atomic hardlink (preferred to preserve disk space) or atomic move from Staging.

```
[Raw Incoming / Torrent]
       │
       ▼ (Atomic Move / Ingest)
[Staging Directory] ─── (Lockfile acquired)
       │
       ├─────────────────────────────────┐
       ▼ (Seed Mode Configured)          ▼ (Organize & Sanitize)
[Seed Directory]                  [Target Media Library]
(Original Name for Seeding)      (Clean Plex/Jellyfin Hierarchy)
```

### Rationale
- Ensures raw incoming directories are not locked or polluted with temporary organization artifacts.
- Guarantees complete separation of concerns between seeding preservation and media server consumption.
- Prevents torrent clients from crashing or re-downloading when files are renamed.

---

## 3. Metadata Extraction & Filename Sanitization

### Decision
1. **Video (Movies & Series)**:
   - High-performance regex parser that removes common scene tags (`1080p`, `2160p`, `WEB-DL`, `BluRay`, `x264`, `x265`, `HEVC`, `AAC5.1`, release group tags like `-FLUX`, `-SPARKS`).
   - Identifies standard season/episode tokens: `S\d+E\d+`, `\d+x\d+`, `Season \d+`, `Episode \d+`.
   - Identifies 4-digit release years `(19\d{2}|20\d{2})`.
2. **Audio (Music & Audiobooks)**:
   - Lightweight metadata inspection (e.g. `tinytag` or `mutagen`) to extract ID3/Vorbis tags: `artist`, `album`, `title`, `track`, `year`. Falls back to filename regex pattern: `(\d+)[- .]+(.+)`.
3. **E-books**:
   - EPUB: inspect `META-INF/container.xml` and OPF package document for `<dc:title>` and `<dc:creator>`.
   - PDF: inspect standard PDF document info dictionary (`/Title`, `/Author`).
   - Fallback: parse `Author - Title (Year)` from filename.

### Alternatives Considered
- *External API lookups (TMDB/MusicBrainz) by default*: Rejected for default pipeline. External API requests introduce network dependencies, rate limits, API keys, and latency. Sane defaults MUST work offline and deterministically; API lookups should be secondary pluggable plugins.

---

## 4. Container Integrity Verification

### Decision
Perform lightweight, fast non-destructive container validation:
1. **File Size Check**: Ensure file size exceeds minimal sanity threshold (e.g., > 10MB for video, > 100KB for audio/books).
2. **Container Header & Atom Validation**:
   - **MKV (Matroska)**: Verify standard EBML header signature (`0x1A 0x45 0xDF 0xA3`) and ensure readable segment cluster elements.
   - **MP4 / M4V**: Verify presence of valid `ftyp` box in first 64 bytes and find valid `moov` atom.
   - **Audio (MP3/FLAC/M4A)**: Verify `ID3` / `fLaC` magic bytes.
   - **EPUB / PDF**: Verify standard ZIP header (`PK\x03\x04`) for EPUB or `%PDF-` header for PDF.
3. **Subprocess verification (optional/fallback)**:
   - If `ffprobe` is detected in system `PATH`, invoke `ffprobe -v error -show_entries format=duration` with a short 3-second timeout for definitive stream validation.

---

## 5. Concurrency Control & File Locking

### Decision
- Use standard POSIX `fcntl.flock` with `LOCK_EX | LOCK_NB` on a dedicated `.media-cron.lock` file created inside the configured `staging_dir`.
- If lock cannot be acquired (returns `BlockingIOError` or `EWOULDBLOCK`), log an informational notice and exit immediately with status code `1` (busy/skip).
- On process termination (normal or exception), lock is automatically released by the OS when file descriptor closes, with explicit cleanup in Python `finally` / context manager blocks.

---

## 6. Summary of Key Decisions

| Area | Chosen Solution | Primary Advantage |
|---|---|---|
| **Plugin System** | In-tree `abc.ABC` + `PluginRegistry` | Zero external dependencies; strict static typing; easy test mocking |
| **Ingestion Staging** | Atomic move into dedicated `staging_dir` | Original download folder freed up; source immutability guaranteed |
| **Seeding Support** | Dedicated `SeedRelocatorOutput` plugin | Preserves seeding filenames via hardlink/move to separate folder |
| **Collision Resolution** | Quality upgrade (bitrate/resolution) | Automatically keeps best version without manual intervention |
| **Integrity Checks** | Magic bytes + atom inspection + optional ffprobe | Blazing fast offline validation; halts corrupted containers |
| **Concurrency** | Non-blocking `fcntl.flock` in `staging_dir` | Eliminates race conditions in recurring cron jobs |
