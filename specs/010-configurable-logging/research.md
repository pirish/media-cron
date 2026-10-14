# Technical Research & Architecture Decisions: Configurable Logging

**Branch**: `010-configurable-logging` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

---

## 1. Logging Framework Selection

### Decision
Use Python's built-in standard library `logging` module with custom `logging.Formatter` and `logging.Filter` components.

### Rationale
- **Zero Runtime Dependencies**: Python's standard `logging` is ubiquitous, highly optimized, thread-safe, and requires no external third-party dependencies, adhering directly to Constitution Principle I (Library-First) and Principle V (Container-Native & Environment Isolation).
- **Native Codebase Compatibility**: The existing `media_cron` codebase already uses standard `logging.getLogger(__name__)` across 14+ modules (e.g. `media_cron/pipeline.py`, `media_cron/review/manager.py`, `media_cron/metadata/*`). Configuring the root or package logger seamlessly activates comprehensive logging throughout the entire application without refactoring existing logger call sites.
- **Customizable Extension Points**: The standard library provides battle-tested hooks (`logging.Handler`, `logging.Formatter`, `logging.Filter`) for rotation, formatting (text and JSON), and in-flight credential sanitization.

### Alternatives Considered
- `structlog`: Powerful structured logging library, but introduces external runtime dependencies and requires wrapping existing logger instances or complex bridging layers.
- `loguru`: Ergonomic and popular, but maintains its own handler sink abstraction that conflicts with standard `logging.getLogger()` calls without intercept handlers, adding unnecessary runtime overhead and complexity.

---

## 2. Console Stream Routing (UNIX Text Stream Convention)

### Decision
Direct all console logging records to standard error (`sys.stderr`), keeping standard output (`sys.stdout`) strictly reserved for command data payloads, tables, and machine-readable JSON summaries.

### Rationale
- **Constitution Principle I Compliance**: The Media-Cron Constitution explicitly dictates: *"Each module MUST expose its core functionality via a dedicated CLI entry point following standard UNIX text stream conventions (arguments/stdin → stdout, errors → stderr). CLI commands MUST support both machine-parsable JSON output and human-readable text formatting."*
- **Pipeline and Tool Composability**: Commands such as `media-cron run --json` or `media-cron routes list --json` output JSON payloads to stdout for consumption by piping into tools like `jq`, scripts, or orchestrators. Directing log messages to stdout would interleave log text into the JSON stream, causing JSON parsing syntax errors.
- **Precedent**: Established across the existing CLI (`media_cron/cli.py`), where status and error messages already use `typer.echo(..., err=True)`.

### Alternatives Considered
- **Severity-based split (`stdout` for INFO/DEBUG, `stderr` for WARNING/ERROR)**: Rejected because routine INFO logs would pollute stdout during `--json` execution.
- **All logs to `stdout`**: Rejected as it breaks UNIX stream isolation and prevents command piping.

---

## 3. Log Formatting Architecture (Text vs. Structured JSON)

### Decision
Implement two dedicated formatters in `media_cron/logging/formatter.py`:
1. `StandardTextFormatter`: Produces clean, readable terminal output:
   `YYYY-MM-DD HH:MM:SS [LEVEL] logger.name: Message text`
2. `JsonLogFormatter`: Produces single-line JSON objects conforming to the schema:
   `{"timestamp": "...", "level": "INFO", "logger": "media_cron.pipeline", "message": "...", "context": {...}, "exception": null}`

### Rationale
- **Human Readability**: Local developers and terminal operators require clean, legible timestamps and levels without noisy JSON delimiters when troubleshooting.
- **Log Aggregator Ingestion**: Cloud and container log collectors (Fluentbit, Promtail, Vector, Datadog) ingest single-line JSON streams to index log records by timestamp, severity, and component without regex parsing.
- **Lightweight Implementation**: A standard library `json.dumps`-based formatter is ~40 lines of code, deterministic, and adds negligible CPU overhead (<1%).

### Alternatives Considered
- `python-json-logger`: External package offering JSON formatting; rejected to avoid adding a dependency for trivial JSON serialization.

---

## 4. In-Flight Credential Sanitization & Redaction

### Decision
Implement a custom `logging.Filter` (`SensitiveDataFilter`) attached to all handlers that inspects log message strings and structured record attributes before emission, masking matched secrets with `***REDACTED***`.

### Rationale
- **Universal Protection**: Intercepts log records from all loggers (core, plugins, third-party libraries) before they reach any handler or destination.
- **Defense in Depth**: Protects against accidental leakage of qBittorrent passwords, Discogs tokens, and OpenLibrary/media server API keys that may appear in configuration dumps or error messages.
- **Regex & Keyword Pattern Matching**: Targets patterns including:
  - Key-value pairs: `(password|token|secret|api_key|auth|pass)=['"]?([^'"\s&]+)`
  - URL credentials: `(https?://[^:]+:)([^@]+)(@)`

### Alternatives Considered
- **Manual sanitization at call sites**: High risk of omission by developers adding new log statements.
- **Custom Logger class override**: Requires replacing the logger factory, which can conflict with third-party libraries and testing tools.

---

## 5. File Destination Management & Rotation

### Decision
Use `logging.handlers.RotatingFileHandler` with automatic directory creation and fail-fast validation.

### Rationale
- **Bounded Storage Footprint**: Prevents unbounded disk growth on unattended cron servers (Constitution Principle III & V).
- **Default Policy**: 10 MB per file (`maxBytes = 10,485,760`), retaining up to 5 backup files (`backupCount = 5`).
- **Fail-Fast Startup**: If the target directory cannot be created or the file is unwritable, `setup_logging` raises a `ConfigurationError` and exits cleanly with `EXIT_CONFIG_ERROR` (code 2), emitting a descriptive error to `stderr` rather than continuing silently without logging.
- **Atomic Line Writes**: In POSIX operating systems, appending to files opened in append mode (`a`) is atomic for writes under page size limits, ensuring safe concurrent execution by multiple processes.

### Alternatives Considered
- `TimedRotatingFileHandler`: Rotates at midnight or hourly; rejected because bursty file-processing operations can generate large volume within a single interval, risking disk exhaustion.
- Unrotated plain file: Unacceptable for automated production systems.

---

## 6. Configuration Precedence & Hierarchical Overrides

### Decision
Enforce a four-tier configuration resolution hierarchy:
1. **CLI Flags**: `--log-level`, `-v` / `--verbose`, `-q` / `--quiet`, `--log-file`, `--console`, `--no-console`, `--log-format` (Highest)
2. **Environment Variables**: `MEDIA_CRON_LOG_LEVEL`, `MEDIA_CRON_LOG_DESTINATION`, `MEDIA_CRON_LOG_FILE`, `MEDIA_CRON_LOG_FORMAT`, `MEDIA_CRON_LOG_MAX_SIZE_MB`, `MEDIA_CRON_LOG_BACKUP_COUNT`
3. **Configuration File**: `logging:` section in `config.yaml`
4. **Built-in Defaults**: Level `INFO`, destination `console` (via `stderr`), format `text`, rotation 10MB x 5 backups (Lowest)

### Rationale
- Matches Twelve-Factor app principles and existing media-cron precedence conventions established in `media_cron/config.py`.
- Allows temporary ad-hoc debugging via `-v` without editing configuration files, while enabling scheduled cron jobs to enforce consistent file destinations via environment variables or YAML.

---

## Summary of Architectural Decisions

| Area | Decision | Key Rationale |
|---|---|---|
| **Engine** | Standard Python `logging` | 0 dependencies, native compatibility with existing `media_cron` loggers |
| **Console Stream** | `sys.stderr` exclusively | Preserves clean `stdout` for command outputs and `--json` summaries |
| **Formats** | `text` (default) & `json` | Human terminal readability + machine-readable container ingestion |
| **Redaction** | In-flight `SensitiveDataFilter` | Universal masking of passwords, tokens, and keys across all sinks |
| **File Sinks** | `RotatingFileHandler` (10MB x 5) | Prevents disk exhaustion, auto-creates parent directories |
| **Precedence** | CLI > Env Vars > Config > Default | Flexible local troubleshooting and predictable production configuration |
