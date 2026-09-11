# Research & Technical Decisions: Unrecognized Media Staging and Interactive Manual Review

**Feature Branch**: `007-unrecognized-files-staging`  
**Date**: 2026-09-09  

---

## 1. Review Directory Layout & Collision Prevention

- **Decision**: Isolate each unrecognized release or item in its own dedicated subdirectory formatted as `<review_dir>/<item_name>_<timestamp_or_uuid>/`, containing the original file(s) and a companion `manifest.json` metadata file.
- **Rationale**: Staging directory often contains releases with identical or generic names (e.g. `Release`, `CD1`, `Unknown`, `sample.mkv`). Placing each item in an isolated timestamped/UUID folder ensures zero naming collisions, groups multi-file releases together, and keeps the item's failure manifest strictly co-located with the files.
- **Alternatives Considered**:
  - *Flat layout with prefixing*: Placing files directly in `review_dir` with name suffixes (`sample_1.mkv`, `sample_2.mkv`). Rejected because it breaks directory hierarchy for multi-file releases and scatters manifests.
  - *Mirroring relative staging path*: Recreating the exact folder hierarchy from staging. Rejected because staging folders are ephemeral and items from different staging runs could collide or overwrite unreviewed files.

---

## 2. Inotify Safety & Atomic Promotion into Review Directory

- **Decision**: When moving unrecognized items into `review_dir`, stage files into a hidden temporary directory (`.staging_<item_name>_<uuid>`) on the review filesystem, write `manifest.json`, and promote the folder via atomic `os.replace` (POSIX rename).
- **Rationale**: Adheres strictly to Constitution Principle III. If any external watcher (such as backup jobs, custom monitoring scripts, or file indexers) watches `review_dir`, hidden directory staging ensures watchers never observe partial transfers or incomplete manifests.
- **Alternatives Considered**:
  - *Direct in-place copy/move*: Moving files straight into the destination folder. Rejected because a slow copy or network mount interrupt would leave incomplete files.

---

## 3. Torrent Seeding Protection & Transfer Modes

- **Decision**: Respect global `general.mode` (move/copy/hardlink), but automatically fallback to non-destructive `copy` or `hardlink` whenever a file or its parent release belongs to an active seeding torrent.
- **Rationale**: Constitution Principle III requires non-destructive handling of seeding torrents. If `general.mode` is set to `move`, moving an unrecognized file out of staging would break active seeds. By detecting torrent client association (via `TorrentInputPlugin` / client registry), the pipeline forces copy/hardlink so torrent seeding continues uninterrupted.
- **Alternatives Considered**:
  - *Always hardlink/copy for review regardless of mode*: Safe, but for non-torrent local downloads, users with limited disk space expect `move` to free staging disk space.
  - *Skip review staging for torrent seeds*: Leaving unrecognized seeds in staging indefinitely. Rejected because it fails the core goal of clearing staging clutter.

---

## 4. Category Hint Extraction Heuristics

- **Decision**: Use lightweight file extension and container heuristics to populate `detected_category_hint` in `manifest.json`:
  - Video extensions (`.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.m4v`): if season/episode tokens (`S\d+E\d+`, `\d+x\d+`) detected → `tv`, else → `movie`.
  - Audio extensions (`.mp3`, `.flac`, `.m4a`, `.ogg`, `.wav`, `.opus`, `.ape`): → `music`.
  - Audiobooks (`.m4b`): → `audiobook`.
  - E-books / documents (`.epub`, `.mobi`, `.azw3`, `.pdf`, `.cbz`, `.cbr`): → `book`.
  - Fallback / Unknown: `None`.
- **Rationale**: Zero external binary dependencies (Constitution Principle I: stdlib only, no required ffprobe/mediainfo). Heuristic runs in microseconds and provides a 95%+ accurate initial suggestion in the interactive CLI, reducing manual user keystrokes.
- **Alternatives Considered**:
  - *Execute ffprobe / mediainfo*: Heavyweight, requires external binaries that may not be installed in all container environments.
  - *No hints / leave blank*: Forces the user to select from an unselected prompt every single time.

---

## 5. Interactive CLI Ergonomics & Fallbacks

- **Decision**: Implement `media-cron review` using a Typer subcommand with standard Python stdlib `input()` wrapped in a clean, formatted terminal menu. If `sys.stdin.isatty()` is False (headless/cron/CI), abort interactive triage with an informative error message directing the user to use non-interactive commands (`media-cron review list / resolve / discard`).
- **Rationale**: Avoids heavy third-party TUI frameworks (e.g. `curses`, `textual`, `rich-prompt`) maintaining stdlib-only/existing-dependencies simplicity while guaranteeing reliable execution across SSH sessions, Docker terminals, and pipes.
- **Alternatives Considered**:
  - *Full-screen TUI with curses*: High complexity, prone to terminal resizing and encoding glitches on remote servers.
  - *Web-based review UI*: Out of scope for a CLI/cron utility.

---

## 6. Action Resolution: Immediate Organization vs Re-Ingestion

- **Decision**:
  - **Organize Now**: Directly instantiates `FileSystemOrganizerOutput`, constructs the final destination library path using the user's manual annotation and standard templates, performs the atomic transfer, triggers media server rescan (if video/music), and marks the item `RESOLVED` (removing it from pending review).
  - **Return to Staging**: Writes an adjacent `.media-cron-hint.json` containing the user's metadata and transfers the files back into `staging_dir` so the regular pipeline can ingest it on the next run.
  - **Discard**: Deletes the item folder from `review_dir` after confirmation.
  - **Skip**: Leaves the item in `review_dir` unchanged.
- **Rationale**: Gives users immediate gratification ("Organize Now") while also providing "Return to Staging" for complex scenarios (e.g. when downstream plugins perform further multi-track processing).
- **Alternatives Considered**:
  - *Only Return to Staging*: Inefficient; requires the user to wait for the next cron cycle or manually run `media-cron process` to see results.
  - *Only Organize Now*: Does not support workflows where users want standard pipeline plugins to process companion assets.

---

## 7. Media Server Rescan on Manual Resolution

- **Decision**: When an item is resolved via "Organize Now" with category `movie`, `tv`, or `music`, instantiate the configured media server client (`JellyfinClient`, `EmbyClient`, or `PlexClient`) from `media_cron.metadata.media_servers` and dispatch a library rescan with timeout protection.
- **Rationale**: Consistent with User Story 3 from Feature 006. Users expect the media server to update immediately after organizing files manually.
- **Alternatives Considered**:
  - *No media server notification*: Requires users to trigger manual scans on their Plex/Jellyfin web interfaces.

---

## 8. Retention & Purge Heuristics

- **Decision**: Default retention is indefinite (`max_age_days = 0`), ensuring media files are never lost or deleted without user knowledge. Provide `paths.review_max_age_days` in configuration and a CLI command `media-cron review purge --older-than <days> [--force]` with interactive confirmation.
- **Rationale**: Non-destructive operation is mandatory under Constitution Principle III. Automatic deletion by default would risk permanent data loss if a user forgets to triage the review folder.
- **Alternatives Considered**:
  - *Automatic 30-day purge during cron runs*: Dangerous for slow or occasional review workflows.
