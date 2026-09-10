# Feature Specification: Video Organization, Drop-Folder Spooling, and Media Server Library Rescan

**Feature Branch**: `006-video-organization`  
**Created**: 2026-09-09  
**Status**: Ready  
**Input**: User description: "video: Automatic identification should be supported but not required. Dumping media to a folder to be consumed by a library manager, such as *arr stack, that handles identification and organization is also a valid work flow. If we are handling identification and organization we should also have a configurable option to trigger a media player (jellyfin, emby, plex) to rescan the library."

---

## Clarifications & Design Decisions

### Session 2026-09-09
- **Q1: Media Server Notification Scope (FR-008)** → **A**: Single active media server configured at a time (`video.media_server: { provider: "jellyfin" | "emby" | "plex", url: "...", token: "..." }`). Keeps configuration clean, deterministic, and aligns with standard single-home-server setups.
- **Q2: Library Rescan Granularity (FR-010)** → **A**: Target-specific with global fallback: when a library/section ID or path is configured, request a selective refresh of that specific library; if omitted, fall back to triggering a full server library scan.
- **Q3: External Manager Interaction (*arr Stack) (FR-004)** → **A**: Drop-folder filesystem handoff with atomic hidden directory staging (`.incoming_<release>_<uuid>`) and a configurable post-ingest command execution hook (`--video-post-command` / `video.post_ingest_command` supporting `{release_path}` token substitution for custom scripts or curl commands).
- **Q4: Drop Directory Release Name Collision (FR-003)** → **A**: If an incoming release folder name already exists in the drop destination, skip promotion, retain files in staging, and record a warning in telemetry.
- **Q5: Hybrid Workflow Mode Behavior (FR-001)** → **A**: Sanitize folder/file names, pair companion subtitles, and purge clutter/samples before spooling the release into the drop directory.
- **Q6: Direct Mode Destination Collision & Upgrade (FR-006)** → **A**: Quality-aware upgrade: replace existing destination file only if incoming release has a higher resolution rank (2160p > 1080p > 720p), otherwise skip.
- **Q7: Companion Subtitle Language & Descriptor Tagging (FR-007)** → **A**: Preserve detected language codes and descriptor tags (e.g. `.en.srt`, `.forced.srt`, `.sdh.srt`) when renaming sidecars adjacent to the video file, falling back to `<VideoBase>.<sub_ext>` if no language tags exist.
- **Q8: Media Server Rescan Retry Policy (FR-009)** → **A**: Default single-shot attempt (0 retries) with 5.0s timeout; retry attempts are configurable (`max_retries`) and fail non-fatally upon exhaustion.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Video Drop-Folder Spooling for External Managers (*arr Stack) (Priority: P1) 🎯 MVP

A user operating an automated home media pipeline with external library managers (e.g., Sonarr for TV, Radarr for Movies, or generic *arr stack download blackholes) wants incoming video releases deposited directly into a designated drop/spool directory without mandatory internal identification. The external manager handles identification, renaming, and organization. media-cron must preserve the complete release folder hierarchy, bundle companion assets (subtitles, artwork, metadata files), enforce atomic inotify-safe folder promotion (`.incoming_*`), and support optional post-drop command execution.

**Why this priority**: Core user requirement establishing external manager handoff. Provides immediate, standalone value for users whose downstream managers manage naming and tagging.

**Independent Test**: Provide an incoming movie or TV episode directory containing video files, subtitle files, and metadata in staging; execute in spool mode targeting a drop directory; verify that the complete release directory and companion assets are deposited atomically into the drop directory with zero partial or locked files, leaving original torrent seeds intact.

**Acceptance Scenarios**:

1. **Given** a video release directory containing video files (`.mkv`, `.mp4`) and companion assets (`.srt`, `.nfo`, artwork), **When** processed in `spool` mode with `--video-spool-dir`, **Then** the release folder and its contents are deposited into the drop directory while preserving internal hierarchy.
2. **Given** downstream inotify watchers monitoring the drop directory, **When** files are transferred, **Then** media-cron stages files in a hidden directory (`.incoming_<release>_<uuid>`) and atomically promotes the completed folder via directory rename to avoid watcher race conditions.
3. **Given** an optional post-ingest command configured, **When** drop-folder promotion completes successfully, **Then** the command hook is executed with `{release_path}` substituted.

---

### User Story 2 - Autonomous Video Identification & Direct Library Organization (Priority: P2)

A user without external video managers wants media-cron to autonomously inspect video filenames, extract show/movie metadata, resolution, quality, season, and episode cues, sanitize titles, and organize files directly into a structured movie (`Movies/<Title> (<Year>)/...`) or TV show (`TV/<Show>/Season <SS>/...`) destination library, preserving associated subtitles while purging clutter and samples.

**Why this priority**: Delivers complete standalone video organization for users who do not run *arr stack managers.

**Independent Test**: Ingest raw video files and companion subtitles into staging; execute in direct organization mode; verify movies and TV episodes are correctly identified, formatted into destination folder templates, and subtitles are renamed and placed adjacent to their video assets.

**Acceptance Scenarios**:

1. **Given** TV episode video files (e.g., `Show.Name.S02E05.1080p.mkv`), **When** processed in `direct` mode, **Then** the files are sorted into `TV/<Show>/Season 02/<Show> - S02E05 - <Episode> [1080p].mkv`.
2. **Given** Movie video files (e.g., `Movie.Title.2023.2160p.mkv`), **When** processed in `direct` mode, **Then** the files are sorted into `Movies/<Title> (2023)/<Title> (2023) [2160p].mkv`.
3. **Given** associated subtitle files (e.g., `Show.Name.S02E05.en.srt`), **When** organized, **Then** subtitles are preserved and mapped alongside the organized video file.
4. **Given** sample video clips or promotional junk, **When** analyzed, **Then** samples are quarantined or purged according to file size and duration thresholds.

---

### User Story 3 - Configurable Media Server Library Rescan Notification (Priority: P3)

A user running direct library organization in conjunction with a media server (Jellyfin, Emby, or Plex) wants media-cron to automatically notify the media server after newly organized video assets are placed in the library. This triggers an immediate library rescan so new content appears in client players without waiting for periodic filesystem polling intervals.

**Why this priority**: Bridges autonomous organization and immediate consumer playback, fulfilling the explicit user request for media player rescan triggering.

**Independent Test**: Organize video assets into the destination library with media server notification enabled; verify media-cron issues a valid rescan request to the configured media server API with appropriate authentication and debouncing, logging results without interrupting the organization batch if the server is unreachable.

**Acceptance Scenarios**:

1. **Given** a configured media server (Jellyfin, Emby, or Plex) with valid API credentials, **When** direct organization successfully moves video assets to the library, **Then** a consolidated library rescan request is dispatched to the server (targeting specific library section if configured, otherwise full scan).
2. **Given** multiple video files organized in a single batch, **When** rescan notification is triggered, **Then** rescan calls are debounced/aggregated so only a single consolidated notification is sent per affected library rather than flooding the server.
3. **Given** the configured media server is offline, unreachable, or returns an HTTP error, **When** notification is attempted, **Then** media-cron logs a warning and completes the batch without failing or rolling back the organized media files.

---

### User Story 4 - Non-Destructive Simulation, Operational Safety & Observability (Priority: P4)

A system administrator running scheduled cron automation requires safe execution guarantees. The system must support `--dry-run` simulation (predicting drop-folder placements, target library paths, and simulated media server rescan triggers without disk mutations) and emit structured telemetry reporting video processing statistics.

**Why this priority**: Required by Constitution Principle III (Idempotency) and Principle IV (Observability) for automated cron stability.

**Independent Test**: Run `media-cron process --dry-run` against staging directories with video media; verify all proposed operations and simulated notifications are reported in text and JSON output without writing or moving any files.

**Acceptance Scenarios**:

1. **Given** video files in staging processed with `--dry-run`, **When** executed, **Then** the output reports all planned spooling or library relocations and simulated media server notifications without modifying the filesystem.
2. **Given** diagnostic CLI commands (`test-video-identify`, `test-video-spool`, `test-media-server-notify`), **When** invoked, **Then** they display detailed tag extractions, spooling previews, and server ping results in human-readable text or structured JSON.
3. **Given** completed batch execution, **When** summary is rendered, **Then** `video_summary` metrics (scanned, spooled, organized, rescans sent) are included.

---

### Edge Cases

- **Multi-Episode / Multi-Part Files**: Video files covering multiple episodes (e.g. `S01E01-E02`) or split across parts (`CD1/CD2`); in direct mode, the parser must capture episode spans or part suffixes without truncating.
- **Sidecar Subtitles with Differing Naming**: Subtitle files named `2_English.srt` or located in a `Subs/` subdirectory; the system must cluster them with the primary video asset.
- **Drop Directory Release Name Collision**: If an incoming release directory name already exists in the target drop directory, media-cron skips promotion of that release, retains the files intact in staging, and records a collision warning in telemetry.
- **Destination File Collision in Direct Mode**: When a movie or episode file already exists at the destination path, media-cron evaluates resolution rank; higher quality releases trigger an upgrade/replace operation, whereas equal or lower quality incoming releases are skipped without error.
- **Server Offline During Rescan**: Media server down or responding with 5xx/401; notification failures must be recorded as non-fatal warnings without impacting the exit code of successful filesystem operations.
- **Rapid Successive Cron Runs**: Debouncing and locking mechanisms must ensure concurrent or frequent cron jobs do not initiate overlapping rescan requests.
- **Cross-Device Spooling**: When source staging and drop folder are on different mount points, hardlinking falls back seamlessly to copy with verification.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support configurable video workflow modes (`--video-mode` / `video.workflow_mode`): `spool` (handoff to external manager drop folder without renaming), `direct` (autonomous metadata extraction and destination library organization), and `hybrid` (autonomously sanitize folder/file names, pair companion subtitles, and purge clutter/samples, then deposit the cleaned release into the drop directory), automatically defaulting to `spool` whenever a drop directory (`--video-spool-dir`) is supplied, and `direct` otherwise.
- **FR-002**: In `spool` mode, system MUST deposit incoming video releases into a configurable drop/spool directory while preserving the release folder hierarchy and companion assets (subtitles, artwork, `.nfo` files).
- **FR-003**: In `spool` mode, system MUST stage incoming releases in a hidden temporary directory (`.incoming_<release>_<uuid>`) on the drop filesystem and atomically promote the directory via `os.replace` to prevent external watcher race conditions; if a target release directory with the same name already exists in the drop directory, the system MUST skip promotion, retain the staging release intact, and log a warning in telemetry.
- **FR-004**: System MUST support an optional post-ingest command execution hook (`--video-post-command`) executed upon successful drop-folder deposition, providing `{release_path}` token substitution.
- **FR-005**: In `direct` mode, system MUST extract video metadata (title, year, season, episode, quality, resolution, codecs) from filenames and directory structures using regex heuristics without requiring mandatory external network calls.
- **FR-006**: In `direct` mode, system MUST organize video files into standardized directory hierarchies: `Movies/<Title> (<Year>)/...` for movies and `TV/<Show>/Season <SS>/...` for television series, applying quality-aware replacement when destination files already exist (upgrading only if incoming release has a higher resolution rank, skipping otherwise).
- **FR-007**: In `direct` mode, system MUST preserve and rename associated subtitle files (`.srt`, `.vtt`, `.ass`, `.sub`) adjacent to their parent video files, maintaining detected language codes and modifier tags (e.g. `.en.srt`, `.forced.srt`) on the standardized base name, or defaulting to `<VideoBase>.<sub_ext>` when untagged.
- **FR-008**: In `direct` mode, system MUST support a configurable media server library rescan notification option (`video.media_server`) supporting a single active primary server (Jellyfin, Emby, or Plex).
- **FR-009**: Media server notification failures (timeouts, network errors, invalid credentials) MUST NOT fail or roll back already-completed media organization operations; rescan requests MUST default to a single-shot attempt (5.0s timeout) with configurable retry attempts (`video.media_server.max_retries`), recording any exhaustion errors non-fatally in batch telemetry.
- **FR-010**: System MUST aggregate and debounce media server rescan notifications so that a batch with multiple modified files triggers a single consolidated rescan request, targeting specific library section/folder path if configured, or performing full server scan as fallback.
- **FR-011**: System MUST provide diagnostic CLI commands: `test-video-identify` (inspect extracted video tags), `test-video-spool` (test atomic drop staging), and `test-media-server-notify` (test connection and rescan ping to media server) supporting text and JSON output.
- **FR-012**: System MUST enforce 100% predictive `--dry-run` simulation mode reporting planned filesystem operations and simulated media server notifications without modifying disk or invoking remote webhooks.
- **FR-013**: System MUST record video telemetry metrics (`total_videos`, `spooled_releases`, `organized_movies`, `organized_episodes`, `rescan_notifications_sent`, `rescan_errors`) in `BatchSummary.video_summary`.

---

### Key Entities

- **VideoWorkflowMode**: Operational mode enum: `spool`, `direct`, `hybrid`.
- **VideoReleaseBundle**: Represents a clustered video release containing primary video tracks, subtitle files, artwork, and metadata.
- **MediaServerType**: Supported media player/server type enum: `jellyfin`, `emby`, `plex`.
- **MediaServerConfig**: Configuration entity containing server type, base URL, API token, optional library ID / section ID, request timeout, optional max retries (default 0), and enabled flag.
- **MediaServerRescanResult**: Entity tracking media server notification outcome: server type, target endpoint, HTTP status code, duration, success flag, and error detail.
- **VideoSpoolResult**: Outcome of drop-folder staging and post-command execution.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In spool mode, 100% of clustered release files (videos and companions) are deposited with zero partial files exposed to external inotify watchers.
- **SC-002**: In direct mode, TV episodes and movies are organized into their respective directory templates with 100% preservation of associated subtitles.
- **SC-003**: When media server rescan notification is enabled, a batch modifying 1 to 100 files triggers a single debounced rescan request in under 3 seconds without blocking pipeline execution.
- **SC-004**: If the media server is offline, unreachable, or misconfigured, the organization batch completes with exit code 0 and records the notification error in telemetry.
- **SC-005**: In `--dry-run` mode, 0 bytes are written, 0 files are moved, 0 remote rescan calls are dispatched, and 100% of planned actions are accurately predicted.

---

## Assumptions

- External managers (*arr stack) have their own watch folders and file monitoring mechanisms (e.g. Sonarr/Radarr drone factory or folder scanner).
- Jellyfin, Emby, and Plex provide accessible HTTP REST APIs for library refresh when supplied with a valid API key or token.
- Video files follow common scene or P2P naming conventions (e.g. `Show.Name.S01E02.1080p.mkv` or `Movie.Title.2024.UHD.mp4`).
- Media server notification is an optional post-organization enhancement and does not prevent standalone usage without media servers.
