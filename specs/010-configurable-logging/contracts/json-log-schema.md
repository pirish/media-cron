# JSON Log Schema: Structured Observability

**Branch**: `010-configurable-logging` | **Date**: 2026-10-14 | **Spec**: [spec.md](../spec.md)

---

## 1. Schema Specification (JSON Schema Draft-07)

When `format: "json"` (or `--log-format json`) is configured, each emitted log line is serialized as a single, newline-delimited JSON document adhering strictly to this schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MediaCronLogRecord",
  "type": "object",
  "required": ["timestamp", "level", "logger", "message"],
  "properties": {
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO-8601 formatted timestamp with timezone offset"
    },
    "level": {
      "type": "string",
      "enum": ["DEBUG", "INFO", "WARNING", "ERROR"],
      "description": "Log record severity level name in uppercase"
    },
    "logger": {
      "type": "string",
      "description": "Originating Python module namespace or logger name"
    },
    "message": {
      "type": "string",
      "description": "Primary log message text with sensitive credentials redacted"
    },
    "context": {
      "type": "object",
      "description": "Optional arbitrary structured key-value attributes passed to the logger",
      "additionalProperties": true
    },
    "exception": {
      "type": ["string", "null"],
      "description": "Formatted error message and traceback (populated on errors in DEBUG mode)"
    }
  },
  "additionalProperties": false
}
```

---

## 2. Example Serialized Records

### Routine Informational Event
```json
{
  "timestamp": "2026-10-14T11:45:00.123456+00:00",
  "level": "INFO",
  "logger": "media_cron.pipeline",
  "message": "Discovered 14 media assets in source directory",
  "context": {
    "source_dir": "/mnt/downloads",
    "scanned": 14
  },
  "exception": null
}
```

### Dry-Run Simulation Event
```json
{
  "timestamp": "2026-10-14T11:45:01.234567+00:00",
  "level": "INFO",
  "logger": "media_cron.pipeline",
  "message": "[DRY-RUN] Planned hardlink: /mnt/downloads/album/track01.flac -> /mnt/music/Artist/Album/01 - track01.flac",
  "context": {
    "media_type": "music",
    "dry_run": true,
    "mode": "hardlink"
  },
  "exception": null
}
```

### Redacted Warning Event
```json
{
  "timestamp": "2026-10-14T11:45:02.345678+00:00",
  "level": "WARNING",
  "logger": "media_cron.torrent.clients.qbittorrent",
  "message": "Connection attempt to http://admin:***REDACTED***@127.0.0.1:8080 timed out",
  "context": {
    "client": "qbittorrent",
    "timeout_seconds": 10
  },
  "exception": null
}
```

### Detailed Debug Exception Event
```json
{
  "timestamp": "2026-10-14T11:45:03.456789+00:00",
  "level": "DEBUG",
  "logger": "media_cron.metadata.udc",
  "message": "UDC lookup failed for barcode 9780141439518",
  "context": {
    "barcode": "9780141439518",
    "provider": "openlibrary"
  },
  "exception": "Traceback (most recent call last):\n  File \"media_cron/metadata/udc.py\", line 45, in resolve\n    raise ServiceUnavailableError(\"503 Service Unavailable\")\nServiceUnavailableError: 503 Service Unavailable"
}
```
