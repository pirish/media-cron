# Domain Data Model: Configurable Logging Subsystem

**Branch**: `010-configurable-logging` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

---

## 1. Domain Enums

### `LogLevel`
Represents the severity filtering threshold for log events.

```python
from enum import Enum
import logging


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def python_level(self) -> int:
        mapping = {
            LogLevel.DEBUG: logging.DEBUG,  # 10
            LogLevel.INFO: logging.INFO,  # 20
            LogLevel.WARNING: logging.WARNING,  # 30
            LogLevel.ERROR: logging.ERROR,  # 40
        }
        return mapping[self]

    @classmethod
    def from_str(cls, val: str) -> "LogLevel":
        normalized = val.strip().lower()
        try:
            return cls(normalized)
        except ValueError:
            raise ValueError(
                f"Invalid log level '{val}'. Allowed levels: {', '.join(cls.values())}"
            )

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]
```

### `LogDestination`
Represents the target sink(s) for emitted log events.

```python
class LogDestination(str, Enum):
    CONSOLE = "console"  # Standard error stream (stderr)
    FILE = "file"  # Persistent file on disk (console silenced)
    BOTH = "both"  # Dual emission to both file and stderr

    @classmethod
    def from_str(cls, val: str) -> "LogDestination":
        normalized = val.strip().lower()
        try:
            return cls(normalized)
        except ValueError:
            raise ValueError(f"Invalid log destination '{val}'. Allowed: {', '.join(cls.values())}")

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]
```

### `LogFormat`
Represents the serialization format of emitted log records.

```python
class LogFormat(str, Enum):
    TEXT = "text"  # Human-readable terminal output
    JSON = "json"  # Machine-readable single-line JSON

    @classmethod
    def from_str(cls, val: str) -> "LogFormat":
        normalized = val.strip().lower()
        try:
            return cls(normalized)
        except ValueError:
            raise ValueError(f"Invalid log format '{val}'. Allowed: {', '.join(cls.values())}")

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]
```

---

## 2. Configuration Entities

### `LoggingConfig`
Declared inside `MediaCronConfig` to control the global logging engine.

| Field | Type | Default | Description |
|---|---|---|---|
| `level` | `LogLevel` | `LogLevel.INFO` | Minimum severity level to emit |
| `destination` | `LogDestination` | `LogDestination.CONSOLE` | Target sink (`console`, `file`, or `both`) |
| `file_path` | `Path | None` | `None` | Persistent log file path (required if destination is `file` or `both`) |
| `format` | `LogFormat` | `LogFormat.TEXT` | Formatting engine (`text` or `json`) |
| `max_size_mb` | `int` | `10` | Maximum log file size in megabytes before rotation |
| `backup_count` | `int` | `5` | Number of rotated backup log files to retain |

#### Validation Invariants:
1. If `destination` is `LogDestination.FILE` or `LogDestination.BOTH`, `file_path` MUST NOT be `None` or empty.
2. `max_size_mb` MUST be greater than `0`.
3. `backup_count` MUST be greater than or equal to `0`.
4. If `file_path` exists, it MUST NOT point to an existing directory (it must be a file target).
5. If `file_path.parent` does not exist, the parent directory must be creatable by the current user.

```python
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LoggingConfig:
    level: LogLevel = LogLevel.INFO
    destination: LogDestination = LogDestination.CONSOLE
    file_path: Path | None = None
    format: LogFormat = LogFormat.TEXT
    max_size_mb: int = 10
    backup_count: int = 5

    def validate(self) -> None:
        if self.destination in (LogDestination.FILE, LogDestination.BOTH):
            if not self.file_path:
                raise ValueError(
                    f"Logging destination '{self.destination.value}' requires 'file_path' to be configured."
                )
            if self.file_path.exists() and self.file_path.is_dir():
                raise ValueError(
                    f"Configured log file path '{self.file_path}' is an existing directory; must specify a file path."
                )
        if self.max_size_mb <= 0:
            raise ValueError("Logging max_size_mb must be greater than 0.")
        if self.backup_count < 0:
            raise ValueError("Logging backup_count cannot be negative.")
```

---

## 3. Log Record Schema

### `LogRecordPayload`
Structure represented when formatting log records (specifically serialized by `JsonLogFormatter`).

| Field | Type | Example | Description |
|---|---|---|---|
| `timestamp` | `string` (ISO-8601) | `"2026-10-14T11:45:00.123456+00:00"` | Precise event timestamp |
| `level` | `string` | `"INFO"` | Severity name (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `logger` | `string` | `"media_cron.pipeline"` | Logger namespace / module origin |
| `message` | `string` | `"Discovered 14 media assets in source directory"` | Sanitized event description |
| `context` | `object` | `{"source_dir": "/mnt/downloads", "scanned": 14}` | Optional structured key-value attributes |
| `exception` | `string | null` | `null` | Formatted exception traceback (populated only on errors when log level is `DEBUG`) |

---

## 4. Sensitive Credential Redaction Model

### `SensitivePattern`
Defines regex rules applied by `SensitiveDataFilter` to prevent secrets leakage in emitted logs.

| Pattern Type | Target Match Expression | Replacement |
|---|---|---|
| **Key-Value Pair** | `(?i)(password\|token\|secret\|api[_-]?key\|auth\|pass)\s*[:=]\s*['"]?([^'"\s,;&]+)` | `\1=***REDACTED***` |
| **URL Basic Auth** | `(https?://[^:\s]+:)([^@\s]+)(@)` | `\1***REDACTED***\3` |
| **Authorization Header** | `(?i)(Bearer\|Basic)\s+([A-Za-z0-9\-._~+/]+=*)` | `\1 ***REDACTED***` |

---

## 5. Precedence Resolution Matrix

| Target Option | CLI Option Flag | Environment Variable | Configuration Key | Built-in Default |
|---|---|---|---|---|
| **Log Level** | `--log-level` / `-v` / `-q` | `MEDIA_CRON_LOG_LEVEL` | `logging.level` | `"info"` |
| **Destination** | `--log-file` + `--console` | `MEDIA_CRON_LOG_DESTINATION` | `logging.destination` | `"console"` |
| **File Target** | `--log-file` | `MEDIA_CRON_LOG_FILE` | `logging.file_path` | `None` |
| **Format** | `--log-format` | `MEDIA_CRON_LOG_FORMAT` | `logging.format` | `"text"` |
| **Max Size** | `--log-max-size-mb` | `MEDIA_CRON_LOG_MAX_SIZE_MB` | `logging.max_size_mb` | `10` |
| **Backup Count** | `--log-backup-count` | `MEDIA_CRON_LOG_BACKUP_COUNT` | `logging.backup_count` | `5` |
