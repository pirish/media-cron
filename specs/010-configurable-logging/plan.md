# Implementation Plan: Configurable and Comprehensive System Logging

**Branch**: `010-configurable-logging` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

---

## Summary

This feature establishes a centralized, robust, and zero-dependency logging subsystem for media-cron that addresses troubleshooting and monitoring challenges across both interactive CLI usage and unattended container/cron deployments. The architecture uses Python's standard library `logging` framework, routing console logs exclusively to standard error (`sys.stderr`) to preserve standard output (`sys.stdout`) for clean data payloads and piped JSON summaries. The system supports four severity levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`), three destination modes (`console`, `file`, `both`), automatic parent directory creation, log file size rotation (defaulting to 10MB with 5 backups), dual formatting engines (human-readable text and structured JSON), in-flight credential sanitization to prevent secrets leakage, and a four-tier configuration precedence hierarchy (CLI flags > environment variables > YAML configuration > defaults).

---

## Technical Context

**Language/Version**: Python 3.11+ (verified against Python 3.13)
**Primary Dependencies**: Python standard library (`logging`, `logging.handlers.RotatingFileHandler`, `json`, `dataclasses`, `enum`, `re`, `pathlib`, `typing`, `sys`), `typer` for CLI bindings, and `pyyaml` for configuration file loading. Zero new runtime dependencies.
**Storage**: Local filesystems, mounted container volumes, and standard POSIX text streams.
**Testing**: `pytest` with mandatory Test-Driven Development (contract tests, unit tests, integration stream verification, and end-to-end quickstart scenarios).
**Target Platform**: Linux server, container-native (Docker, Podman, Kubernetes CronJobs).
**Project Type**: Standalone Python library module and CLI media management utility.
**Performance Goals**:
- Logging overhead strictly <3% of total execution time under standard `INFO` workloads (SC-004).
- Subsystem initialization and configuration resolution in <5ms.
- Zero-copy stream writing with atomic POSIX line flushes.
**Constraints**:
- Strict adherence to Constitution Principle I: all console logs directed to `stderr`, leaving `stdout` clean for command payloads and JSON pipelines.
- Strict adherence to Constitution Principle II (TDD): contract and unit tests authored and failing before domain implementation.
- Zero credential leakage: 100% of sensitive keys (passwords, tokens, secret keys) redacted before record emission (SC-005).
- Fail-fast on unwritable log targets: immediate non-zero exit code (`EXIT_CONFIG_ERROR = 2`) with descriptive diagnostic on `stderr`.
**Scale/Scope**: Centralized logging engine serving all 14+ modules across `media_cron/`, supporting 4 severity levels, 3 destination modes, 2 serialization formats, and rotating file archives.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I: Library-First & CLI-Driven**: **PASS**. Logging domain logic is completely encapsulated in `media_cron/logging/` (`models.py`, `engine.py`, `formatter.py`, `sanitizer.py`), decoupled from schedulers or specific CLI frameworks. CLI options (`--log-level`, `-v`, `-q`, `--log-file`, `--console`, `--log-format`) are exposed uniformly across root and subcommands, strictly adhering to UNIX stream conventions (`stderr` for logs, `stdout` for command payloads/JSON).
- **Principle II: Test-First & Contract Verification (NON-NEGOTIABLE)**: **PASS**. Dedicated protocol contracts defined in `media_cron/logging/base.py` (`LoggingEngineProtocol`, `LogFormatterProtocol`, `SensitiveDataSanitizerProtocol`) with corresponding contract tests in `tests/contract/`. Unit and integration test suites will be implemented prior to domain logic.
- **Principle III: Idempotency & Failure Resilience**: **PASS**. Safe atomic line appending in POSIX filesystems, bounded disk footprint via size rotation (10MB x 5 backups), and fail-fast startup on unwritable paths preventing silent unlogged operations.
- **Principle IV: Structured Observability & Diagnosability**: **PASS**. Core foundation of this feature. Implements consistent log levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`), ISO-8601 timestamps, machine-readable JSON format, deterministic exit codes, and clean stack trace suppression in non-debug operational modes.
- **Principle V: Container-Native & Environment Isolation**: **PASS**. Fully configurable via `MEDIA_CRON_LOG_*` environment variables and `config.yaml`. Default stderr logging integrates natively with container runtimes (Docker, Podman, Kubernetes), while file logging is suitable for dedicated volume mounts.

---

## Project Structure

### Documentation (this feature)

```text
specs/010-configurable-logging/
├── plan.md                                      # This implementation plan
├── research.md                                  # Phase 0 technical decisions & framework research
├── data-model.md                                # Phase 1 domain entities, enums, & schemas
├── quickstart.md                                # 5 runnable end-to-end validation scenarios
├── checklists/
│   └── requirements.md                          # Specification quality checklist
├── contracts/
│   ├── logging-interface.md                     # Python protocols, CLI flags, & stream contracts
│   ├── config-schema.md                         # YAML schema & environment variable bindings
│   └── json-log-schema.md                       # JSON schema for machine-readable log records
└── tasks.md                                     # Task breakdown generated by /speckit-tasks
```

### Source Code (repository root)

```text
media_cron/
├── logging/
│   ├── __init__.py                              # Public package exports (setup_logging, get_logger, LoggingConfig)
│   ├── models.py                                # LogLevel, LogDestination, LogFormat, LoggingConfig
│   ├── base.py                                  # LoggingEngineProtocol, LogFormatterProtocol, SensitiveDataSanitizerProtocol
│   ├── formatter.py                             # StandardTextFormatter, JsonLogFormatter
│   ├── sanitizer.py                             # SensitiveDataFilter, credential redaction patterns
│   └── engine.py                                # LoggingEngine implementation, handlers, directory creation
├── config.py                                    # LoggingConfig integration into MediaCronConfig & env overrides
├── cli.py                                       # Global logging CLI options & setup_logging lifecycle hook
└── pipeline.py                                  # Comprehensive operational log records across pipeline stages

tests/
├── contract/
│   ├── test_logging_engine_contract.py          # Contract verification for LoggingEngineProtocol
│   ├── test_log_formatter_contract.py           # Contract verification for LogFormatterProtocol
│   └── test_log_sanitizer_contract.py           # Contract verification for SensitiveDataSanitizerProtocol
├── unit/
│   └── logging/
│       ├── test_logging_models.py               # Enums, validation rules, and precedence logic
│       ├── test_formatters.py                   # Text and JSON serialization correctness
│       ├── test_sanitizer.py                    # Credential masking across messages and attributes
│       └── test_engine.py                       # Handler creation, stream routing, rotation, and errors
└── integration/
    ├── test_logging_cli_streams.py              # stdout/stderr isolation and --json piping safety
    └── test_logging_configuration.py            # Precedence hierarchy (CLI > Env > YAML > Default)
```

**Structure Decision**: The logging engine is isolated in a modular package `media_cron/logging/` with clear protocol boundaries in `base.py`, keeping it decoupled from CLI and pipeline logic while providing a clean `setup_logging` entry point for `media_cron/cli.py` and `media_cron/config.py`.

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | *All architectural choices adhere strictly to constitution principles and use standard library tools without external dependencies.* | *N/A* |
