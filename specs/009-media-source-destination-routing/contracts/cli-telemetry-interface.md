# CLI & Telemetry Interface: Per-Media Routing

**Feature Branch**: `009-media-source-destination-routing`
**Date**: 2026-10-07
**Spec**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

---

## 1. CLI Diagnostic Commands

### 1.1 `media-cron routes list`

Inspects resolved routing configuration across all supported media types.

**Usage**:
```bash
media-cron routes list [--json] [--config PATH]
```

**Human-Readable Output**:
```text
Resolved Media Routing Configuration:
================================================================================
Media Type   Transfer Mode  Destination Type  Destination Path          Sources
--------------------------------------------------------------------------------
music        copy           library           /mnt/fast_nvme/Music      2 sources: [dir: /data/downloads/music, torrent: cat=music]
audiobooks   hardlink       library           /mnt/storage/Audiobooks   1 source:  [dir: /data/incoming/audiobooks]
books        hardlink       library           /mnt/storage/Books        1 source:  [dir: /data/incoming/ebooks]
movies       hardlink       library           /mnt/array/Movies         2 sources: [torrent: cat=radarr, dir: /data/downloads/movies]
tv           move           spool             /mnt/array/spool/tv       1 source:  [torrent: cat=sonarr]
================================================================================
```

### 1.2 `media-cron routes validate`

Verifies mount point safety and accessibility of all configured source and destination directories.

**Usage**:
```bash
media-cron routes validate [--json] [--config PATH]
```

**Exit Codes**:
- `0`: All configured sources and destination root directories exist and are accessible.
- `1`: One or more destination root directories are missing or unmounted.
- `2`: Configuration syntax error.

---

## 2. Telemetry Schema: `BatchSummary.routing_summary`

When `media-cron process --json` or `BatchSummary.to_dict()` is executed, `routing_summary` is included:

```json
{
  "batch_id": "c3d24f62-8e59-4a7d-a24c-0929470474ce",
  "started_at": "2026-10-07T15:30:00Z",
  "completed_at": "2026-10-07T15:30:05Z",
  "dry_run": false,
  "exit_code": 0,
  "total_scanned": 12,
  "processed_count": 10,
  "review_staged_count": 2,
  "routing_summary": {
    "music": {
      "source_count": 2,
      "destination_path": "/mnt/fast_nvme/Music",
      "destination_type": "library",
      "transfer_mode": "copy",
      "scanned_count": 5,
      "processed_count": 4,
      "spooled_count": 0,
      "review_staged_count": 1,
      "skipped_count": 0,
      "error_count": 0,
      "errors": []
    },
    "movies": {
      "source_count": 2,
      "destination_path": "/mnt/array/Movies",
      "destination_type": "library",
      "transfer_mode": "hardlink",
      "scanned_count": 3,
      "processed_count": 3,
      "spooled_count": 0,
      "review_staged_count": 0,
      "skipped_count": 0,
      "error_count": 0,
      "errors": []
    },
    "tv": {
      "source_count": 1,
      "destination_path": "/mnt/array/spool/tv",
      "destination_type": "spool",
      "transfer_mode": "move",
      "scanned_count": 4,
      "processed_count": 3,
      "spooled_count": 3,
      "review_staged_count": 1,
      "skipped_count": 0,
      "error_count": 0,
      "errors": []
    }
  }
}
```
