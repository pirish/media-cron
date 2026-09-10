# Contract: Video Configuration Schema

**Feature**: `006-video-organization`  
**Date**: 2026-09-09  
**Status**: Complete  

---

## YAML Configuration Schema

```yaml
video:
  enabled: true                         # Enable/disable video processing
  workflow_mode: "direct"               # "spool" | "direct" | "hybrid" (auto-inferred if spool_dir provided)
  spool_dir: null                       # Path to drop directory for *arr stack (e.g., /drop/sonarr)
  post_ingest_command: null             # Shell hook: e.g. "curl -X POST ..." or "sh /scripts/hook.sh {release_path}"
  preserve_companions: true             # Preserve subtitles (.srt, .vtt) and artwork
  library_movies_dir: "Movies"          # Subdirectory for movies in direct mode
  library_tv_dir: "TV"                  # Subdirectory for TV series in direct mode

  media_server:
    enabled: false                      # Enable media player library rescan trigger
    provider: "jellyfin"                # "jellyfin" | "emby" | "plex"
    url: "http://localhost:8096"        # Media server base URL
    token: ""                           # Media server API token
    library_id: null                    # Optional target library/section ID
    timeout_seconds: 5.0                # Request timeout in seconds
    max_retries: 0                      # Configurable retry count (default 0 for single-shot)
```

---

## Environment Variable Mapping

| Environment Variable | Config Path | Default |
|---|---|---|
| `MEDIA_CRON_VIDEO_ENABLED` | `video.enabled` | `true` |
| `MEDIA_CRON_VIDEO_MODE` | `video.workflow_mode` | `"direct"` |
| `MEDIA_CRON_VIDEO_SPOOL_DIR` | `video.spool_dir` | `null` |
| `MEDIA_CRON_VIDEO_POST_COMMAND` | `video.post_ingest_command` | `null` |
| `MEDIA_CRON_VIDEO_PRESERVE_COMPANIONS` | `video.preserve_companions` | `true` |
| `MEDIA_CRON_MEDIA_SERVER_ENABLED` | `video.media_server.enabled` | `false` |
| `MEDIA_CRON_MEDIA_SERVER_PROVIDER` | `video.media_server.provider` | `"jellyfin"` |
| `MEDIA_CRON_MEDIA_SERVER_URL` | `video.media_server.url` | `""` |
| `MEDIA_CRON_MEDIA_SERVER_TOKEN` | `video.media_server.token` | `""` |
| `MEDIA_CRON_MEDIA_SERVER_LIBRARY_ID` | `video.media_server.library_id` | `null` |
| `MEDIA_CRON_MEDIA_SERVER_MAX_RETRIES` | `video.media_server.max_retries` | `0` |
