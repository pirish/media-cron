# Configuration Schema Contract: Logging Section

**Branch**: `010-configurable-logging` | **Date**: 2026-10-14 | **Spec**: [spec.md](../spec.md)

---

## 1. YAML Configuration Schema

The logging configuration is declared in the root `logging` section of `config.yaml`.

```yaml
logging:
  # Minimum severity level to emit. Allowed: "debug", "info", "warning", "error"
  # Default: "info"
  level: "info"

  # Target destination sink. Allowed: "console", "file", "both"
  # Default: "console"
  destination: "console"

  # Persistent file target path. Required if destination is "file" or "both".
  # Default: null
  file_path: "/var/log/media-cron/media-cron.log"

  # Serialization format. Allowed: "text", "json"
  # Default: "text"
  format: "text"

  # Maximum size of a single log file in megabytes before rotation.
  # Default: 10
  max_size_mb: 10

  # Number of rotated backup files to retain.
  # Default: 5
  backup_count: 5
```

---

## 2. Environment Variable Bindings

Environment variables override values defined in `config.yaml`:

| Configuration Key | Environment Variable | Accepted Values | Example |
|---|---|---|---|
| `logging.level` | `MEDIA_CRON_LOG_LEVEL` | `debug`, `info`, `warning`, `error` | `export MEDIA_CRON_LOG_LEVEL=debug` |
| `logging.destination` | `MEDIA_CRON_LOG_DESTINATION` | `console`, `file`, `both` | `export MEDIA_CRON_LOG_DESTINATION=both` |
| `logging.file_path` | `MEDIA_CRON_LOG_FILE` | Any valid absolute or relative path | `export MEDIA_CRON_LOG_FILE=/var/log/media-cron.log` |
| `logging.format` | `MEDIA_CRON_LOG_FORMAT` | `text`, `json` | `export MEDIA_CRON_LOG_FORMAT=json` |
| `logging.max_size_mb` | `MEDIA_CRON_LOG_MAX_SIZE_MB` | Positive integer | `export MEDIA_CRON_LOG_MAX_SIZE_MB=50` |
| `logging.backup_count` | `MEDIA_CRON_LOG_BACKUP_COUNT` | Non-negative integer | `export MEDIA_CRON_LOG_BACKUP_COUNT=10` |

---

## 3. Configuration Profiles

### Profile A: Default (Out-of-the-Box)
No configuration required. Emits human-readable text logs to `stderr` at `info` level.
```yaml
# config.yaml (empty or no logging section)
```

### Profile B: Automated Background Cron (File-Only)
Directs all routine logs to a persistent file, keeping console silent to prevent cron emails.
```yaml
logging:
  level: "info"
  destination: "file"
  file_path: "/var/log/media-cron/service.log"
  max_size_mb: 20
  backup_count: 7
```

### Profile C: Containerized Deployment (Structured JSON to stderr)
Outputs single-line JSON records to `stderr` for ingestion by container log collectors (Fluentbit/Datadog).
```yaml
logging:
  level: "info"
  destination: "console"
  format: "json"
```

### Profile D: Dual Destination (Persistent File + Interactive Console)
Appends records to a log file while simultaneously displaying them on the console.
```yaml
logging:
  level: "debug"
  destination: "both"
  file_path: "/var/log/media-cron/debug.log"
  format: "text"
```
