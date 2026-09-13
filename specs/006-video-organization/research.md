# Research: Video Organization, Drop-Folder Spooling, and Media Server Rescan

**Feature**: `006-video-organization`
**Date**: 2026-09-09
**Status**: Complete

---

## 1. Video Drop-Folder Spooling & Release Bundling

### Decision
Implement `VideoReleaseBundleAggregator` and `VideoSpoolEngine` in `media_cron/metadata/video_bundler.py` and `media_cron/metadata/video_spooler.py`, mimicking the battle-tested architecture of the music spooler (`MusicSpoolEngine`).

### Rationale
- External media managers (Sonarr for TV, Radarr for Movies, or generic *arr download watch folders) monitor input folders using inotify filesystem watchers.
- Directly copying large video files (often 2GB–30GB for 1080p/4K releases) directly into the watch folder leads to catastrophic race conditions where the manager attempts to process partial in-flight files.
- Staging into a hidden directory on the target drop filesystem (`<spool_dir>/.incoming_<release_name>_<uuid>/`) and using atomic `os.replace` rename guarantees zero partial files are exposed to external watchers (Constitution Principle III).
- Grouping video files alongside companion assets (subtitles `.srt`, `.vtt`, `.ass`, `.sub`, `.idx`, metadata `.nfo`, and posters/artwork) ensures the downstream manager receives complete release context.
- Hardlinking is prioritized when source and drop directory share the same mount point, ensuring instant, zero-copy handoffs compatible with active torrent seeding.
- **Drop Folder Collision Handling**: If a directory with the same release name already exists in the drop directory (e.g. from an in-progress import or duplicate download), media-cron skips promotion of that release, retains files intact in staging, and logs a warning in telemetry, preventing corruption of external manager ingest pipelines.
- **Hybrid Workflow Mode**: When operating in `hybrid` mode, media-cron autonomously sanitizes directory/file names (clean titles, resolution tags), pairs companion subtitles, and purges clutter/samples before spooling the clean release into the drop directory.

### Alternatives Considered
- *Polling / File Lock Checking*: Wait for file write locks to release before alerting the downstream manager. Rejected: inotify triggers on initial file creation, causing downstream managers to immediately lock or fail before polling checks can run.
- *Writing Directly without Hidden Prefix*: Relying on `.partial` file extension renames. Rejected: *arr stack applications monitor directories and often import directory bundles rather than individual files, making directory-level atomic promotion essential.

---

## 2. Media Player & Server Library Rescan Protocols (Jellyfin, Emby, Plex)

### Decision
Implement a pure Python standard-library `MediaServerClientProtocol` and adapters for Jellyfin, Emby, and Plex in `media_cron/metadata/media_servers/` using `urllib.request`.

### Server API Analysis & Endpoints

| Media Server | Auth Header | Global Refresh Endpoint | Targeted Refresh Endpoint | Method |
|---|---|---|---|---|
| **Jellyfin** | `X-Emby-Token: <token>` or `Authorization: MediaBrowser Token="<token>"` | `/Library/Refresh` | `/Items/{section_id}/Refresh` or `/Library/Media/Updated` | `POST` |
| **Emby** | `X-Emby-Token: <token>` | `/Library/Refresh` | `/Items/{section_id}/Refresh` | `POST` |
| **Plex** | `X-Plex-Token: <token>` | `/library/sections/all/refresh` | `/library/sections/{section_id}/refresh[?path=...]` | `GET` |

### Error Handling, Retry Policy & Non-Blocking Execution
- All media server calls use an explicit timeout (default: 5.0 seconds).
- **Retry Policy**: Default single-shot attempt (0 retries). Configurable via `max_retries` (e.g. 1–3 retries with short backoff) for environments with intermittent network connectivity.
- Failures (network unreachable, DNS failure, 401 Unauthorized, 404, 500, retry exhaustion) return a structured `MediaServerRescanResult(success=False, error=...)` and log a warning.
- Under no circumstances does a media server notification failure abort, roll back, or fail an already-completed media organization run (exit code remains 0).

### Batch Aggregation & Debouncing
- When a cron run organizes 50 TV episodes or 5 movies, sending 55 HTTP requests causes unnecessary CPU load and potential rate-limiting on the media server.
- In `Pipeline`, media server rescan notifications are collected during asset organization and debounced: exactly one consolidated rescan request is dispatched per unique target server/library section after the batch organization phase completes.

### Alternatives Considered
- *Third-Party SDKs (e.g. `plexapi`, `jellyfin-apiclient-python`)*: Rejected: violates Constitution Principle and Core Constraint of zero new runtime dependencies. The REST endpoints required for library refresh are simple HTTP calls easily handled by `urllib.request`.
- *Async Background Daemons*: Rejected: media-cron is a deterministic CLI and scheduled cron tool. Synchronous requests with short timeouts (3–5s) are clean, predictable, and container-friendly.

---

## 3. Autonomous Video Identification & Direct Library Naming

### Decision
Leverage and extend `SceneVideoLookup` (`media_cron/plugins/lookup/video.py`) to extract metadata (Show, Season, Episode, Title, Year, Resolution, Source Quality, Audio/Video Codecs) using regex heuristics, organizing into standard library templates.

### Structure & Path Formatting
- **Movies**:
  `Movies/<Title> (<Year>)/<Title> (<Year>) [<Quality>].<ext>`
  Example: `Movies/Inception (2010)/Inception (2010) [1080p BluRay].mkv`
- **TV Shows**:
  `TV/<Show>/Season <SS>/<Show> - S<SS>E<EE> - <Title> [<Quality>].<ext>`
  Example: `TV/Breaking Bad/Season 01/Breaking Bad - S01E01 - Pilot [1080p WEB-DL].mkv`
- **Sidecar Subtitles**:
  Automatically matched and renamed adjacent to the organized video file, preserving detected ISO 639 language codes and modifier tags (e.g. `Breaking Bad - S01E01 - Pilot [1080p WEB-DL].en.srt`, `.forced.srt`, `.sdh.srt`), defaulting to `<VideoBase>.<ext>` when untagged.
- **Destination Collision & Upgrade**:
  When destination movie/episode files already exist, apply quality-aware replacement (replace if incoming resolution rank 2160p > 1080p > 720p is higher, skip otherwise).
- **Sample & Clutter Filtering**:
  Files matching sample patterns (e.g. `*sample*.mkv`) with file size `< 50MB` or short duration are recognized as junk/samples and purged or quarantined, preventing library pollution.

---

## 4. CLI Ergonomics, Dry-Run Simulation & Telemetry

### Decision
Extend `media-cron process` / `run` with dedicated video flags, add diagnostic inspection tools, enforce 100% predictive `--dry-run` simulation, and record metrics in `BatchSummary.video_summary`.

### CLI Options
- `--video / --no-video`: Global video toggle.
- `--video-mode [spool|direct|hybrid]`: Operational workflow mode (inferred as `spool` if `--video-spool-dir` is passed, otherwise `direct`).
- `--video-spool-dir <PATH>`: Drop folder for external managers.
- `--video-post-command <CMD>`: Post-ingest command hook with `{release_path}`.
- `--media-server-provider [jellyfin|emby|plex]`: Active media server.
- `--media-server-url <URL>`: Base URL of media server.
- `--media-server-token <TOKEN>`: API token/key.
- `--media-server-library-id <ID>`: Optional targeted library/section ID.
- `--media-server-max-retries <INT>`: Max retry attempts for rescan notifications (default: 0).

### Diagnostic Commands
- `test-video-identify <PATH> [--format text|json]`: Non-destructive extraction of video tags and companion files.
- `test-video-spool <SOURCE_PATH> --spool-dir <DIR> [--dry-run]`: Test release folder bundling and atomic promotion.
- `test-media-server-notify [--format text|json]`: Test connectivity and rescan ping against configured media server.
