# Contract: Recovery Telemetry & Output Schema

**Feature Branch**: `011-resume-failed-transfers`
**Date**: 2026-10-15
**Spec Reference**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

---

## 1. BatchSummary Integration

The existing `BatchSummary` model is extended with a new `recovery_summary` attribute:

```python
@dataclass
class BatchSummary:
    # Existing fields: batch_id, started_at, finished_at, dry_run, exit_code, ...
    recovery_summary: RecoverySummary | None = None
```

---

## 2. JSON Schema for Recovery Telemetry

When media-cron emits JSON batch telemetry (`--json`), the `recovery` block is structured as follows:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "RecoveryTelemetry",
  "type": "object",
  "required": [
    "items_scanned",
    "items_resumed",
    "transfers_bypassed",
    "items_purged",
    "bytes_saved",
    "purge_errors"
  ],
  "properties": {
    "items_scanned": {
      "type": "integer",
      "minimum": 0,
      "description": "Total candidate items inspected in staging and destination."
    },
    "items_resumed": {
      "type": "integer",
      "minimum": 0,
      "description": "Count of queued items whose staging copy matched and was reused."
    },
    "transfers_bypassed": {
      "type": "integer",
      "minimum": 0,
      "description": "Count of items whose destination file matched and transfer was skipped."
    },
    "items_purged": {
      "type": "integer",
      "minimum": 0,
      "description": "Count of corrupt/mismatched candidate files or directories deleted."
    },
    "bytes_saved": {
      "type": "integer",
      "minimum": 0,
      "description": "Total volume in bytes of physical transfers eliminated."
    },
    "purge_errors": {
      "type": "integer",
      "minimum": 0,
      "description": "Count of purge operations that failed due to filesystem permissions."
    }
  }
}
```

---

## 3. Human-Readable CLI Batch Summary Output

When running in standard console mode, the batch summary text block includes a dedicated **Fast Recovery Telemetry** section when recovery checks are performed:

```text
=== Media-Cron Batch Summary ===
Batch ID: 8bb18440-0a5f-4a73-bb63-05a7810abb16
Started:  2026-10-15 13:00:00.000000+00:00
Finished: 2026-10-15 13:00:15.000000+00:00
Mode:     [LIVE EXECUTION]
Scanned:  10
Organized: 8
Upgraded: 0
Junk/Sample Purged: 0
Skipped:  0
Errors:   0
Exit Code: 0
--- Fast Recovery Telemetry ---
Candidates Inspected: 4
Staged Resumed:       2 (re-copy avoided)
Destination Bypassed: 1 (redundant transfer skipped)
Corrupt Purged:       1 (cleaned and restarted)
Data Transfer Saved:  14.25 GB
```

---

## 4. Structured Operational Log Records

The logging subsystem emits standardized structured logs across recovery events:

| Event Type | Level | Format String | Context Key-Values |
|---|---|---|---|
| Size mismatch | `WARNING` | `"Corrupted candidate '%s' rejected by file size (%d != %d); purging and restarting"` | `target_path`, `target_size`, `source_size` |
| Hash mismatch | `WARNING` | `"Candidate '%s' SHA-256 mismatch (%s != %s); purging and restarting"` | `target_path`, `target_hash`, `source_hash` |
| Staging resume | `INFO` | `"Staged item '%s' verified matching; resuming without re-copying (%s bytes saved)"` | `item_name`, `bytes_saved` |
| Destination bypass | `INFO` | `"Destination file '%s' verified matching; bypassing transfer and completing post-transfer lifecycle"` | `destination_path`, `bytes_saved` |
| Safe purge executed | `INFO` | `"Purged invalid candidate '%s' prior to clean restart"` | `target_path`, `dry_run` |
