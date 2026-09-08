# Contract: Command-Line Interface (CLI)

**Branch**: `002-torrent-client-integration` | **Date**: 2026-09-07 | **Spec**: [spec.md](../spec.md)

## Command Structure

### 1. `media-cron run` (Extended Options)

Executes the media organization pipeline with support for torrent client ingestion, folder monitoring, or hybrid mode.

```text
Usage: media-cron run [OPTIONS]

Options:
  --source-dir PATH               Source directory to monitor and ingest from.
  --staging-dir PATH              Dedicated staging directory where files are isolated.
  --destination-dir PATH          Final organized media library directory.
  --seed-dir PATH                 Dedicated directory for seeding torrent files.
  --torrent-client TEXT           Enable torrent client ingestion (e.g. 'qbittorrent').
  --hybrid / --no-hybrid          Run both folder monitoring and torrent client ingestion [default: False].
  --torrent-hash TEXT             Target a specific completed torrent by info-hash.
  --torrent-name TEXT             Target a specific completed torrent by release name.
  --seeding-mode [client_relocate|direct_filesystem|none]
                                  Seeding strategy to maintain active seeding.
  --dry-run                       Simulate actions without writing or altering client state.
  --format [text|json]            Output formatting [default: text].
  --config PATH                   Path to YAML configuration file.
  --help                          Show this message and exit.
```

### 2. `media-cron test-client` (New Diagnostic Command)

Validates network connectivity and authentication against the configured torrent client.

```text
Usage: media-cron test-client [OPTIONS]

Options:
  --torrent-client TEXT           Client provider to test ('qbittorrent', 'transmission', 'deluge').
  --config PATH                   Path to YAML configuration file.
  --format [text|json]            Output formatting [default: text].
  --help                          Show this message and exit.
```

---

## Exit Codes

Deterministic exit codes adhering to Constitution Principle IV:

| Code | Constant | Meaning |
|---|---|---|
| `0` | `EXIT_SUCCESS` | Operation completed successfully with zero fatal errors. |
| `1` | `EXIT_PARTIAL_OR_LOCKED` | Ingestion locked by another running instance, or partial skips occurred. |
| `2` | `EXIT_CONFIG_ERROR` | Invalid configuration parameters or rejected authentication credentials. |
| `3` | `EXIT_FATAL_ERROR` | Torrent client unreachable, network timeout, or filesystem permission failure. |

---

## JSON Output Schema Extensions

When invoked with `--format json`, the batch summary includes torrent execution telemetry:

```json
{
  "batch_id": "8f3b28b9-8c67-4e94-8172-efbb612e5c8a",
  "started_at": "2026-09-07T22:45:00.000000",
  "completed_at": "2026-09-07T22:45:03.500000",
  "dry_run": false,
  "total_scanned": 12,
  "processed_count": 8,
  "upgraded_count": 0,
  "junk_purged_count": 4,
  "skipped_count": 0,
  "error_count": 0,
  "exit_code": 0,
  "torrent_summary": {
    "client": "qbittorrent",
    "discovered_torrents": 2,
    "ingested_torrents": 2,
    "relocated_torrents": 2,
    "tagged_torrents": 2
  },
  "operations": [
    {
      "plan_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "op_type": "TORRENT_STAGE_COPY",
      "source_path": "/mnt/downloads/Movie.Release.2024.1080p/movie.mkv",
      "destination_path": "/mnt/staging/Movie.Release.2024.1080p/movie.mkv",
      "status": "SUCCESS",
      "reason": "Copied torrent payload to staging for isolation"
    },
    {
      "plan_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "op_type": "TORRENT_RELOCATE",
      "source_path": "/mnt/downloads/Movie.Release.2024.1080p",
      "destination_path": "/mnt/seeding/Movie.Release.2024.1080p",
      "status": "SUCCESS",
      "reason": "qBittorrent setLocation updated to seed directory"
    },
    {
      "plan_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "op_type": "TORRENT_TAG",
      "source_path": "4a5b6c7d8e9f0123456789abcdef0123456789ab",
      "destination_path": null,
      "status": "SUCCESS",
      "reason": "Added tag 'media-cron-processed' and set category 'media-cron-done'"
    }
  ],
  "errors": []
}
```
