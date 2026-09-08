# Quickstart & Verification Guide: Torrent Client Integration

**Branch**: `002-torrent-client-integration` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

## Prerequisites

1. Python 3.11+ with `media_cron` package installed in development mode (`pip install -e .`).
2. A running qBittorrent instance (or local test mock server) with Web API enabled.
3. Test staging, destination, and seed directories configured on disk.

---

## Scenario 1: Non-Destructive Dry-Run Simulation

Simulate querying qBittorrent for completed downloads and preview planned staging and tagging without altering disk or client state.

```bash
# Execute dry-run with qBittorrent client
media-cron run \
  --torrent-client qbittorrent \
  --staging-dir /tmp/mc-staging \
  --destination-dir /tmp/mc-library \
  --seed-dir /tmp/mc-seeding \
  --dry-run \
  --format text
```

**Expected Outcome**:
- Output previews discovered completed torrents.
- Lists planned staging copy operations and planned tag updates (`media-cron-processed`).
- Zero files copied to `/tmp/mc-staging`.
- Zero tags or category changes applied in qBittorrent.
- Exit code `0`.

---

## Scenario 2: Live Ingestion with Staging Isolation and Clutter Preservation

Process a completed multi-file torrent containing media and clutter (`.nfo`, sample clips):

```bash
media-cron run \
  --torrent-client qbittorrent \
  --staging-dir /tmp/mc-staging \
  --destination-dir /tmp/mc-library \
  --seed-dir /tmp/mc-seeding \
  --seeding-mode client_relocate
```

**Expected Outcome**:
- Payload files copied to `/tmp/mc-staging`.
- Media file sanitized, verified, and placed into `/tmp/mc-library`.
- Clutter files (`.nfo`, samples) are excluded from `/tmp/mc-library`.
- Clutter files remain intact in the original download/seeding path.
- qBittorrent receives `setLocation` relocation command moving storage to `/tmp/mc-seeding`.
- Torrent in qBittorrent is tagged with `media-cron-processed` and assigned category `media-cron-done`.
- Exit code `0`.

---

## Scenario 3: Targeted Single-Torrent Hook Ingestion

Simulate invocation from qBittorrent's completion runner (`Run external program on torrent completion`):

```bash
# Invocation using torrent info-hash (%I)
media-cron run \
  --torrent-client qbittorrent \
  --torrent-hash "4a5b6c7d8e9f0123456789abcdef0123456789ab" \
  --staging-dir /tmp/mc-staging \
  --destination-dir /tmp/mc-library \
  --seed-dir /tmp/mc-seeding
```

**Expected Outcome**:
- Only the targeted torrent is fetched and processed.
- Other completed torrents in qBittorrent are ignored.
- Exit code `0`.

---

## Scenario 4: Hybrid Ingestion (Drop Folder + Torrent Client)

Simulate simultaneous processing of a dropped video file in `/tmp/mc-drop` and a completed download in qBittorrent:

```bash
media-cron run \
  --source-dir /tmp/mc-drop \
  --torrent-client qbittorrent \
  --hybrid \
  --staging-dir /tmp/mc-staging \
  --destination-dir /tmp/mc-library \
  --seed-dir /tmp/mc-seeding
```

**Expected Outcome**:
- File from `/tmp/mc-drop` is moved into staging.
- Completed torrent payload is copied into staging.
- Both assets are sanitized and organized into `/tmp/mc-library`.
- Consolidated JSON summary reports items from both sources.
- Exit code `0`.

---

## Scenario 5: Diagnostic Connection Test

Verify connectivity and authentication credentials:

```bash
media-cron test-client --torrent-client qbittorrent
```

**Expected Outcome**:
- When client is up and credentials valid: prints `[SUCCESS] Connected to qBittorrent Web API v2` and exits `0`.
- When client is unreachable: prints `[ERROR] Connection refused / timeout` and exits `3`.
- When credentials invalid: prints `[ERROR] Authentication failed (403 Forbidden)` and exits `2`.
