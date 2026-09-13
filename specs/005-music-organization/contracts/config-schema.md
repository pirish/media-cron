# Contract: Music Subsystem Configuration Schema

**Feature**: `005-music-organization`
**Date**: 2026-09-09
**Status**: Complete

---

## 1. YAML Configuration Schema

Configuration resides under the `music:` top-level block in `media-cron.yml`:

```yaml
music:
  enabled: true                        # Enable or disable music processing
  workflow_mode: "spool"               # "spool" | "direct" | "hybrid" (auto-detected if omitted)
  spool_dir: "/mnt/storage/beets_drop" # Target drop folder for external managers
  post_ingest_command: "beet import -q \"{release_path}\"" # Optional shell hook executed post-drop
  post_command_timeout_seconds: 120    # Timeout for post-ingest command execution

  # Organization settings (direct mode)
  library_dir: "Music"                 # Subdirectory under destination_dir
  path_template: "{album_artist}/{album} ({year})/{track_padded} - {title}.{ext}"
  compilation_artist: "Various Artists"# Fallback folder for compilations

  # External Catalog Lookup (direct/hybrid mode)
  enable_external_lookup: false        # Enable online queries (MusicBrainz/Discogs)
  provider: "musicbrainz"              # "musicbrainz" | "discogs"
  discogs_token: null                  # Optional personal access token for Discogs
  confidence_threshold: 0.85           # Score required to override embedded tags
  cache_ttl_days: 30                   # Cache expiration for catalog responses

  # Filesystem behavior
  hardlink_with_copy_fallback: true    # Use hardlinks when on same filesystem; fall back to copy
```

---

## 2. Environment Variable Overrides

All YAML configuration values can be overridden via environment variables:

| Environment Variable | Target Setting | Default / Format |
|---|---|---|
| `MEDIA_CRON_MUSIC_ENABLED` | `music.enabled` | `true` |
| `MEDIA_CRON_MUSIC_MODE` | `music.workflow_mode` | `spool` or `direct` |
| `MEDIA_CRON_MUSIC_SPOOL_DIR` | `music.spool_dir` | Path string |
| `MEDIA_CRON_MUSIC_POST_COMMAND`| `music.post_ingest_command`| Command string with `{release_path}` placeholder |
| `MEDIA_CRON_MUSIC_LOOKUP` | `music.enable_external_lookup` | `false` |
| `MEDIA_CRON_MUSIC_PROVIDER` | `music.provider` | `musicbrainz` |
| `MEDIA_CRON_DISCOGS_TOKEN` | `music.discogs_token` | Secret string |

---

## 3. Telemetry Schema

Extended in `BatchSummary.music_summary`:

```json
{
  "total_tracks": 24,
  "releases_bundled": 2,
  "spooled_releases": 2,
  "organized_tracks": 0,
  "external_matches": 0,
  "average_confidence": 1.0,
  "post_commands_run": 2,
  "errors": 0
}
```
