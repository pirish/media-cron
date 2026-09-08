# Contract: CLI Interface

This document specifies the command-line interface, argument syntax, flags, JSON output schema, and exit codes for Media-Cron.

---

## 1. Command Syntax

```bash
media-cron [OPTIONS] COMMAND [ARGS]...
```

### Core Commands

#### `organize`
Run the main ingestion, sanitization, and organization pipeline.

```bash
media-cron organize \
  --source <PATH> \
  --destination <PATH> \
  [--staging <PATH>] \
  [--seed-dir <PATH>] \
  [--mode <hardlink|move|copy>] \
  [--dry-run] \
  [--format <text|json>] \
  [--config <PATH>] \
  [--verbose]
```

| Argument / Option | Default | Required | Description |
|---|---|---|---|
| `--source, -s` | Config value or None | Yes (if not in config) | Directory containing raw downloads |
| `--destination, -d`| Config value or None | Yes (if not in config) | Target media library root |
| `--staging` | `~/.media-cron/staging`| No | User-configurable staging directory |
| `--seed-dir` | None | No | Optional directory to relocate seed material |
| `--mode, -m` | `hardlink` | No | Transfer mode (`hardlink`, `move`, `copy`) |
| `--dry-run, -n` | `False` | No | Simulation mode (zero filesystem changes) |
| `--format, -f` | `text` | No | Output stream format (`text` or `json`) |
| `--config, -c` | `~/.config/media-cron/config.yaml` | No | Path to custom YAML configuration |
| `--verbose, -v` | `False` | No | Enable verbose debug-level logging |

---

## 2. Process Exit Codes

Per the project constitution and specification, exit codes are strictly deterministic:

| Exit Code | Constant | Meaning |
|---|---|---|
| `0` | `EXIT_SUCCESS` | All operations completed successfully |
| `1` | `EXIT_PARTIAL_OR_LOCKED` | Execution skipped due to active lockfile or items skipped due to collision/quarantine |
| `2` | `EXIT_CONFIG_ERROR` | Invalid CLI arguments, unparseable config file, or unknown plugin specified |
| `3` | `EXIT_FATAL_ERROR` | Permission denied, missing critical directory, or unhandled filesystem exception |

---

## 3. Structured Output JSON Schema (`--format json`)

When `--format json` is enabled, `stdout` emits a single root JSON object containing the complete execution outcome:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "BatchSummaryResponse",
  "type": "object",
  "required": [
    "batch_id",
    "started_at",
    "completed_at",
    "dry_run",
    "total_scanned",
    "processed_count",
    "upgraded_count",
    "junk_purged_count",
    "skipped_count",
    "error_count",
    "exit_code",
    "operations"
  ],
  "properties": {
    "batch_id": { "type": "string", "format": "uuid" },
    "started_at": { "type": "string", "format": "date-time" },
    "completed_at": { "type": "string", "format": "date-time" },
    "dry_run": { "type": "boolean" },
    "total_scanned": { "type": "integer" },
    "processed_count": { "type": "integer" },
    "upgraded_count": { "type": "integer" },
    "junk_purged_count": { "type": "integer" },
    "skipped_count": { "type": "integer" },
    "error_count": { "type": "integer" },
    "exit_code": { "type": "integer" },
    "operations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["plan_id", "op_type", "source_path", "status"],
        "properties": {
          "plan_id": { "type": "string", "format": "uuid" },
          "op_type": { "type": "string" },
          "source_path": { "type": "string" },
          "destination_path": { "type": ["string", "null"] },
          "status": { "type": "string", "enum": ["SUCCESS", "SKIPPED", "FAILED"] },
          "reason": { "type": "string" }
        }
      }
    },
    "errors": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```
