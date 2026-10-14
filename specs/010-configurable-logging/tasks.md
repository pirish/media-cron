# Tasks: Configurable and Comprehensive System Logging

**Branch**: `010-configurable-logging` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize logging subsystem package structure, protocol contracts, and domain models.

- [X] T001 Create logging package directory in `media_cron/logging/` and test directories in `tests/contract/` and `tests/unit/logging/`
- [X] T002 [P] Define core logging protocols in `media_cron/logging/base.py` (`LoggingEngineProtocol`, `LogFormatterProtocol`, `SensitiveDataSanitizerProtocol`)
- [X] T003 [P] Define domain enums and models in `media_cron/logging/models.py` (`LogLevel`, `LogDestination`, `LogFormat`, `LoggingConfig`, `LogRecordPayload`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core engine infrastructure, configuration schema integration, and protocol contract verification that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Create contract tests for `LoggingEngineProtocol` in `tests/contract/test_logging_engine_contract.py`
- [X] T005 [P] Create unit tests for logging models, validation invariants, and enum parsing in `tests/unit/logging/test_logging_models.py`
- [X] T006 [P] Implement core `LoggingEngine` lifecycle skeleton (`setup`, `reset`, `get_effective_config`) in `media_cron/logging/engine.py`
- [X] T007 [P] Integrate `LoggingConfig` into `MediaCronConfig` with YAML loading and environment variable overrides in `media_cron/config.py`
- [X] T008 Wire public package exports (`setup_logging`, `get_logger`, `LoggingConfig`) in `media_cron/logging/__init__.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel or sequentially.

---

## Phase 3: User Story 1 - Default Out-of-the-Box Console Logging (Priority: P1) 🎯 MVP

**Goal**: Running any media-cron command without logging configuration or flags automatically emits `INFO` level logs to `stderr`, leaving `stdout` cleanly dedicated to command output payloads and piped JSON summaries.

**Independent Test**: Execute `media-cron run --dry-run` with empty configuration; verify `stderr` receives ISO-formatted `[INFO]` log entries while `stdout` contains only command summary tables or clean JSON.

### Tests for User Story 1 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T009 [P] [US1] Create contract tests for `LogFormatterProtocol` (Text Formatter) in `tests/contract/test_log_formatter_contract.py`
- [X] T010 [P] [US1] Create unit tests for `StandardTextFormatter` and stream routing to `stderr` in `tests/unit/logging/test_text_formatter.py`
- [X] T011 [P] [US1] Create integration tests verifying stdout/stderr stream isolation during CLI runs in `tests/integration/test_logging_cli_streams.py`

### Implementation for User Story 1

- [X] T012 [US1] Implement `StandardTextFormatter` with ISO timestamps, severity levels, and logger names in `media_cron/logging/formatter.py`
- [X] T013 [US1] Implement default console `StreamHandler` targeting `sys.stderr` in `media_cron/logging/engine.py`
- [X] T014 [US1] Hook `setup_logging()` into Typer CLI application startup and lifecycle in `media_cron/cli.py`

**Checkpoint**: At this point, User Story 1 is fully functional and delivers an immediate MVP for all executions.

---

## Phase 4: User Story 2 - Configurable Logging Level & Verbosity (Priority: P2)

**Goal**: Operators can adjust log levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`) via CLI arguments (`--log-level`, `-v`/`--verbose`, `-q`/`--quiet`), environment variables, and `config.yaml`, with strict precedence resolution and validation.

**Independent Test**: Run media-cron with `-v`/`--verbose` or `--log-level debug` and verify `DEBUG` logs appear; run with `--log-level error` and verify routine logs are suppressed; run with an invalid level and verify exit code 2.

### Tests for User Story 2 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T015 [P] [US2] Create unit tests for log level filtering, verbosity flags, and invalid level validation in `tests/unit/logging/test_log_levels.py`
- [X] T016 [P] [US2] Create integration tests for configuration precedence hierarchy (CLI > Env > YAML > Default) in `tests/integration/test_logging_configuration.py`

### Implementation for User Story 2

- [X] T017 [US2] Add CLI options (`--log-level`, `-v`/`--verbose`, `-q`/`--quiet`) to main app and operational commands in `media_cron/cli.py`
- [X] T018 [US2] Implement configuration precedence resolution helper in `media_cron/logging/models.py`
- [X] T019 [US2] Add validation for unrecognized log levels emitting allowed levels to `stderr` and exiting with `EXIT_CONFIG_ERROR` (code 2) in `media_cron/cli.py`

**Checkpoint**: User Stories 1 and 2 work independently, enabling deep local troubleshooting via verbose flags.

---

## Phase 5: User Story 3 - Configurable Log Destinations & Rotation (Priority: P3)

**Goal**: Support logging to persistent files, console, or both simultaneously. Auto-create missing destination directories, enforce exclusive file logging by default, fail fast on unwritable paths, and rotate logs at 10MB retaining 5 backups.

**Independent Test**: Specify `--log-file /tmp/nested/media-cron.log` in a non-existent directory; verify parent folders are auto-created, logs are written to the file, and console output is silenced. Specify `--console` alongside `--log-file` and verify dual logging.

### Tests for User Story 3 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T020 [P] [US3] Create unit tests for `RotatingFileHandler` initialization, directory auto-creation, and file rotation in `tests/unit/logging/test_file_destination.py`
- [X] T021 [P] [US3] Create unit tests for destination modes (`console`, `file`, `both`) and unwritable destination fail-fast error handling in `tests/unit/logging/test_destination_modes.py`
- [X] T022 [P] [US3] Create integration tests for file-only and dual-destination CLI execution in `tests/integration/test_logging_destinations.py`

### Implementation for User Story 3

- [X] T023 [US3] Implement `RotatingFileHandler` with automated parent directory creation and default rotation thresholds (10MB x 5 backups) in `media_cron/logging/engine.py`
- [X] T024 [US3] Implement destination routing logic for exclusive file logging (console silenced) and dual logging (`both` mode) in `media_cron/logging/engine.py`
- [X] T025 [US3] Add destination CLI options (`--log-file`, `--console`, `--no-console`, `--log-max-size-mb`, `--log-backup-count`) in `media_cron/cli.py`

**Checkpoint**: User Stories 1, 2, and 3 are functional, supporting production cron jobs and persistent log files.

---

## Phase 6: User Story 4 - Comprehensive Contextual Logging Across Pipeline Operations (Priority: P4)

**Goal**: Ingesting files across media types emits consistent, contextual log events across all pipeline stages (intake discovery, classification, metadata lookup, file transfers, client notifications, review staging, and batch completion) with clean error formatting.

**Independent Test**: Process a multi-category batch of media files; verify that emitted log records document every file through intake, metadata resolution, transfer outcome, and batch completion without noisy stack traces unless DEBUG mode is active.

### Tests for User Story 4 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T026 [P] [US4] Create integration tests verifying lifecycle stage log records and stack trace suppression in `tests/integration/test_pipeline_logging.py`

### Implementation for User Story 4

- [X] T027 [US4] Add structured operational log records to intake and discovery stages in `media_cron/pipeline.py`
- [X] T028 [US4] Add contextual log records to metadata identification and classification in `media_cron/metadata/` and `media_cron/routing/engine.py`
- [X] T029 [US4] Add contextual log records for file transfer operations (move, copy, hardlink, and dry-run simulation) in `media_cron/pipeline.py`
- [X] T030 [US4] Add operational log records to torrent client integration and review staging in `media_cron/torrent/` and `media_cron/review/manager.py`
- [X] T031 [US4] Implement clean error message diagnostics at INFO/WARNING/ERROR levels and full stack traces only in DEBUG mode in `media_cron/cli.py` and `media_cron/pipeline.py`

**Checkpoint**: Full end-to-end operational visibility across all media types and processing modules.

---

## Phase 7: User Story 5 - Structured JSON Logging & Credential Redaction (Priority: P5)

**Goal**: Support machine-readable single-line JSON log formatting (`--log-format json`) for container log aggregators, and enforce automatic in-flight redaction of passwords, tokens, and secret keys across all formats and destinations.

**Independent Test**: Execute commands with `--log-format json` and verify each output line matches `contracts/json-log-schema.md`; inject test passwords and API tokens and verify they are masked as `***REDACTED***`.

### Tests for User Story 5 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T032 [P] [US5] Create contract tests for `SensitiveDataSanitizerProtocol` in `tests/contract/test_log_sanitizer_contract.py`
- [X] T033 [P] [US5] Create unit tests for `JsonLogFormatter` validating adherence to JSON schema in `tests/unit/logging/test_json_formatter.py`
- [X] T034 [P] [US5] Create unit tests for `SensitiveDataFilter` password and token pattern redaction in `tests/unit/logging/test_sanitizer.py`

### Implementation for User Story 5

- [X] T035 [US5] Implement `JsonLogFormatter` conforming to `contracts/json-log-schema.md` in `media_cron/logging/formatter.py`
- [X] T036 [US5] Implement `SensitiveDataFilter` with regex rules for passwords, tokens, and API keys in `media_cron/logging/sanitizer.py`
- [X] T037 [US5] Attach `SensitiveDataFilter` to all active handlers during engine setup in `media_cron/logging/engine.py`
- [X] T038 [US5] Add `--log-format` (`text`, `json`) CLI option and `MEDIA_CRON_LOG_FORMAT` env override in `media_cron/cli.py`

**Checkpoint**: Complete container-native structured observability with guaranteed credential safety.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, documentation updates, full regression test execution, and code quality verification.

- [X] T039 [P] Execute all 5 validation scenarios documented in `specs/010-configurable-logging/quickstart.md`
- [X] T040 [P] Update documentation in `README.md` with logging configuration options, environment variables, and CLI flag reference
- [X] T041 Run full test suite with `pytest` to verify zero regressions across existing test suites
- [X] T042 Run linter and formatter checks with `ruff check .` and `ruff format --check .`

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational) ───► [BLOCKS ALL USER STORIES]
    │
    ├───────────────────────┬───────────────────────┬───────────────────────┐
    ▼                       ▼                       ▼                       ▼
Phase 3 (US1: Default)  Phase 4 (US2: Levels)  Phase 5 (US3: Sinks)    Phase 7 (US5: JSON)
    │                       │                       │                       │
    └───────────────────────┴───────────┬───────────┴───────────────────────┘
                                        ▼
                               Phase 6 (US4: Pipeline Context)
                                        │
                                        ▼
                               Phase 8 (Polish & Verification)
```

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Foundational (Phase 2). Delivers standalone MVP.
- **User Story 2 (P2)**: Depends on Foundational (Phase 2). Integrates with US1 formatter/handlers.
- **User Story 3 (P3)**: Depends on Foundational (Phase 2). Adds file handler and rotation to engine.
- **User Story 4 (P4)**: Depends on US1, US2, and US3. Enriches pipeline modules with contextual log calls.
- **User Story 5 (P5)**: Depends on Foundational (Phase 2). Adds JSON formatter and sanitizer filter to engine.

### Within Each User Story
1. Tests MUST be authored and fail before writing implementation code.
2. Formatter and filter components before engine integration.
3. Engine integration before CLI options wiring.
4. Verify independent test criteria at each story checkpoint.

---

## Parallel Execution Examples

### Parallel Example: User Story 1
```bash
# Launch contract, unit, and integration tests in parallel:
Task T009: tests/contract/test_log_formatter_contract.py
Task T010: tests/unit/logging/test_text_formatter.py
Task T011: tests/integration/test_logging_cli_streams.py
```

### Parallel Example: User Story 3
```bash
# Launch unit and integration tests in parallel:
Task T020: tests/unit/logging/test_file_destination.py
Task T021: tests/unit/logging/test_destination_modes.py
Task T022: tests/integration/test_logging_destinations.py
```

### Parallel Example: User Story 5
```bash
# Launch contract and unit tests in parallel:
Task T032: tests/contract/test_log_sanitizer_contract.py
Task T033: tests/unit/logging/test_json_formatter.py
Task T034: tests/unit/logging/test_sanitizer.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (User Story 1).
3. **STOP and VALIDATE**: Run `media-cron run --dry-run` to verify default `INFO` logging on `stderr` and clean `stdout`.
4. The system is immediately usable with clear console feedback without any configuration required.

### Incremental Delivery
1. **Increment 1 (MVP)**: Default console logging on `stderr` (US1).
2. **Increment 2**: Granular verbosity via `--log-level` and `-v`/`-q` flags (US2).
3. **Increment 3**: Persistent rotating file logging for automated cron jobs (US3).
4. **Increment 4**: Comprehensive operational logs across all pipeline stages (US4).
5. **Increment 5**: Structured JSON formatting and credential redaction (US5).
6. **Increment 6**: End-to-end quickstart validation and documentation polish.
