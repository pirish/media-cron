# Configuration Schema: Per-Media Routing

**Feature Branch**: `009-media-source-destination-routing`
**Date**: 2026-10-07
**Spec**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

---

## 1. YAML Configuration Schema

Per-media routing is distributed inside each media block (`music:`, `books:`, `audiobook:`, and `video:`) in `config.yaml`.

```yaml
# Global defaults (used as fallbacks)
paths:
  source_dir: "/data/downloads"
  staging_dir: "/home/user/.media-cron/staging"
  destination_dir: "/data/media"
  review_dir: "/data/review"

general:
  mode: "hardlink"
  dry_run: false

# Music Routing
music:
  enabled: true
  workflow_mode: "direct"
  transfer_mode: "copy"                      # Override general.mode for music
  sources:
    - type: "directory"
      path: "/data/downloads/music"
    - type: "torrent"
      client_profile: "qbittorrent_music"   # Specific client profile
      category: "music"
      tag: "lossless"
  destination:
    type: "library"
    path: "/mnt/fast_nvme/Music"
    template: "{artist}/{album} ({year})/{track:02d} - {title}.{ext}"

# Books Routing
books:
  enabled: true
  sources:
    - type: "directory"
      path: "/data/incoming/ebooks"
  destination:
    type: "library"
    path: "/mnt/storage/Books"

# Audiobook Routing
audiobook:
  enabled: true
  sources:
    - type: "directory"
      path: "/data/incoming/audiobooks"
  destination:
    type: "library"
    path: "/mnt/storage/Audiobooks"

# Video Routing (supports movies and tv sub-routes)
video:
  enabled: true
  workflow_mode: "direct"
  movies:
    sources:
      - type: "torrent"
        category: "radarr"
      - type: "directory"
        path: "/data/downloads/movies"
    destination:
      type: "library"                       # or "spool" for *arr drop folder
      path: "/mnt/array/Movies"
  tv:
    sources:
      - type: "torrent"
        category: "sonarr"
    destination:
      type: "spool"                         # drop/spool folder handoff
      path: "/mnt/array/spool/tv"
```

---

## 2. Environment Variable Bindings

Each media route property can be supplied or overridden via environment variables:

| Setting | Environment Variable | Format / Description |
|---------|---------------------|----------------------|
| Music Transfer Mode | `MEDIA_CRON_MUSIC_TRANSFER_MODE` | `hardlink` \| `copy` \| `move` |
| Music Source Dirs | `MEDIA_CRON_MUSIC_SOURCE_DIRS` | Comma-separated paths |
| Music Destination Path | `MEDIA_CRON_MUSIC_DESTINATION_PATH` | Path string |
| Music Destination Type | `MEDIA_CRON_MUSIC_DESTINATION_TYPE` | `library` \| `spool` |
| Books Source Dirs | `MEDIA_CRON_BOOKS_SOURCE_DIRS` | Comma-separated paths |
| Books Destination Path | `MEDIA_CRON_BOOKS_DESTINATION_PATH` | Path string |
| Audiobooks Source Dirs | `MEDIA_CRON_AUDIOBOOK_SOURCE_DIRS` | Comma-separated paths |
| Audiobooks Destination Path | `MEDIA_CRON_AUDIOBOOK_DESTINATION_PATH` | Path string |
| Movies Source Dirs | `MEDIA_CRON_MOVIES_SOURCE_DIRS` | Comma-separated paths |
| Movies Torrent Category | `MEDIA_CRON_MOVIES_TORRENT_CATEGORY` | Torrent category string |
| Movies Destination Path | `MEDIA_CRON_MOVIES_DESTINATION_PATH` | Path string |
| Movies Destination Type | `MEDIA_CRON_MOVIES_DESTINATION_TYPE` | `library` \| `spool` |
| TV Source Dirs | `MEDIA_CRON_TV_SOURCE_DIRS` | Comma-separated paths |
| TV Torrent Category | `MEDIA_CRON_TV_TORRENT_CATEGORY` | Torrent category string |
| TV Destination Path | `MEDIA_CRON_TV_DESTINATION_PATH` | Path string |
| TV Destination Type | `MEDIA_CRON_TV_DESTINATION_TYPE` | `library` \| `spool` |

---

## 3. Fallback Hierarchy

When evaluating any routing parameter for a media type, the system applies this strict resolution order:

1. **Environment Variables**: Overrides all other settings.
2. **Domain Route Configuration**: Explicit block in `config.yaml` (`music.sources`, `music.destination`, etc.).
3. **Domain Legacy Fields**: Legacy destination fields (`video.spool_dir`, `music.spool_dir`, `music.library_dir`).
4. **Global System Defaults**: `paths.source_dir`, `paths.destination_dir`, `general.mode`, `active_torrent_client`.
