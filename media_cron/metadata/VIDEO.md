# Video Organization, Drop-Folder Spooling, and Media Server Rescan Subsystem

The `media_cron.metadata` video subsystem provides automated video library organization, drop-folder ingestion for external media managers (e.g., the `*arr` stack: `Sonarr`, `Radarr`), autonomous direct library organization with resolution/quality-aware collision upgrades, sidecar companion subtitle tag preservation, and non-blocking, debounced library rescan notifications to `Jellyfin`, `Emby`, and `Plex` media servers.

---

## Subsystem Architecture

```
media_cron/
├── metadata/
│   ├── base.py                   # VideoSpoolEngineProtocol, MediaServerClientProtocol
│   ├── models.py                 # VideoReleaseBundle, VideoTrack, VideoCompanionAsset, etc.
│   ├── video_bundler.py          # VideoReleaseBundleAggregator (tracks, subdirs, companions, samples)
│   ├── video_spooler.py          # VideoSpoolEngine (atomic staging & post-command hook)
│   └── media_servers/
│       ├── __init__.py           # get_media_server_client factory & registry
│       ├── base.py               # BaseMediaServerClient with retry policy & dry-run simulation
│       ├── jellyfin.py           # JellyfinClient (/Library/Refresh and /Items/{id}/Refresh)
│       ├── emby.py               # EmbyClient (/Library/Refresh with token auth)
│       └── plex.py               # PlexClient (/library/sections/{id}/refresh with X-Plex-Token)
└── plugins/
    └── lookup/
        └── video.py              # SceneVideoLookup (regex cues, multi-episode spans, subtitle pairing)
```

---

## Operational Workflow Modes

Configure the active workflow mode via `--video-mode [spool|direct|hybrid]` or in configuration under `video.workflow_mode`:

### 1. Spool Mode (`spool`)
- **Purpose**: Handoff release bundles to downstream automated library managers like Sonarr, Radarr, or custom post-processors.
- **Auto-Detection**: If `--video-spool-dir` is provided and `--video-mode` is omitted, the system automatically defaults to `spool` mode.
- **Preserved Release Hierarchy**: Entire release folders (including nested `Subs/` or `Subtitles/` subfolders) and companion assets (`.srt`, `.vtt`, `.nfo`, poster artwork) are clustered into an atomic `VideoReleaseBundle` and transferred to the drop directory.
- **Post-Ingest Command Hook**: Executes optional command templates (e.g., `sh /notify.sh "{release_path}"`) upon successful drop.

### 2. Direct Mode (`direct`)
- **Purpose**: Autonomous standalone library organization without external video managers.
- **Movie Destination Structure**:
  ```
  Movies/<Title> (<Year>)/<Title> (<Year>) [<Resolution>].<ext>
  ```
- **Television Destination Structure**:
  ```
  TV/<Show>/Season <SS>/<Show> - S<SS>E<EE> - <Title> [<Resolution>].<ext>
  ```
- **Quality-Aware Collision Upgrades**: When a target file already exists in the library, media-cron compares resolution ranks (`2160p` > `1080p` > `720p` > `480p`). If the incoming asset has a higher quality rank, the existing file is replaced; otherwise, the lower/equal quality asset is safely skipped.
- **Companion Subtitle Tag Preservation**: Companion subtitles are placed adjacent to their video assets with language and descriptor tags intact (e.g., `<Title> (<Year>) [<Resolution>].en.forced.srt`).

### 3. Hybrid Mode (`hybrid`)
- **Purpose**: Sanitizes clutter (junk extensions, sample videos) from the release bundle before depositing the clean bundle into the external manager's drop directory.

---

## Inotify Watcher Safety & Atomic Staging

To eliminate race conditions with external file watchers (e.g., Sonarr, Radarr, inotifywait):

1. **Hidden Directory Isolation**:
   Releases are deposited first into a hidden directory on the target filesystem:
   ```
   <spool_dir>/.incoming_<release_name>_<uuid>/
   ```
2. **Atomic Promotion**:
   Once all video tracks and companion files are fully transferred and flushed, `os.replace` atomically renames the staging directory to its final release directory in under 50ms.
3. **Collision Skipping**:
   If the target release directory already exists in the drop folder, transfer is skipped to prevent partial overwrites.

---

## Media Server Rescan Notifications

When video organization completes, media-cron can notify media servers to initiate a library rescan:

- **Supported Servers**: `Jellyfin`, `Emby`, `Plex`.
- **Debounced Batching**: Exactly one rescan notification is triggered per batch, regardless of the number of files organized.
- **Non-Fatal Resilience**: If the media server is offline or unreachable, the organization batch completes successfully with exit code 0 and records the error in batch telemetry.
- **Retry Policy**: Default single-shot attempt (`max_retries = 0`). Configurable retries with exponential backoff via `--media-server-max-retries`.
- **Dry-Run Simulation**: In `--dry-run` mode, 0 network calls are dispatched and the simulated rescan is accurately reported in telemetry.

---

## CLI Options & Diagnostics

### Primary Options
```bash
media-cron process \
  --source /downloads \
  --destination /media \
  --video-mode direct \
  --media-server \
  --media-server-provider jellyfin \
  --media-server-url http://localhost:8096 \
  --media-server-token "my-api-token"
```

### Diagnostic Commands

1. **Inspect and Identify Video Metadata**:
   ```bash
   media-cron test-video-identify /downloads/Breaking.Bad.S02E05.1080p.mkv --format json
   ```
2. **Test Spool Release Deposition**:
   ```bash
   media-cron test-video-spool /downloads/Dune.Part.Two.2024.2160p --spool-dir /drop/radarr --dry-run
   ```
3. **Verify Media Server Rescan Connectivity**:
   ```bash
   media-cron test-media-server-notify --provider jellyfin --url http://localhost:8096 --token "my-token" --dry-run
   ```
