# Quickstart Validation Guide: Per-Media Routing

**Feature Branch**: `009-media-source-destination-routing`
**Date**: 2026-10-07
**Spec**: [spec.md](spec.md) | **Data Model**: [data-model.md](data-model.md) | **Contracts**: [contracts/](contracts/)

---

## Prerequisites & Setup

Run from the root of the repository:

```bash
# Ensure dependencies are installed and test environment is ready
uv run pytest tests/unit -q
```

---

## Scenario 1: Per-Media Custom Destination Routing (User Story 1 - MVP)

**Objective**: Verify that music and movie files are routed to completely separate target directory roots instead of a shared global destination.

### 1. Setup Test Workspace & Config
```bash
TEST_DIR=$(mktemp -d -t media_route_s1_XXXXXX)
mkdir -p "$TEST_DIR/downloads" "$TEST_DIR/dest_music" "$TEST_DIR/dest_movies"

# Create dummy sample media
touch "$TEST_DIR/downloads/Daft Punk - Discovery - 01 - One More Time.flac"
touch "$TEST_DIR/downloads/Inception.2010.1080p.mkv"

# Write configuration
cat << EOF > "$TEST_DIR/config.yaml"
paths:
  staging_dir: "$TEST_DIR/staging"
  destination_dir: "$TEST_DIR/fallback"
general:
  mode: "copy"
music:
  enabled: true
  destination:
    type: "library"
    path: "$TEST_DIR/dest_music"
video:
  enabled: true
  movies:
    destination:
      type: "library"
      path: "$TEST_DIR/dest_movies"
EOF
```

### 2. Execute Dry-Run & Live Ingestion
```bash
# Preview operations
uv run media-cron process --config "$TEST_DIR/config.yaml" --source "$TEST_DIR/downloads" --dry-run

# Run live process
uv run media-cron process --config "$TEST_DIR/config.yaml" --source "$TEST_DIR/downloads"
```

### 3. Verification
```bash
# Verify music arrived in dest_music and movie arrived in dest_movies
find "$TEST_DIR/dest_music" -name "*.flac"
find "$TEST_DIR/dest_movies" -name "*.mkv"
test ! -d "$TEST_DIR/fallback/Music"
```
**Expected Outcome**: Music files exist in `$TEST_DIR/dest_music`, movie files exist in `$TEST_DIR/dest_movies`, and `$TEST_DIR/fallback` was never touched.

---

## Scenario 2: Multi-Source Intake Aggregation (User Story 2)

**Objective**: Verify that a media type can concurrently aggregate inputs from multiple directories.

### 1. Setup Multiple Intake Sources
```bash
TEST_DIR=$(mktemp -d -t media_route_s2_XXXXXX)
mkdir -p "$TEST_DIR/incoming_bandcamp" "$TEST_DIR/incoming_cdrips" "$TEST_DIR/dest_music"

touch "$TEST_DIR/incoming_bandcamp/Artist - Album - 01 - Track1.flac"
touch "$TEST_DIR/incoming_cdrips/Artist - Album - 02 - Track2.flac"

cat << EOF > "$TEST_DIR/config.yaml"
paths:
  staging_dir: "$TEST_DIR/staging"
general:
  mode: "copy"
music:
  enabled: true
  sources:
    - type: "directory"
      path: "$TEST_DIR/incoming_bandcamp"
    - type: "directory"
      path: "$TEST_DIR/incoming_cdrips"
  destination:
    type: "library"
    path: "$TEST_DIR/dest_music"
EOF
```

### 2. Execute Ingestion
```bash
uv run media-cron process --config "$TEST_DIR/config.yaml"
```

### 3. Verification
```bash
# Both tracks from both separate source directories must be organized into dest_music
test -f "$TEST_DIR/dest_music/Artist/Album/01 - Track1.flac"
test -f "$TEST_DIR/dest_music/Artist/Album/02 - Track2.flac"
```

---

## Scenario 3: Mixed Destination Types (Library vs Spool) (User Story 3)

**Objective**: Verify that movies are organized directly into a library structure while TV shows are deposited into an atomic drop/spool folder.

### 1. Setup Test Config
```bash
TEST_DIR=$(mktemp -d -t media_route_s3_XXXXXX)
mkdir -p "$TEST_DIR/downloads/tv_release" "$TEST_DIR/dest_movies" "$TEST_DIR/spool_tv"

touch "$TEST_DIR/downloads/Movie.Title.2022.1080p.mkv"
touch "$TEST_DIR/downloads/tv_release/Show.Name.S01E01.mkv"
touch "$TEST_DIR/downloads/tv_release/Show.Name.S01E01.en.srt"

cat << EOF > "$TEST_DIR/config.yaml"
paths:
  staging_dir: "$TEST_DIR/staging"
general:
  mode: "copy"
video:
  enabled: true
  movies:
    destination:
      type: "library"
      path: "$TEST_DIR/dest_movies"
  tv:
    destination:
      type: "spool"
      path: "$TEST_DIR/spool_tv"
EOF
```

### 2. Execute
```bash
uv run media-cron process --config "$TEST_DIR/config.yaml" --source "$TEST_DIR/downloads"
```

### 3. Verification
```bash
# Movie organized into structured folder
find "$TEST_DIR/dest_movies" -type f -name "*.mkv"

# TV release deposited as a complete folder bundle inside spool_tv
test -d "$TEST_DIR/spool_tv/tv_release"
test -f "$TEST_DIR/spool_tv/tv_release/Show.Name.S01E01.mkv"
test -f "$TEST_DIR/spool_tv/tv_release/Show.Name.S01E01.en.srt"
```

---

## Scenario 4: Strict Source Isolation & Review Quarantine (Clarification Q1, FR-011)

**Objective**: Verify that non-music files placed into a music-dedicated source are quarantined into review and NOT routed to video libraries.

### 1. Setup Dedicated Source with Stray File
```bash
TEST_DIR=$(mktemp -d -t media_route_s4_XXXXXX)
mkdir -p "$TEST_DIR/music_inbox" "$TEST_DIR/dest_music" "$TEST_DIR/dest_movies" "$TEST_DIR/review"

touch "$TEST_DIR/music_inbox/Valid.Track.mp3"
touch "$TEST_DIR/music_inbox/Stray.Movie.2023.mkv"

cat << EOF > "$TEST_DIR/config.yaml"
paths:
  staging_dir: "$TEST_DIR/staging"
  review_dir: "$TEST_DIR/review"
general:
  mode: "copy"
music:
  enabled: true
  sources:
    - type: "directory"
      path: "$TEST_DIR/music_inbox"
  destination:
    type: "library"
    path: "$TEST_DIR/dest_music"
video:
  enabled: true
  movies:
    destination:
      type: "library"
      path: "$TEST_DIR/dest_movies"
EOF
```

### 2. Execute
```bash
uv run media-cron process --config "$TEST_DIR/config.yaml"
```

### 3. Verification
```bash
# Valid track is in dest_music
find "$TEST_DIR/dest_music" -name "*.mp3"

# Stray movie MUST NOT be in dest_movies
test ! -f "$TEST_DIR/dest_movies/Stray.Movie.2023.mkv"

# Stray movie MUST be quarantined in review_dir
find "$TEST_DIR/review" -name "*Stray.Movie*"
```

---

## Scenario 5: Mount Safety Protection (Clarification Q4, FR-008)

**Objective**: Verify that if a destination root directory does not exist, processing for that media type aborts safely without polluting root disks.

### 1. Setup Missing Destination Target
```bash
TEST_DIR=$(mktemp -d -t media_route_s5_XXXXXX)
mkdir -p "$TEST_DIR/downloads" "$TEST_DIR/dest_music"
# Notice: $TEST_DIR/unmounted_drive is intentionally NOT created!

touch "$TEST_DIR/downloads/track.flac"
touch "$TEST_DIR/downloads/movie.mkv"

cat << EOF > "$TEST_DIR/config.yaml"
paths:
  staging_dir: "$TEST_DIR/staging"
general:
  mode: "copy"
music:
  enabled: true
  destination:
    type: "library"
    path: "$TEST_DIR/dest_music"
video:
  enabled: true
  movies:
    destination:
      type: "library"
      path: "$TEST_DIR/unmounted_drive/movies"
EOF
```

### 2. Execute Validation Command
```bash
# Routes validate command must fail
uv run media-cron routes validate --config "$TEST_DIR/config.yaml"
# Exit code should be non-zero (1)
```

### 3. Execute Process Command
```bash
uv run media-cron process --config "$TEST_DIR/config.yaml" --source "$TEST_DIR/downloads"
```

### 4. Verification
```bash
# Music succeeded
find "$TEST_DIR/dest_music" -name "*.flac"

# Unmounted directory was NOT created by mkdir -p
test ! -d "$TEST_DIR/unmounted_drive"
```
**Expected Outcome**: Music is organized successfully; movie processing is aborted safely; `$TEST_DIR/unmounted_drive` is never created.
