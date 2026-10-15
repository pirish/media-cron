# Media-Cron

[![CI](https://github.com/pirish/media-cron/actions/workflows/ci.yml/badge.svg)](https://github.com/pirish/media-cron/actions/workflows/ci.yml)
[![Release](https://github.com/pirish/media-cron/actions/workflows/release.yml/badge.svg)](https://github.com/pirish/media-cron/actions/workflows/release.yml)
[![GitHub Release](https://img.shields.io/github/v/release/pirish/media-cron)](https://github.com/pirish/media-cron/releases)

**Media-Cron** is a modular, library-first Python CLI tool designed to automate post-download cleanup, media sanitization, container integrity verification, per-media routing, and automated library organization across video, audio, and literature.

---

## Key Features

- **Pluggable Architecture with Sane Defaults**: Decoupled `InputPlugin`, `LookupPlugin`, and `OutputPlugin` protocols with built-in offline implementations.
- **Configurable Per-Media Routing**: Route individual media types (`music`, `audiobooks`, `books`, `movies`, `tv`) from dedicated directory and torrent sources directly into library collections or external drop-folder spools, complete with strict destination mount safety checks.
- **Torrent Client Integration**: First-class qBittorrent integration for automated ingestion of completed torrents, container-to-host path mappings, category/tag filtering, and automated seeding relocation.
- **Unrecognized Media Staging & Manual Review**: Isolates unidentifiable media into a dedicated `review_dir` with structured JSON manifests. Features an interactive terminal triage UI (`media-cron review`) and scriptable CLI subcommands (`list`, `show`, `resolve`, `discard`, `purge`).
- **Comprehensive Media Sanitization & Organization**:
  - **Video**: Parses scene titles, years, and resolutions; bundles companion subtitles (`.srt`, `.ass`, `.sub`, `.vtt`); supports direct library placement or Sonarr/Radarr drop spools.
  - **Music**: Embedded ID3/FLAC tag inspection with optional MusicBrainz and Discogs catalog lookups; supports direct organization or Beets drop-folder spooling with post-ingest command hooks.
  - **Literature & Audiobooks**: Author disambiguation and online metadata matching via Open Library and Audnexus; Universal Decimal Classification (UDC) tagging; automated EPUB conversion via Calibre or Python fallback.
- **Media Server Library Rescan**: Triggers automated library refreshes for Jellyfin, Emby, and Plex upon video ingestion.
- **Staging Directory Isolation**: Safely isolates incoming raw downloads into a dedicated `staging_dir` to prevent race conditions during active unpacking.
- **Seeding Directory Relocation**: Relocates original files to an optional `seed_dir` with original filenames preserved for continuous torrent seeding while hardlinking organized files into your media libraries.
- **Clutter Purging**: Prunes junk files (`.nfo`, `.txt`, `.url`, `.sfv`, `.exe`, `.website`, etc.) and sample clips under 50 MB, followed by empty parent directory cleanup.
- **Container Integrity Verification**: Inspects Matroska EBML, MP4 atoms, audio magic bytes, and e-book archives, preventing corrupt or truncated downloads from contaminating libraries.
- **Fast Failure Recovery & Transfer Resumption**: Automatically checks non-empty staging and destination directories against active queue items. Employs size-first rejection and streaming SHA-256 integrity verification to resume existing matching files without re-copying, bypasses redundant destination writes while triggering post-transfer hooks (torrent seed relocation, move-mode source cleanup), and safely purges corrupted or truncated artifacts within bounded directory roots.
- **Concurrency Protection**: Non-blocking staging lockfile (`.media-cron.lock`) protects automated cron jobs from concurrent execution conflicts.
- **Dry-Run Simulation**: 100% predictive `--dry-run` simulation mode with zero filesystem writes.
- **Dual Output Streams**: Clean human-readable text logs or structured JSON for automated script integration.

---

## Installation

```bash
# Clone and install in editable mode
git clone <repo-url> media-cron
cd media-cron
pip install -e ".[dev]"
```

---

## Quickstart & Usage

### 1. Dry-Run Simulation

Preview all planned renames, deletions, and moves without modifying any files:

```bash
media-cron organize \
  --source /downloads/completed \
  --staging /data/staging \
  --destination /media/library \
  --dry-run \
  --format text
```

Or get machine-readable JSON:

```bash
media-cron organize \
  --source /downloads/completed \
  --destination /media/library \
  --dry-run \
  --format json
```

### 2. Live Execution with Hardlinks & Seeding

```bash
media-cron organize \
  --source /downloads/completed \
  --staging /data/staging \
  --destination /media/library \
  --seed-dir /downloads/seeding \
  --mode hardlink
```

### 3. Torrent Ingestion & Hybrid Execution

Ingest completed torrents directly from qBittorrent, or run in hybrid mode to monitor both a downloads directory and the torrent client:

```bash
# Hybrid ingestion: scan both /downloads/completed and active qBittorrent client
media-cron organize \
  --source /downloads/completed \
  --torrent-client qbittorrent \
  --hybrid
```

### 4. Route Inspection & Mount Safety

Inspect and validate configured source and destination routes:

```bash
# Display resolved routing table across all media domains
media-cron routes list

# Validate destination root mount safety and filesystem accessibility
media-cron routes validate
```

### 5. Interactive Review of Unrecognized Media

When unrecognized files are quarantined into `review_dir`, launch the interactive TTY triage interface:

```bash
# Interactive manual triage
media-cron review

# Scriptable triage subcommands
media-cron review list
media-cron review show <review-id>
media-cron review resolve <review-id> --action organize
media-cron review resolve <review-id> --action discard
media-cron review purge --days 30
```

---

## Configuration (`~/.config/media-cron/config.yaml`)

Media-Cron loads configuration from `~/.config/media-cron/config.yaml` by default. You can specify a custom configuration file using the `--config` / `-c` CLI option or the `MEDIA_CRON_CONFIG` environment variable.

### Precedence Hierarchy

Settings resolve in the following order (highest precedence first):
1. **CLI Flags**: Explicit options passed to `media-cron` commands.
2. **Environment Variables**: `MEDIA_CRON_*` environment variables.
3. **Domain Route Configuration**: Explicit per-media route definitions (`music.sources`, `music.destination`, `video.movies`, etc.).
4. **Domain Legacy Fields**: Domain-specific directory fallbacks (`video.spool_dir`, `music.spool_dir`, `music.library_dir`).
5. **Global System YAML Defaults**: Top-level `paths.source_dir`, `paths.destination_dir`, `general.mode`, and `active_torrent_client`.
6. **Built-in Defaults**: Application fallbacks defined in code.

---

### Complete `config.yaml` Reference

```yaml
# Global filesystem paths
paths:
  source_dir: "/downloads/completed"          # Default fallback raw downloads root
  staging_dir: "/data/staging"                # Working directory for quarantine and processing
  destination_dir: "/media/library"           # Default fallback organized library root
  seed_dir: "/downloads/seeding"              # Optional destination for continuous torrent seeding
  review_dir: "/data/review"                  # Quarantine location for unrecognized media

# General engine settings
general:
  mode: "hardlink"                            # Global transfer mode: hardlink, copy, move
  dry_run: false                              # Simulate actions without writing to disk
  lockfile_timeout_seconds: 0                 # 0 = exit immediately if locked; >0 waits up to N seconds
  sample_size_threshold_mb: 50                # Delete video samples smaller than threshold
  junk_extensions:                            # Extensions purged during ingestion
    - ".nfo"
    - ".txt"
    - ".url"
    - ".sfv"
    - ".exe"
    - ".m3u"
    - ".website"

# Logging & observability
logging:
  level: "info"                               # Log severity: debug, info, warning, error
  destination: "console"                      # Target sink: console (stderr), file, both
  file_path: null                             # Target file path (required if destination is file or both)
  format: "text"                              # Output formatting: text, json
  max_size_mb: 10                             # Max file size in MB before log rotation
  backup_count: 5                             # Number of rotated log backup archives to retain

# Active torrent client and hybrid ingestion
active_torrent_client: "qbittorrent"          # Active client key from torrent_clients (or null)
hybrid_ingest: false                          # When true, scans both source_dir and torrent client

# Torrent client connection and policy profiles
torrent_clients:
  qbittorrent:
    client_type: "qbittorrent"
    host: "localhost"
    port: 8080
    username: "admin"
    password: "adminadmin"
    use_ssl: false
    timeout: 10.0
    path_mappings:
      - remote_prefix: "/downloads/completed" # Path as reported by torrent client
        local_prefix: "/data/completed"       # Local filesystem mount path
    filters:
      categories:                             # Ingest only these categories (empty = all)
        - "movies"
        - "tv"
        - "music"
      tags: []                                # Ingest only torrents with these tags
      exclude_tags:
        - "media-cron-processed"              # Exclude previously ingested torrents
      exclude_categories:
        - "media-cron-done"
      min_progress: 1.0                       # Ingest only 100% completed torrents
    seeding:
      mode: "client_relocate"                 # client_relocate, direct_filesystem, or none
      target_location: "seed_dir"             # Relocate payload to seed_dir or destination_dir
      completion_tag: "media-cron-processed"  # Tag applied after successful processing
      completion_category: "media-cron-done"  # Category applied after processing
      pause_after_process: false

# Unrecognized media staging and manual review
review:
  enabled: true                               # Stage unidentifiable media into review_dir
  max_age_days: 0                             # Retention in days (0 = retain indefinitely)

# Music configuration and routing
music:
  enabled: true
  workflow_mode: "direct"                     # "direct" (organize to library), "spool" (drop folder), "hybrid"
  spool_dir: null                             # Drop folder for external managers (e.g. /data/beets_drop)
  post_ingest_command: null                   # Shell hook, e.g.: beet import -q "{release_path}"
  post_command_timeout_seconds: 120
  library_dir: "Music"
  path_template: "{artist}/{album} ({year})/{track:02d} - {title}.{ext}"
  compilation_artist: "Various Artists"
  enable_external_lookup: false               # Query MusicBrainz/Discogs for missing metadata
  provider: "musicbrainz"                     # "musicbrainz" or "discogs"
  discogs_token: null                         # API token required if using Discogs
  confidence_threshold: 0.85                  # Threshold to accept external metadata matches
  hardlink_with_copy_fallback: true
  preserve_companions: true                   # Preserve cover art and log files
  cache:
    enabled: true
    ttl_seconds: 2592000                      # Cache TTL (30 days)
    cache_file: ".media-cron-cache/music_cache.json"
  transfer_mode: "copy"                       # Per-media transfer override (hardlink, copy, move)
  sources:
    - type: "directory"
      path: "/downloads/music"
    - type: "torrent"
      client_profile: "qbittorrent"
      category: "music"
  destination:
    type: "library"                           # "library" or "spool"
    path: "/media/Music"
    template: "{artist}/{album} ({year})/{track:02d} - {title}.{ext}"

# Video configuration, routing, and media server integration
video:
  enabled: true
  workflow_mode: "direct"                     # "direct", "spool", or "hybrid"
  spool_dir: null                             # Drop folder for external *arr stack
  post_ingest_command: null                   # Shell hook executed post-ingest
  post_command_timeout_seconds: 120
  preserve_companions: true                   # Preserve companion subtitles and artwork
  library_movies_dir: "Movies"
  library_tv_dir: "TV"
  movie_path_template: "{library_movies_dir}/{title} ({year})/{title} ({year}) [{resolution}].{ext}"
  tv_path_template: "{library_tv_dir}/{show}/Season {season:02d}/{show} - S{season:02d}E{episode:02d} - {title} [{resolution}].{ext}"

  media_server:
    enabled: false                            # Notify media server to trigger library rescan
    provider: "jellyfin"                      # "jellyfin", "emby", or "plex"
    url: "http://localhost:8096"
    token: ""                                 # Media server API token
    library_id: null                          # Optional section/library ID
    timeout_seconds: 5.0
    max_retries: 0

  movies:
    transfer_mode: "hardlink"
    sources:
      - type: "directory"
        path: "/downloads/movies"
      - type: "torrent"
        category: "radarr"
    destination:
      type: "library"
      path: "/media/Movies"

  tv:
    transfer_mode: "copy"
    sources:
      - type: "torrent"
        category: "sonarr"
    destination:
      type: "spool"                           # Spool handoff directly into Sonarr drop folder
      path: "/data/spool/tv"

# Digital literature (e-books) configuration and routing
books:
  enabled: true
  enable_external_lookup: true                # Query Open Library for book metadata
  confidence_threshold: 0.85
  udc_lookup:
    enabled: false                            # Universal Decimal Classification tagging
    min_confidence: 0.70
    summary_table_path: null                  # Path to custom UDC table, or null for bundled
  conversion:
    enabled: false                            # Convert non-EPUB formats (.mobi, .azw3, .pdf) to EPUB
    preferred_engine: "calibre"               # "calibre" (ebook-convert) or "python_fallback"
    timeout_seconds: 120
    retention_policy: "preserve"              # "preserve", "archive", or "replace"
    archive_dir: null                         # Required when retention_policy is "archive"
    inject_metadata: true                     # Embed canonical metadata and UDC into EPUB OPF
  cache:
    enabled: true
    ttl_seconds: 2592000
    cache_file: ".media-cron-cache/book_cache.json"
  sources:
    - type: "directory"
      path: "/downloads/ebooks"
  destination:
    type: "library"
    path: "/media/Books"

# Audiobook configuration and routing
audiobook:
  enable_external_lookup: true                # Query metadata providers for author disambiguation
  confidence_threshold: 0.85
  cache:
    enabled: true
    ttl_seconds: 2592000
    cache_file: ".media-cron-cache/audiobook_cache.json"
  providers:
    openlibrary:
      enabled: true
      priority: 10
      base_url: "https://openlibrary.org"
      timeout_seconds: 5.0
      rate_limit_delay: 1.0
    audnexus:
      enabled: false                          # Audnexus provider for audiobook chapters & authors
      priority: 20
      base_url: "https://api.audnexus.com"
      timeout_seconds: 5.0
      rate_limit_delay: 0.5
  sources:
    - type: "directory"
      path: "/downloads/audiobooks"
  destination:
    type: "library"
    path: "/media/Audiobooks"

# Default filename templates
templates:
  movie: "Movies/{title} ({year})/{title} ({year}).{ext}"
  series: "TV Shows/{show}/Season {season:02d}/{show} - S{season:02d}E{episode:02d}.{ext}"
  music: "Music/{artist}/{album}/{track:02d} - {title}.{ext}"
  audiobook: "Audiobooks/{author}/{title}/{track:02d} - {title}.{ext}"
  book: "Books/{author}/{title}.{ext}"

# Pluggable components pipeline
plugins:
  input: "directory_scanner"
  lookups:
    - "scene_video"
    - "music"
    - "audio_tag"
    - "book_meta"
  outputs:
    - "library_organizer"
    - "seed_relocator"
    - "junk_cleaner"
```

---

### Environment Variable Overrides

All YAML settings can be declared or overridden via environment variables for 12-factor application and container environments:

#### Core Paths & Runtime

| Environment Variable | Target Setting | Default | Description |
|---|---|---|---|
| `MEDIA_CRON_CONFIG` | Config path | `~/.config/media-cron/config.yaml` | Path to YAML configuration file |
| `MEDIA_CRON_SOURCE_DIR` | `paths.source_dir` | `None` | Global fallback raw downloads directory |
| `MEDIA_CRON_STAGING_DIR` | `paths.staging_dir` | `~/.media-cron/staging` | Staging isolation directory |
| `MEDIA_CRON_DESTINATION_DIR` | `paths.destination_dir` | `None` | Global fallback media library root |
| `MEDIA_CRON_SEED_DIR` | `paths.seed_dir` | `None` | Target directory for seeding torrents |
| `MEDIA_CRON_PATHS_REVIEW_DIR` | `paths.review_dir` | `None` | Staging directory for unrecognized media |
| `MEDIA_CRON_MODE` | `general.mode` | `hardlink` | Transfer mode: `hardlink`, `copy`, `move` |
| `MEDIA_CRON_DRY_RUN` | `general.dry_run` | `false` | Enable predictive simulation mode |

#### Review Staging & Retention

| Environment Variable | Target Setting | Default | Description |
|---|---|---|---|
| `MEDIA_CRON_REVIEW_ENABLED` | `review.enabled` | `true` | Enable staging of unrecognized media |
| `MEDIA_CRON_REVIEW_MAX_AGE_DAYS` | `review.max_age_days` | `0` | Retention threshold in days (`0` = indefinite) |

#### Logging & Diagnostics

| Environment Variable | Target Setting | Default | Description |
|---|---|---|---|
| `MEDIA_CRON_LOG_LEVEL` | `logging.level` | `info` | Minimum severity: `debug`, `info`, `warning`, `error` |
| `MEDIA_CRON_LOG_DESTINATION` | `logging.destination` | `console` | Destination sink: `console` (strictly `stderr`), `file`, `both` |
| `MEDIA_CRON_LOG_FILE` | `logging.file_path` | `None` | Target file path; switches destination to `file` if unconfigured |
| `MEDIA_CRON_LOG_FORMAT` | `logging.format` | `text` | Formatting style: `text` or `json` (single-line JSON) |
| `MEDIA_CRON_LOG_MAX_SIZE_MB` | `logging.max_size_mb` | `10` | Max file size in MB before log rotation |
| `MEDIA_CRON_LOG_BACKUP_COUNT` | `logging.backup_count` | `5` | Rotated backup retention count |

#### Torrent Client Integration

| Environment Variable | Target Setting | Default | Description |
|---|---|---|---|
| `MEDIA_CRON_ACTIVE_TORRENT_CLIENT` | `active_torrent_client` | `None` | Active torrent client profile (e.g. `qbittorrent`) |
| `MEDIA_CRON_HYBRID_INGEST` | `hybrid_ingest` | `false` | Ingest from both folder scanner and torrent client |
| `MEDIA_CRON_QBITTORRENT_HOST` | `torrent_clients.qbittorrent.host` | `localhost` | qBittorrent Web UI hostname or IP |
| `MEDIA_CRON_QBITTORRENT_PORT` | `torrent_clients.qbittorrent.port` | `8080` | qBittorrent Web UI port |
| `MEDIA_CRON_QBITTORRENT_USERNAME` | `torrent_clients.qbittorrent.username` | `None` | Web UI username |
| `MEDIA_CRON_QBITTORRENT_PASSWORD` | `torrent_clients.qbittorrent.password` | `None` | Web UI password |
| `MEDIA_CRON_SEEDING_MODE` | `torrent_clients.qbittorrent.seeding.mode` | `client_relocate` | Seeding mode (`client_relocate`, `direct_filesystem`, `none`) |
| `MEDIA_CRON_COMPLETION_TAG` | `torrent_clients.qbittorrent.seeding.completion_tag` | `media-cron-processed` | Tag applied upon completed ingestion |
| `MEDIA_CRON_COMPLETION_CATEGORY` | `torrent_clients.qbittorrent.seeding.completion_category` | `media-cron-done` | Category assigned upon completed ingestion |

#### Per-Media Routing Overrides

Each media type supports independent environment variable overrides for transfer modes, source directories, torrent categories, and destination endpoints:

| Environment Variable | Target Setting | Format / Options |
|---|---|---|
| `MEDIA_CRON_MUSIC_TRANSFER_MODE` | `music.transfer_mode` | `hardlink` \| `copy` \| `move` |
| `MEDIA_CRON_MUSIC_SOURCE_DIRS` | `music.sources` | Comma-separated directory paths |
| `MEDIA_CRON_MUSIC_TORRENT_CATEGORY` | `music.sources` | Torrent category filter |
| `MEDIA_CRON_MUSIC_DESTINATION_PATH` | `music.destination.path` | Absolute filesystem path |
| `MEDIA_CRON_MUSIC_DESTINATION_TYPE` | `music.destination.type` | `library` \| `spool` |
| `MEDIA_CRON_MOVIES_TRANSFER_MODE` | `video.movies.transfer_mode` | `hardlink` \| `copy` \| `move` |
| `MEDIA_CRON_MOVIES_SOURCE_DIRS` | `video.movies.sources` | Comma-separated directory paths |
| `MEDIA_CRON_MOVIES_TORRENT_CATEGORY`| `video.movies.sources` | Torrent category filter (e.g. `radarr`) |
| `MEDIA_CRON_MOVIES_DESTINATION_PATH` | `video.movies.destination.path` | Absolute filesystem path |
| `MEDIA_CRON_MOVIES_DESTINATION_TYPE` | `video.movies.destination.type` | `library` \| `spool` |
| `MEDIA_CRON_TV_TRANSFER_MODE` | `video.tv.transfer_mode` | `hardlink` \| `copy` \| `move` |
| `MEDIA_CRON_TV_SOURCE_DIRS` | `video.tv.sources` | Comma-separated directory paths |
| `MEDIA_CRON_TV_TORRENT_CATEGORY` | `video.tv.sources` | Torrent category filter (e.g. `sonarr`) |
| `MEDIA_CRON_TV_DESTINATION_PATH` | `video.tv.destination.path` | Absolute filesystem path |
| `MEDIA_CRON_TV_DESTINATION_TYPE` | `video.tv.destination.type` | `library` \| `spool` |
| `MEDIA_CRON_BOOKS_TRANSFER_MODE` | `books.transfer_mode` | `hardlink` \| `copy` \| `move` |
| `MEDIA_CRON_BOOKS_SOURCE_DIRS` | `books.sources` | Comma-separated directory paths |
| `MEDIA_CRON_BOOKS_TORRENT_CATEGORY` | `books.sources` | Torrent category filter |
| `MEDIA_CRON_BOOKS_DESTINATION_PATH` | `books.destination.path` | Absolute filesystem path |
| `MEDIA_CRON_BOOKS_DESTINATION_TYPE` | `books.destination.type` | `library` \| `spool` |
| `MEDIA_CRON_AUDIOBOOK_TRANSFER_MODE`| `audiobook.transfer_mode` | `hardlink` \| `copy` \| `move` |
| `MEDIA_CRON_AUDIOBOOK_SOURCE_DIRS` | `audiobook.sources` | Comma-separated directory paths |
| `MEDIA_CRON_AUDIOBOOK_TORRENT_CATEGORY` | `audiobook.sources` | Torrent category filter |
| `MEDIA_CRON_AUDIOBOOK_DESTINATION_PATH` | `audiobook.destination.path` | Absolute filesystem path |
| `MEDIA_CRON_AUDIOBOOK_DESTINATION_TYPE` | `audiobook.destination.type` | `library` \| `spool` |

#### Media Subsystems & External Providers

| Environment Variable | Target Setting | Default | Description |
|---|---|---|---|
| `MEDIA_CRON_MUSIC_ENABLED` | `music.enabled` | `true` | Enable music processing |
| `MEDIA_CRON_MUSIC_MODE` | `music.workflow_mode` | `direct` | `direct`, `spool`, or `hybrid` |
| `MEDIA_CRON_MUSIC_SPOOL_DIR` | `music.spool_dir` | `None` | Drop directory for external tools (beets) |
| `MEDIA_CRON_MUSIC_POST_COMMAND` | `music.post_ingest_command` | `None` | Hook executed post-ingest (`{release_path}`) |
| `MEDIA_CRON_MUSIC_LOOKUP` | `music.enable_external_lookup` | `false` | Enable MusicBrainz/Discogs queries |
| `MEDIA_CRON_MUSIC_PROVIDER` | `music.provider` | `musicbrainz` | Primary provider (`musicbrainz`, `discogs`) |
| `MEDIA_CRON_DISCOGS_TOKEN` | `music.discogs_token` | `None` | Personal access token for Discogs API |
| `MEDIA_CRON_MUSIC_CONFIDENCE_THRESHOLD` | `music.confidence_threshold` | `0.85` | Match confidence threshold |
| `MEDIA_CRON_MUSIC_PRESERVE_COMPANIONS` | `music.preserve_companions` | `true` | Preserve album art and companion files |
| `MEDIA_CRON_VIDEO_ENABLED` | `video.enabled` | `true` | Enable video processing |
| `MEDIA_CRON_VIDEO_MODE` | `video.workflow_mode` | `direct` | `direct`, `spool`, or `hybrid` |
| `MEDIA_CRON_VIDEO_SPOOL_DIR` | `video.spool_dir` | `None` | Drop directory for *arr stack |
| `MEDIA_CRON_VIDEO_POST_COMMAND` | `video.post_ingest_command` | `None` | Hook executed post-ingest (`{release_path}`) |
| `MEDIA_CRON_VIDEO_PRESERVE_COMPANIONS` | `video.preserve_companions` | `true` | Preserve subtitle and artwork files |
| `MEDIA_CRON_MEDIA_SERVER_ENABLED` | `video.media_server.enabled` | `false` | Enable media server rescan notification |
| `MEDIA_CRON_MEDIA_SERVER_PROVIDER` | `video.media_server.provider` | `jellyfin` | Media server provider (`jellyfin`, `emby`, `plex`) |
| `MEDIA_CRON_MEDIA_SERVER_URL` | `video.media_server.url` | `""` | Base URL of media server |
| `MEDIA_CRON_MEDIA_SERVER_TOKEN` | `video.media_server.token` | `""` | Media server authentication token |
| `MEDIA_CRON_MEDIA_SERVER_LIBRARY_ID` | `video.media_server.library_id` | `None` | Section ID to refresh |
| `MEDIA_CRON_MEDIA_SERVER_MAX_RETRIES` | `video.media_server.max_retries` | `0` | Max retries for notification calls |
| `MEDIA_CRON_BOOKS_ENABLED` | `books.enabled` | `true` | Enable digital books processing |
| `MEDIA_CRON_BOOKS_EXTERNAL_LOOKUP` | `books.enable_external_lookup` | `true` | Enable Open Library catalog lookups |
| `MEDIA_CRON_BOOKS_CONFIDENCE_THRESHOLD` | `books.confidence_threshold` | `0.85` | Metadata match confidence threshold |
| `MEDIA_CRON_BOOKS_UDC_ENABLED` | `books.udc_lookup.enabled` | `false` | Enable UDC classification tagging |
| `MEDIA_CRON_BOOKS_CONVERT_EPUB` | `books.conversion.enabled` | `false` | Convert non-EPUB files to EPUB |
| `MEDIA_CRON_BOOKS_CONVERSION_ENGINE` | `books.conversion.preferred_engine` | `calibre` | Conversion engine (`calibre` or `python_fallback`) |
| `MEDIA_CRON_BOOKS_RETENTION_POLICY` | `books.conversion.retention_policy` | `preserve` | Policy: `preserve`, `archive`, or `replace` |
| `MEDIA_CRON_BOOKS_ARCHIVE_DIR` | `books.conversion.archive_dir` | `None` | Archive folder for originals |
| `MEDIA_CRON_BOOKS_CACHE_FILE` | `books.cache.cache_file` | `.media-cron-cache/book_cache.json` | Cache file path |
| `MEDIA_CRON_BOOKS_CACHE_TTL` | `books.cache.ttl_seconds` | `2592000` | Cache TTL in seconds (30 days) |
| `MEDIA_CRON_AUDIOBOOK_ENABLE_LOOKUP` | `audiobook.enable_external_lookup` | `true` | Enable audiobook metadata queries |
| `MEDIA_CRON_AUDIOBOOK_CONFIDENCE_THRESHOLD` | `audiobook.confidence_threshold` | `0.85` | Match confidence threshold |
| `MEDIA_CRON_AUDIOBOOK_CACHE_ENABLED` | `audiobook.cache.enabled` | `true` | Enable response caching |
| `MEDIA_CRON_AUDIOBOOK_CACHE_TTL` | `audiobook.cache.ttl_seconds` | `2592000` | Cache TTL in seconds |
| `MEDIA_CRON_AUDIOBOOK_CACHE_FILE` | `audiobook.cache.cache_file` | `.media-cron-cache/audiobook_cache.json` | Cache file path |
| `MEDIA_CRON_OPENLIBRARY_ENABLED` | `audiobook.providers.openlibrary.enabled` | `true` | Enable Open Library provider |
| `MEDIA_CRON_AUDNEXUS_ENABLED` | `audiobook.providers.audnexus.enabled` | `false` | Enable Audnexus provider |
| `MEDIA_CRON_OPENLIBRARY_TIMEOUT` | `audiobook.providers.openlibrary.timeout_seconds` | `5.0` | Open Library timeout in seconds |
| `MEDIA_CRON_AUDNEXUS_TIMEOUT` | `audiobook.providers.audnexus.timeout_seconds` | `5.0` | Audnexus timeout in seconds |

---

## Logging & Observability

Media-Cron features a zero-dependency, container-native logging subsystem built directly on standard Python `logging`.

### Key Capabilities & Architectural Principles

- **Strict Stream Isolation**: All console logging is sent exclusively to `stderr` across all severity levels. `stdout` is strictly reserved for command outputs and machine-readable JSON payloads (`--format json`), guaranteeing reliable downstream piping to tools like `jq`.
- **Sensible Defaults**: Running commands with no logging arguments defaults to `INFO` level output sent to `stderr`.
- **Destination Routing & Exclusive Sinks**:
  - `console`: Standard error console output (default).
  - `file`: Exclusive file logging (`--log-file /path/to/log.log`). Routine console emission is suppressed. Subdirectories are created automatically.
  - `both`: Dual emission to both the file and console (`--console` alongside `--log-file`).
- **Bounded Rotation**: Log files automatically rotate when reaching `max_size_mb` (default 10 MB) retaining `backup_count` (default 5) archives.
- **Structured JSON Logging**: Setting `--log-format json` produces single-line, schema-compliant JSON records (`timestamp`, `level`, `logger`, `message`, `context`, `exception`) ideal for container log forwarders (FluentBit, Vector, Promtail).
- **In-Flight Credential Redaction**: All formatters and sinks automatically scrub passwords, API tokens, secret keys, and Basic/Bearer authentication headers across all log messages, replacing them with `***REDACTED***`.

### CLI Logging Flags Reference

| Flag | Description | Default |
|---|---|---|
| `-v`, `--verbose` | Shortcut for `--log-level debug` | `false` |
| `-q`, `--quiet` | Shortcut for `--log-level error` | `false` |
| `--log-level` | Minimum severity (`debug`, `info`, `warning`, `error`) | `info` |
| `--log-file` | Destination path for persistent log file | `None` |
| `--console` / `--no-console` | Force enable or disable console log emission | `None` |
| `--log-format` | Log record formatting (`text` or `json`) | `text` |
| `--log-max-size-mb` | Size threshold in MB before log rotation | `10` |
| `--log-backup-count` | Number of rotated backup archives to retain | `5` |

### Configuration Precedence

Logging settings resolve across 4 tiers (highest precedence first):
1. **CLI Flags**: `--log-level`, `-v`, `-q`, `--log-file`, `--console`, `--log-format`, etc.
2. **Environment Variables**: `MEDIA_CRON_LOG_LEVEL`, `MEDIA_CRON_LOG_DESTINATION`, etc.
3. **Configuration File**: `logging.*` block in `config.yaml`.
4. **Built-in Defaults**: Level `INFO`, destination `console`, format `text`, max size 10MB, 5 backups.

---

## Cron & Automation Setup

Example `/etc/cron.d/media-cron` job running every 15 minutes:

```cron
*/15 * * * * user media-cron organize --config /etc/media-cron/config.yaml --format json >> /var/log/media-cron.log 2>&1
```

If a prior job is still running, the non-blocking lockfile will cause subsequent executions to exit immediately with exit code `1` and a logged notice, preventing race conditions.

---

## Development & Quality Gates

### Pre-Commit Hooks

Media-Cron uses [pre-commit](https://pre-commit.com/) to automatically enforce file hygiene, Ruff linting/formatting, and the complete test suite before any commit is finalized:

```bash
# Install git pre-commit hooks
pre-commit install

# Run all hooks manually across the entire repository
pre-commit run --all-files
```

### Running Tests & Linters Manually

```bash
# Run full automated test suite
pytest -v

# Run lint checks
ruff check .

# Run code formatter check
ruff format --check .
```

---

## Container & Kubernetes Deployment

### Docker / Podman

Media-Cron publishes non-root multi-architecture container images (`linux/amd64` and `linux/arm64`) to GitHub Container Registry:

```bash
docker run --rm \
  -v /downloads/completed:/data/completed \
  -v /data/staging:/data/staging \
  -v /media/library:/data/library \
  -v ~/.config/media-cron/config.yaml:/config/config.yaml:ro \
  ghcr.io/pirish/media-cron:latest organize
```

### Kubernetes Helm Chart

Deploy Media-Cron to Kubernetes clusters using the official OCI Helm chart:

```bash
# Deploy as a scheduled batch CronJob (default)
helm install media-cron oci://ghcr.io/pirish/charts/media-cron \
  --set persistence.data.existingClaim=media-storage-pvc \
  --set cronjob.schedule="0 2 * * *"

# Or deploy as a continuous background daemon
helm install media-cron oci://ghcr.io/pirish/charts/media-cron \
  --set workloadType=Deployment
```
