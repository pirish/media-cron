# Quickstart Validation Guide: Music Library Organization and Drop-Folder Ingestion

**Feature**: `005-music-organization`
**Date**: 2026-09-09
**Status**: Ready

This document outlines five validation scenarios proving that music drop-folder spooling, post-ingest command hooks, embedded tag extraction, and optional catalog queries work reliably end-to-end.

---

## Scenario 1: Drop-Folder Ingestion for External Music Library Managers (Beets Spool Mode)

**Goal**: Verify that a multi-track album release in staging is deposited into the configured drop folder with folder hierarchy and companion assets intact.

### 1. Setup Staging Release
```bash
mkdir -p /tmp/mc_music_test/staging/Daft_Punk_Discovery
echo "dummy FLAC audio" > /tmp/mc_music_test/staging/Daft_Punk_Discovery/01_one_more_time.flac
echo "dummy FLAC audio" > /tmp/mc_music_test/staging/Daft_Punk_Discovery/02_aerodynamic.flac
echo "dummy image data" > /tmp/mc_music_test/staging/Daft_Punk_Discovery/cover.jpg
echo "FILE \"Discovery.flac\" WAVE" > /tmp/mc_music_test/staging/Daft_Punk_Discovery/album.cue

mkdir -p /tmp/mc_music_test/beets_drop
mkdir -p /tmp/mc_music_test/dest
```

### 2. Execute Music Processing in Spool Mode
```bash
media-cron process \
  --source /tmp/mc_music_test/staging \
  --staging /tmp/mc_music_test/staging \
  --destination /tmp/mc_music_test/dest \
  --music-spool-dir /tmp/mc_music_test/beets_drop \
  --music-mode spool
```

### 3. Verify Outcome
- The release exists in `/tmp/mc_music_test/beets_drop/Daft_Punk_Discovery/`.
- All tracks (`01_one_more_time.flac`, `02_aerodynamic.flac`) and companion assets (`cover.jpg`, `album.cue`) are present.
- No temporary staging folders (`.incoming_*`) remain.

---

## Scenario 2: Post-Ingest Command Hook Execution

**Goal**: Verify that configuring `--music-post-command` executes the command with `{release_path}` replaced.

### 1. Execute with Command Hook
```bash
media-cron test-music-spool \
  /tmp/mc_music_test/staging/Daft_Punk_Discovery \
  --spool-dir /tmp/mc_music_test/beets_drop \
  --post-command "echo 'Imported release at {release_path}' > /tmp/mc_music_test/hook.log" \
  --no-dry-run \
  --format json
```

### 2. Verify Outcome
- Output JSON indicates `post_command_executed: true` and `post_command_exit_code: 0`.
- `/tmp/mc_music_test/hook.log` contains `Imported release at /tmp/mc_music_test/beets_drop/Daft_Punk_Discovery`.

---

## Scenario 3: Embedded Tag Extraction & Direct Library Organization

**Goal**: Verify that audio files with embedded tags are automatically organized into `Music/<Artist>/<Album> (<Year>)/<Track#> - <Title>.<ext>`.

### 1. Execute Direct Organization
```bash
media-cron process \
  --source /tmp/mc_music_test/staging \
  --destination /tmp/mc_music_test/dest \
  --music-mode direct
```

### 2. Verify Outcome
- Files are organized under `/tmp/mc_music_test/dest/Music/Daft Punk/Discovery (2001)/`.
- Companion files (`cover.jpg`) are placed in the album folder.

---

## Scenario 4: Diagnostic Inspection (`test-music-identify`)

**Goal**: Inspect audio file tags and release bundling without touching files on disk.

### 1. Run Diagnostic Tool
```bash
media-cron test-music-identify \
  /tmp/mc_music_test/staging/Daft_Punk_Discovery/01_one_more_time.flac \
  --format json
```

### 2. Verify Outcome
- Returns clean JSON with artist, album, track number, title, and container format.
- Exit code is 0.

---

## Scenario 5: Dry-Run Simulation & Safety

**Goal**: Verify that `--dry-run` accurately plans spooling or direct organization without creating or moving any files.

### 1. Run in Dry-Run Mode
```bash
media-cron process \
  --source /tmp/mc_music_test/staging \
  --music-spool-dir /tmp/mc_music_test/beets_drop \
  --dry-run \
  --format json
```

### 2. Verify Outcome
- Outputs planned operations in JSON payload (`dry_run: true`).
- No files are written to `/tmp/mc_music_test/beets_drop`.
- Original files in `/tmp/mc_music_test/staging` remain completely untouched.
