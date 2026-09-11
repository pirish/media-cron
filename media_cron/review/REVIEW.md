# Unrecognized Media Staging and Manual Review Guide

## Overview

When processing automated downloads, certain files or multi-file release directories may fail automated identification by all lookup plugins (e.g. books, audiobooks, music, video) and may not match known junk/sample patterns. Rather than silently skipping them or allowing them to accumulate indefinitely in active staging, `media-cron` provides an automated staging and manual review workflow.

Unrecognized items are sequestered into dedicated subdirectories within a configurable review directory, accompanied by an inspection manifest (`manifest.json`). Users can inspect, annotate, and resolve these items either interactively in a terminal or non-interactively via scripted subcommands.

---

## Key Features

1. **Automated Isolation**:
   - Files failing all lookup plugins and not discarded as clutter are moved to `<paths.review_dir>/<item_id>/`.
   - Manifest `manifest.json` is generated with original paths, file sizes, failure reasons, and heuristic category hints.

2. **Active Torrent Seeding Protection**:
   - Files actively seeded by a configured torrent client (e.g. qBittorrent, Transmission, Deluge) are never destructively moved.
   - Non-destructive `copy` or `hardlink` is automatically enforced.

3. **Inotify / Atomicity Safety**:
   - Items are prepared inside a hidden staging directory (`.staging_<item_id>`) and promoted via `os.replace` to prevent external watchers from detecting partial writes.

4. **Interactive Terminal Triage (`media-cron review`)**:
   - Guided terminal workflow to review pending items.
   - Prompts for category override, title, creator, year, season, and episode.
   - Action menu: `[O]rganize Now`, `[R]eturn to Staging`, `[D]iscard`, `[S]kip`, `[Q]uit`.

5. **Direct Scriptable Subcommands**:
   - `list`: View pending or historical items (`--format text` or `--format json`).
   - `show`: Inspect full manifest diagnostics for a specific item.
   - `resolve`: Apply metadata and execute `organize` or `reingest` immediately.
   - `discard`: Delete unwanted items (`--force` required in non-interactive environments).
   - `purge`: Batch delete items older than a retention threshold (`--force` required in non-interactive environments).

6. **Media Server Rescan Integration**:
   - Resolving a video or music item via `Organize Now` triggers a library rescan on configured media servers (Jellyfin, Emby, Plex).

---

## Configuration

### YAML Configuration (`config.yaml`)

```yaml
paths:
  source_dir: "/data/downloads"
  staging_dir: "/data/staging"
  destination_dir: "/data/media"
  review_dir: "/data/review"

review:
  max_age_days: 30       # 0 = keep indefinitely (default)
```

### Environment Variables

- `MEDIA_CRON_PATHS_REVIEW_DIR`: Path to the review directory.
- `MEDIA_CRON_REVIEW_MAX_AGE_DAYS`: Retention threshold in days for automated or manual purge.

### CLI Overrides on Pipeline Run

```bash
media-cron process \
  --review-dir /data/review \
  --review-max-age-days 30
```

---

## CLI Reference

### 1. Interactive Review Session

Starts a guided review session for all pending items in the review directory. Requires an interactive terminal (TTY).

```bash
media-cron review [--review-dir <path>] [--config <path>]
```

### 2. List Review Items

Lists items in the review directory.

```bash
# Formatted table
media-cron review list --review-dir /data/review

# Machine-readable JSON output
media-cron review list --review-dir /data/review --format json

# Filter by status (pending, resolved, reingested, discarded, all)
media-cron review list --status pending --review-dir /data/review
```

### 3. Show Item Details

Displays detailed manifest diagnostics, failure reasons, and contained files.

```bash
media-cron review show <item_id> --review-dir /data/review
media-cron review show <item_id> --review-dir /data/review --format json
```

### 4. Non-Interactive Resolution

Directly applies user metadata and performs the target action.

```bash
# Organize immediately into destination library
media-cron review resolve <item_id> \
  --review-dir /data/review \
  --category movie \
  --title "Solaris" \
  --year 1972 \
  --action organize

# Return to staging with sidecar hint (.media-cron-hint.json)
media-cron review resolve <item_id> \
  --review-dir /data/review \
  --category book \
  --title "Design Patterns" \
  --creator "Gang of Four" \
  --year 1994 \
  --action reingest
```

### 5. Discard Item

Deletes an unwanted item from the review directory.

```bash
media-cron review discard <item_id> --force --review-dir /data/review
```

### 6. Purge Stale Items

Purges review items staged longer than the specified age threshold.

```bash
media-cron review purge --older-than 30 --force --review-dir /data/review
```
