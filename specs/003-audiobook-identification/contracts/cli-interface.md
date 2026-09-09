# CLI Interface: Audiobook Identification & Provider Options

**Branch**: `003-audiobook-identification` | **Date**: 2026-09-08 | **Spec**: [spec.md](../spec.md)

## 1. CLI Options Extended on `media-cron run` & `organize`

```bash
media-cron run [OPTIONS]
```

### New Flags & Options
- `--audiobook-lookup / --no-audiobook-lookup`: Enable or disable external book metadata queries for audiobooks (overrides config).
- `--audiobook-provider TEXT`: Specific provider to force for audiobook lookups (`openlibrary`, `audnexus`).
- `--audiobook-confidence-threshold FLOAT`: Custom confidence threshold $[0.0, 1.0]$ required to override local author/title tags (default `0.85`).
- `--audiobook-cache / --no-audiobook-cache`: Enable or disable response caching.

---

## 2. Diagnostic Command: `media-cron test-book-lookup`

Validates metadata provider connectivity and query parsing without moving or organizing media.

```bash
media-cron test-book-lookup "The Hobbit" --author "J.R.R. Tolkien" --provider openlibrary --format json
```

### Expected Output Schema:
```json
{
  "query_title": "The Hobbit",
  "query_author": "J.R.R. Tolkien",
  "provider": "openlibrary",
  "matches_found": 1,
  "top_match": {
    "title": "The Hobbit",
    "author": "J.R.R. Tolkien",
    "year": 1937,
    "narrator": null,
    "series": null,
    "work_id": "OL262758W",
    "confidence": 0.96
  },
  "cached": false,
  "latency_ms": 284.5
}
```

---

## 3. Telemetry Output: `BatchSummary` Extensions

When executing `media-cron run --format json`, the returned JSON includes an `audiobook_summary` object when audiobooks were processed:

```json
{
  "total_scanned": 12,
  "total_organized": 12,
  "total_purged": 0,
  "total_errors": 0,
  "dry_run": false,
  "exit_code": 0,
  "audiobook_summary": {
    "total_audiobooks": 2,
    "identified_external": 2,
    "identified_local_only": 0,
    "cache_hits": 1,
    "cache_misses": 1,
    "provider_breakdown": {
      "openlibrary": 2
    },
    "average_confidence": 0.94
  }
}
```
