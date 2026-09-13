# Contract: Music CLI Interface & Diagnostics

**Feature**: `005-music-organization`
**Date**: 2026-09-09
**Status**: Complete

---

## 1. Process Command Flags

The primary `process` CLI command is extended with music management options:

```bash
media-cron process [OPTIONS]
```

### Options

| Flag | Type | Default | Description |
|---|---|---|---|
| `--music / --no-music` | Boolean | `True` | Enable or disable music processing. |
| `--music-mode` | Choice (`spool`, `direct`, `hybrid`) | Inferred | Operational workflow mode. If `--music-spool-dir` is passed, defaults to `spool`; otherwise `direct`. |
| `--music-spool-dir` | Path | `None` | Drop/spool directory where releases are deposited for external managers like `beets`. |
| `--music-post-command` | String | `None` | Optional shell command hook executed upon successful release drop (e.g., `beet import -q "{release_path}"`). |
| `--music-lookup / --no-music-lookup` | Boolean | `False` | Enable or disable online music catalog lookup (MusicBrainz/Discogs). |
| `--music-provider` | Choice (`musicbrainz`, `discogs`) | `musicbrainz` | Primary online catalog provider. |
| `--discogs-token` | String | `None` | Optional personal access token for Discogs API queries. |

---

## 2. Diagnostic Commands

### Command: `test-music-identify`
Analyzes an audio file or release folder, displaying extracted embedded tags and optional catalog matches without executing filesystem movements.

```bash
media-cron test-music-identify <PATH> [OPTIONS]
```

#### Arguments & Options
- `PATH`: Path to an audio track or directory release bundle.
- `--lookup / --no-lookup`: Enable/disable external catalog query (default: `--no-lookup`).
- `--format`: Output format (`text` or `json`, default: `text`).

#### Output Schema (JSON Format)
```json
{
  "status": "success",
  "path": "/data/music/Radiohead - Kid A/01 - Everything in Its Right Place.flac",
  "track": {
    "title": "Everything in Its Right Place",
    "artist": "Radiohead",
    "album": "Kid A",
    "album_artist": "Radiohead",
    "track_number": 1,
    "disc_number": 1,
    "year": 2000,
    "genre": "Electronic / Alternative Rock",
    "format": "flac",
    "bitrate_kbps": 940
  },
  "release_bundle": {
    "album_title": "Kid A",
    "album_artist": "Radiohead",
    "year": 2000,
    "total_tracks": 10,
    "total_discs": 1,
    "companion_files": ["cover.jpg"]
  },
  "catalog_match": null
}
```

---

### Command: `test-music-spool`
Simulates or performs atomic drop-folder deposition of a music release into a target spool directory.

```bash
media-cron test-music-spool <SOURCE_PATH> --spool-dir <SPOOL_DIR> [OPTIONS]
```

#### Arguments & Options
- `SOURCE_PATH`: Directory containing the release to spool.
- `--spool-dir`: Target drop folder destination.
- `--post-command`: Shell command template to execute (optional).
- `--dry-run / --no-dry-run`: Simulate deposition without copying/moving files (default: `--dry-run`).
- `--format`: Output format (`text` or `json`, default: `text`).

#### Output Schema (JSON Format)
```json
{
  "status": "success",
  "dry_run": false,
  "source_dir": "/staging/music/Daft Punk - Discovery",
  "spool_dir": "/drop/beets_inbox",
  "target_release_path": "/drop/beets_inbox/Daft Punk - Discovery",
  "files_transferred": [
    "01 - One More Time.flac",
    "02 - Aerodynamic.flac",
    "cover.jpg"
  ],
  "post_command": "beet import -q \"/drop/beets_inbox/Daft Punk - Discovery\"",
  "post_command_exit_code": 0
}
```
