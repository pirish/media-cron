# Contract: Configuration Schema

This document defines the schema and default values for `config.yaml` or environment variables used by Media-Cron.

---

## Example Configuration File (`~/.config/media-cron/config.yaml`)

```yaml
# Core filesystem paths
paths:
  source_dir: "/downloads/completed"
  staging_dir: "/data/staging"
  destination_dir: "/media/library"
  seed_dir: "/downloads/seeding" # Optional: if set, original files relocated here for seeding

# Concurrency & Execution
general:
  mode: "hardlink" # Options: hardlink, move, copy
  dry_run: false
  lockfile_timeout_seconds: 0 # 0 = non-blocking immediate exit
  sample_size_threshold_mb: 50
  junk_extensions:
    - ".nfo"
    - ".txt"
    - ".url"
    - ".sfv"
    - ".exe"
    - ".m3u"
    - ".website"

# Path formatting templates
templates:
  movie: "Movies/{title} ({year})/{title} ({year}).{ext}"
  series: "TV Shows/{show}/Season {season:02d}/{show} - S{season:02d}E{episode:02d}.{ext}"
  music: "Music/{artist}/{album}/{track:02d} - {title}.{ext}"
  audiobook: "Audiobooks/{author}/{title}/{track:02d} - {title}.{ext}"
  book: "Books/{author}/{title}.{ext}"

# Pluggable Interfaces Configuration
plugins:
  input: "directory_scanner" # Default input plugin
  lookups:
    - "scene_video"
    - "audio_tag"
    - "book_meta"
  outputs:
    - "library_organizer"
    - "seed_relocator"
    - "junk_cleaner"
```

---

## Environment Variable Overrides

All configuration values can be overridden via environment variables prefixed with `MEDIA_CRON_`:

| Environment Variable | Equivalent Config Path | Description |
|---|---|---|
| `MEDIA_CRON_SOURCE_DIR` | `paths.source_dir` | Input directory |
| `MEDIA_CRON_STAGING_DIR` | `paths.staging_dir` | Staging directory |
| `MEDIA_CRON_DESTINATION_DIR` | `paths.destination_dir` | Target media library |
| `MEDIA_CRON_SEED_DIR` | `paths.seed_dir` | Optional seeding directory |
| `MEDIA_CRON_MODE` | `general.mode` | Transfer mode (`hardlink`, `move`, `copy`) |
| `MEDIA_CRON_DRY_RUN` | `general.dry_run` | Enable dry-run mode (`true`/`false`) |
| `MEDIA_CRON_CONFIG` | CLI `--config` | Custom configuration file path |
