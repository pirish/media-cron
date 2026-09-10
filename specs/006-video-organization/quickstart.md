# Quickstart Validation Guide: Video Organization, Drop-Folder Spooling, and Media Server Rescan

**Feature**: `006-video-organization`  
**Date**: 2026-09-09  
**Status**: Ready  

This document outlines five validation scenarios proving that video drop-folder spooling, post-ingest command hooks, direct library organization, media server rescan triggers, and simulation modes function reliably end-to-end.

---

## Scenario 1: Drop-Folder Ingestion for External Library Managers (*arr Spool Mode)

**Goal**: Verify that a video release folder containing a movie, companion subtitles, and metadata in staging is deposited into the configured drop directory with folder hierarchy intact and atomic staging.

### 1. Setup Staging Release
```bash
mkdir -p /tmp/mc_video_test/staging/Dune.Part.Two.2024.2160p
head -c 1000 /dev/zero > /tmp/mc_video_test/staging/Dune.Part.Two.2024.2160p/Dune.Part.Two.2024.2160p.mkv
echo "1\n00:00:01,000 --> 00:00:04,000\nSubtitles..." > /tmp/mc_video_test/staging/Dune.Part.Two.2024.2160p/Dune.Part.Two.2024.2160p.en.srt
head -c 500 /dev/zero > /tmp/mc_video_test/staging/Dune.Part.Two.2024.2160p/poster.jpg
echo "<movie><title>Dune: Part Two</title></movie>" > /tmp/mc_video_test/staging/Dune.Part.Two.2024.2160p/movie.nfo

mkdir -p /tmp/mc_video_test/radarr_drop
mkdir -p /tmp/mc_video_test/dest
```

### 2. Execute Video Processing in Spool Mode
```bash
media-cron process \
  --source /tmp/mc_video_test/staging \
  --staging /tmp/mc_video_test/staging \
  --destination /tmp/mc_video_test/dest \
  --video-spool-dir /tmp/mc_video_test/radarr_drop \
  --video-mode spool
```

### 3. Verify Outcome
- The release exists in `/tmp/mc_video_test/radarr_drop/Dune.Part.Two.2024.2160p/`.
- All files (`.mkv`, `.en.srt`, `poster.jpg`, `movie.nfo`) are present.
- Zero temporary staging folders (`.incoming_*`) remain.

---

## Scenario 2: Post-Ingest Command Hook Execution

**Goal**: Verify that configuring `--video-post-command` executes the command with `{release_path}` replaced.

### 1. Execute with Command Hook
```bash
media-cron test-video-spool \
  /tmp/mc_video_test/staging/Dune.Part.Two.2024.2160p \
  --spool-dir /tmp/mc_video_test/radarr_drop \
  --post-command "echo 'Imported video at {release_path}' > /tmp/mc_video_test/video_hook.log" \
  --no-dry-run \
  --format json
```

### 2. Verify Outcome
- Output JSON indicates `post_command_executed: true` and `post_command_exit_code: 0`.
- `/tmp/mc_video_test/video_hook.log` contains `Imported video at /tmp/mc_video_test/radarr_drop/Dune.Part.Two.2024.2160p`.

---

## Scenario 3: Autonomous Video Identification & Direct Library Organization

**Goal**: Verify that raw video files with companion subtitles are organized into `Movies/<Title> (<Year>)/...` or `TV/<Show>/Season <SS>/...`.

### 1. Execute Direct Organization
```bash
media-cron process \
  --source /tmp/mc_video_test/staging \
  --destination /tmp/mc_video_test/dest \
  --video-mode direct
```

### 2. Verify Outcome
- Files are organized under `/tmp/mc_video_test/dest/Movies/Dune Part Two (2024)/`.
- Associated subtitle (`.en.srt`) is placed adjacent to the video file.

---

## Scenario 4: Media Server Library Rescan Trigger (Jellyfin / Plex)

**Goal**: Verify that configuring a media server triggers an authenticated library rescan upon batch completion.

### 1. Execute Diagnostic Notify
```bash
media-cron test-media-server-notify \
  --provider jellyfin \
  --url "http://localhost:8096" \
  --token "secret_token" \
  --dry-run \
  --format json
```

### 2. Verify Outcome
- Returns JSON with `status: "success"` and `dry_run: true`.
- Endpoint targets `http://localhost:8096/Library/Refresh`.

---

## Scenario 5: Dry-Run Simulation & Safety

**Goal**: Verify that `--dry-run` accurately plans spooling or direct organization without creating or moving any files.

### 1. Run in Dry-Run Mode
```bash
media-cron process \
  --source /tmp/mc_video_test/staging \
  --video-spool-dir /tmp/mc_video_test/radarr_drop \
  --dry-run \
  --format json
```

### 2. Verify Outcome
- Outputs planned operations in JSON payload (`dry_run: true`).
- No files are written to `/tmp/mc_video_test/radarr_drop`.
- Staging files remain completely untouched.
