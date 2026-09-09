# Quickstart & Validation Guide: Audiobook Identification

**Branch**: `003-audiobook-identification` | **Date**: 2026-09-08 | **Spec**: [spec.md](spec.md)

This guide provides end-to-end runnable scenarios to validate audiobook identification, multi-file bundling, external provider lookups, response caching, and offline fallback behavior.

---

## Prerequisites & Environment Setup

Ensure `media-cron` is installed and editable:
```bash
pip install -e ".[dev]"
```

Verify the environment:
```bash
media-cron --version
media-cron test-book-lookup "The Hobbit" --author "Tolkien"
```

---

## Scenario 1: Standalone `.m4b` Identification via Open Library (P1)

**Goal**: Ingest a single-file `.m4b` audiobook with sparse embedded tags; verify external query standardizes the author and work title.

```bash
# 1. Setup mock staging environment
mkdir -p /tmp/mc-test/{downloads,staging,library,cache}
cat << 'EOF' > /tmp/mc-test/config.yaml
paths:
  source_dir: "/tmp/mc-test/downloads"
  staging_dir: "/tmp/mc-test/staging"
  destination_dir: "/tmp/mc-test/library"
general:
  mode: "copy"
audiobook:
  enable_external_lookup: true
  confidence_threshold: 0.85
  cache:
    cache_file: "/tmp/mc-test/cache/audiobook_cache.json"
EOF

# 2. Create sample audio file
touch "/tmp/mc-test/downloads/Neil.Gaiman.-.Neverwhere.m4b"

# 3. Execute media-cron run
media-cron run --config /tmp/mc-test/config.yaml --format json
```

**Expected Outcome**:
- `Neverwhere.m4b` is identified as an audiobook work by Neil Gaiman.
- Copied to `/tmp/mc-test/library/Audiobooks/Neil Gaiman/Neverwhere/Neverwhere.m4b`.
- Batch summary shows `identified_external: 1`.

---

## Scenario 2: Multi-File Chapter Bundle with Disc Subfolders (P2)

**Goal**: Ingest an audiobook split into chapters across `CD1/` and `CD2/` folders; verify it is treated as a unified work without issuing redundant queries per track.

```bash
# 1. Create multi-file directory structure
mkdir -p "/tmp/mc-test/downloads/Dune/CD1" "/tmp/mc-test/downloads/Dune/CD2"
touch "/tmp/mc-test/downloads/Dune/CD1/Track01.mp3"
touch "/tmp/mc-test/downloads/Dune/CD1/Track02.mp3"
touch "/tmp/mc-test/downloads/Dune/CD2/Track01.mp3"

# 2. Execute dry-run to preview bundling
media-cron run --config /tmp/mc-test/config.yaml --dry-run --format json
```

**Expected Outcome**:
- All 3 tracks in `/tmp/mc-test/downloads/Dune/` are clustered into a single `AudiobookBundle`.
- Only a single external lookup query is made for the work "Dune".
- Planned destinations maintain chapter files under `/tmp/mc-test/library/Audiobooks/Frank Herbert/Dune/`.

---

## Scenario 3: Persistent Response Caching Performance (P3)

**Goal**: Verify that repeat queries for the same title hit the local cache in <50ms without external HTTP requests.

```bash
# First lookup (populates cache)
media-cron test-book-lookup "1984" --author "George Orwell" --config /tmp/mc-test/config.yaml --format json

# Second lookup (hits cache)
media-cron test-book-lookup "1984" --author "George Orwell" --config /tmp/mc-test/config.yaml --format json
```

**Expected Outcome**:
- First query reports `"cached": false` with latency ~200-500ms.
- Second query reports `"cached": true` with latency < 50ms.
- Local cache file `/tmp/mc-test/cache/audiobook_cache.json` exists and contains the serialized match.

---

## Scenario 4: Offline & Network Outage Fallback (P4)

**Goal**: Ingest audiobooks with external lookups disabled or network unavailable; verify system falls back safely to local tags without failing.

```bash
# Run with --no-audiobook-lookup
media-cron run --config /tmp/mc-test/config.yaml --no-audiobook-lookup --format json
```

**Expected Outcome**:
- Process succeeds with exit code `0`.
- Telemetry reports `"identified_local_only" > 0` and `"identified_external": 0`.
- No network requests are initiated.
