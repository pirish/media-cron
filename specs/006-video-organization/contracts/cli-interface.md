# Contract: Video CLI Interface & Diagnostics

**Feature**: `006-video-organization`  
**Date**: 2026-09-09  
**Status**: Complete  

---

## 1. Process / Run Command Flags

The primary `process` / `run` CLI command is extended with video options:

```bash
media-cron process [OPTIONS]
```

### Options

| Flag | Type | Default | Description |
|---|---|---|---|
| `--video / --no-video` | Boolean | `True` | Enable or disable video processing. |
| `--video-mode` | Choice (`spool`, `direct`, `hybrid`) | Inferred | Operational mode. If `--video-spool-dir` passed, defaults to `spool`; otherwise `direct`. |
| `--video-spool-dir` | Path | `None` | Drop/spool directory where releases are deposited for external managers like Sonarr/Radarr. |
| `--video-post-command` | String | `None` | Optional shell command hook executed upon successful release drop (e.g. `sh /hook.sh "{release_path}"`). |
| `--media-server / --no-media-server` | Boolean | `False` | Enable/disable media server library rescan notification. |
| `--media-server-provider` | Choice (`jellyfin`, `emby`, `plex`) | `jellyfin` | Target media server provider. |
| `--media-server-url` | String | `None` | Base URL of media server (e.g., `http://localhost:8096`). |
| `--media-server-token` | String | `None` | API token or authentication key for the media server. |
| `--media-server-library-id` | String | `None` | Optional specific library/section ID to refresh. |
| `--media-server-max-retries` | Integer | `0` | Max retry attempts for rescan notifications (default: 0). |

---

## 2. Diagnostic Commands

### Command: `test-video-identify`
Analyzes a video file or release directory, displaying extracted title, season, episode, year, resolution, quality, and companion assets without filesystem mutations.

```bash
media-cron test-video-identify <PATH> [OPTIONS]
```

#### Arguments & Options
- `PATH`: Path to a video file or directory release bundle.
- `--format`: Output format (`text` or `json`, default: `text`).

#### Output Schema (JSON Format)
```json
{
  "status": "success",
  "path": "/staging/video/Breaking.Bad.S02E05.1080p.mkv",
  "track": {
    "title": "Breakage",
    "show_title": "Breaking Bad",
    "season_number": 2,
    "episode_number": 5,
    "year": null,
    "resolution": "1080p",
    "source_quality": "WEB-DL",
    "format": "mkv",
    "is_sample": false
  },
  "release_bundle": {
    "release_title": "Breaking Bad S02E05 1080p",
    "is_series": true,
    "show_title": "Breaking Bad",
    "season_number": 2,
    "total_videos": 1,
    "companion_files": ["Breaking.Bad.S02E05.en.srt"]
  }
}
```

---

### Command: `test-video-spool`
Simulates or performs atomic drop-folder deposition of a video release into a target spool directory.

```bash
media-cron test-video-spool <SOURCE_PATH> --spool-dir <SPOOL_DIR> [OPTIONS]
```

#### Arguments & Options
- `SOURCE_PATH`: Directory containing the video release to spool.
- `--spool-dir`: Target drop folder destination.
- `--post-command`: Shell command template to execute (optional).
- `--dry-run / --no-dry-run`: Simulate deposition without copying/moving files (default: `--dry-run`).
- `--format`: Output format (`text` or `json`, default: `text`).

#### Output Schema (JSON Format)
```json
{
  "status": "success",
  "dry_run": false,
  "source_dir": "/staging/video/Dune.Part.Two.2024.2160p",
  "spool_dir": "/drop/radarr_watch",
  "target_release_path": "/drop/radarr_watch/Dune.Part.Two.2024.2160p",
  "files_transferred": [
    "Dune.Part.Two.2024.2160p.mkv",
    "Dune.Part.Two.2024.2160p.en.srt",
    "poster.jpg"
  ],
  "post_command": "echo 'Spool complete at /drop/radarr_watch/Dune.Part.Two.2024.2160p'",
  "post_command_exit_code": 0
}
```

---

### Command: `test-media-server-notify`
Tests network connectivity and authenticated library rescan trigger against a configured media server.

```bash
media-cron test-media-server-notify [OPTIONS]
```

#### Options
- `--provider`: Media server type (`jellyfin`, `emby`, or `plex`).
- `--url`: Server base URL.
- `--token`: API key or authentication token.
- `--library-id`: Optional library/section ID.
- `--dry-run / --no-dry-run`: Simulate request without invoking server endpoint (default: `--dry-run`).
- `--format`: Output format (`text` or `json`, default: `text`).

#### Output Schema (JSON Format)
```json
{
  "status": "success",
  "server_type": "jellyfin",
  "endpoint": "http://localhost:8096/Library/Refresh",
  "status_code": 204,
  "duration_seconds": 0.23,
  "dry_run": false
}
```
