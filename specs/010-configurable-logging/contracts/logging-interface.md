# Interface Contract: Logging Subsystem & CLI

**Branch**: `010-configurable-logging` | **Date**: 2026-10-14 | **Spec**: [spec.md](../spec.md)

---

## 1. Python Protocols

### `LoggingEngineProtocol`
Contract for initializing, updating, and shutting down the centralized logging subsystem.

```python
from typing import Protocol, runtime_checkable
from pathlib import Path
from media_cron.logging.models import LoggingConfig


@runtime_checkable
class LoggingEngineProtocol(Protocol):
    """Core protocol for configuring and managing application-wide logging."""

    def setup(self, config: LoggingConfig) -> None:
        """
        Initializes handlers, formatters, and filters based on LoggingConfig.
        Ensures idempotency (clearing existing handlers before adding new ones).
        Creates parent directories for file targets if required.
        Raises ConfigurationError if file target cannot be initialized.
        """
        ...

    def get_effective_config(self) -> LoggingConfig:
        """Returns the currently active LoggingConfig instance."""
        ...

    def reset(self) -> None:
        """Flushes and closes all handlers and restores default Python logging state."""
        ...
```

### `LogFormatterProtocol`
Contract for formatting individual `logging.LogRecord` instances into strings.

```python
import logging
from typing import Protocol, runtime_checkable


@runtime_checkable
class LogFormatterProtocol(Protocol):
    """Protocol for transforming LogRecord instances into serialized output."""

    def format(self, record: logging.LogRecord) -> str:
        """Formats the specified LogRecord into a text or JSON string."""
        ...
```

### `SensitiveDataSanitizerProtocol`
Contract for intercepting and redacting sensitive credentials before record emission.

```python
import logging
from typing import Protocol, runtime_checkable


@runtime_checkable
class SensitiveDataSanitizerProtocol(Protocol):
    """Protocol for scrubbing sensitive patterns from log messages and attributes."""

    def sanitize_message(self, message: str) -> str:
        """Returns the sanitized message string with sensitive tokens masked."""
        ...

    def filter(self, record: logging.LogRecord) -> bool:
        """Standard logging.Filter method to redact record in-place."""
        ...
```

---

## 2. CLI Interface Contract

### CLI Options
The following options MUST be supported on the main CLI application (`app`) and available on all operational commands (`run`, `organize`, `process`, `review`, etc.):

| Option Flag | Shorthand | Type | Default | Description |
|---|---|---|---|---|
| `--log-level` | | `str` (`debug`, `info`, `warning`, `error`) | `None` (uses config/default) | Minimum log severity to emit |
| `--verbose` | `-v` | `bool` (flag) | `False` | Shorthand for `--log-level debug` |
| `--quiet` | `-q` | `bool` (flag) | `False` | Shorthand for `--log-level error` |
| `--log-file` | | `Path` | `None` | Persistent file target path for logging |
| `--console` / `--no-console` | | `bool` | `None` | Force console logging on or off |
| `--log-format` | | `str` (`text`, `json`) | `None` | Log output format |
| `--log-max-size-mb` | | `int` | `None` | Max log file size in MB before rotation |
| `--log-backup-count` | | `int` | `None` | Number of rotated log files to retain |

### Exit Codes & Error Handling

| Scenario | Exit Code | Stream | Behavior |
|---|---|---|---|
| Successful run | `0` | `stdout` | Command data and summary emitted |
| Invalid `--log-level` (e.g. `--log-level invalid`) | `2` (`EXIT_CONFIG_ERROR`) | `stderr` | Prints allowed levels: `debug`, `info`, `warning`, `error` |
| Invalid `--log-format` (e.g. `--log-format xml`) | `2` (`EXIT_CONFIG_ERROR`) | `stderr` | Prints allowed formats: `text`, `json` |
| Unwritable log file path or missing permissions | `2` (`EXIT_CONFIG_ERROR`) | `stderr` | Prints clear permission/mount error; halts before operations |
| Log file target is an existing directory | `2` (`EXIT_CONFIG_ERROR`) | `stderr` | Prints path collision error; halts |

---

## 3. UNIX Stream Guarantees

1. **Console Logs (`stderr`)**: All console log records (regardless of severity: `DEBUG`, `INFO`, `WARNING`, `ERROR`) are written strictly to standard error (`sys.stderr`).
2. **Command Payloads (`stdout`)**: Standard output (`sys.stdout`) is strictly reserved for user-requested command payloads, human-readable report tables, and machine-readable JSON objects (e.g., when `--json` flag is provided).
3. **Piping Safety**: Piped commands (e.g., `media-cron run --json | jq .processed_count`) will never encounter interleaved log records on `stdout`.
