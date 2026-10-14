# Feature Specification: Configurable and Comprehensive System Logging

**Feature Branch**: `010-configurable-logging`

**Created**: 2026-10-14

**Status**: Ready

**Input**: User description: "troubleshooting and monitoring is difficult without proper logging. Add comprehensive logging. Logging should be configurable for both level/verbosity and destination. If not configured it should default to info level to the console"

## Clarifications

### Session 2026-10-14
- Q: Which console stream should receive log messages during execution, especially when commands emit structured machine-readable output? (FR-002) → A: Send all console logs to standard error (`stderr`), keeping standard output (`stdout`) dedicated strictly to command output and JSON payloads.
- Q: When an operator configures a file destination for logging, should log output be written exclusively to that file, or should it mirror to the console simultaneously? (FR-006) → A: Exclusive file output: route all routine logs to the file and silence console output unless dual logging (`both`) is explicitly requested.
- Q: Should the logging subsystem support network-based log transports (such as syslog, network sockets, or HTTP endpoints) in this feature, or be restricted to local console and filesystem targets? (FR-006) → A: Local only: support console and local filesystem targets only; external shippers handle remote forwarding.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Default Out-of-the-Box Console Logging (Priority: P1) 🎯 MVP

An operator runs media-cron commands (such as running the organization pipeline, checking system status, or synchronizing libraries) without providing any specialized logging configuration or flags. The operator expects clear, informative feedback on the console showing the progress and outcome of the operation at an `INFO` level by default, with no silent executions or complex setup required.

**Why this priority**: Core baseline requirement. Fulfills the explicit user requirement that unconfigured executions default to `INFO` level console output, delivering an immediate observable experience for all existing and new users.

**Independent Test**: Execute any media-cron command with a minimal or blank configuration and without logging flags; verify that high-level progress (e.g., job start, assets detected, actions executed, completion status) is emitted to standard console streams at the `INFO` level.

**Acceptance Scenarios**:

1. **Given** an environment with no logging configuration specified, **When** an operator runs a media-cron command, **Then** the system emits operational progress messages to standard error (`stderr`) at the `INFO` level, keeping standard output (`stdout`) clean for command data and results.
2. **Given** default execution settings, **When** routine operational events take place (e.g., starting an ingestion scan, reporting file counts, batch completion), **Then** each log entry clearly displays a timestamp, severity indicator, and descriptive text.
3. **Given** default execution settings, **When** non-fatal warnings or operational errors occur, **Then** the messages are visibly reported to the console with clear diagnostic details.
4. **Given** default execution settings, **When** internal low-level diagnostic events are generated, **Then** they are suppressed from console output so normal logs remain concise and uncluttered.

---

### User Story 2 - Configurable Logging Level & Verbosity (Priority: P2)

An administrator or developer encounters an unexpected issue (e.g., a media file failing to match metadata, or a torrent client connection failing) and needs deep diagnostic details. The user specifies a `DEBUG` verbosity level via CLI arguments (e.g., `--verbose` or `--log-level debug`), environment variables, or a configuration file to inspect step-by-step decision making. Conversely, an automated cron scheduler can specify a `WARNING` or `ERROR` level to suppress routine output and only alert when issues occur.

**Why this priority**: Directly addresses the troubleshooting challenge. Enables operators to inspect detailed inner workings on demand without modifying code or cluttering routine runs.

**Independent Test**: Execute an organization run with log level set to `DEBUG`; verify that granular decision logs (e.g., metadata queries, candidate scores, skipped files) appear. Re-run with log level set to `ERROR`; verify that only error events appear and all informational lines are suppressed.

**Acceptance Scenarios**:

1. **Given** a log level configured as `DEBUG` (via CLI argument, environment variable, or config file), **When** media-cron processes files, **Then** comprehensive diagnostic logs (including sub-step progress, parameter evaluations, and external call payloads) are emitted.
2. **Given** a log level configured as `WARNING` or `ERROR`, **When** media-cron runs without failures, **Then** routine informational messages are suppressed and no output is emitted for successful steps.
3. **Given** multiple configuration sources (CLI flags, environment variables, configuration file), **When** conflicting log levels are provided, **Then** the system applies settings in strict precedence order: CLI flags override environment variables, which override configuration file entries, which override the default `INFO` level.
4. **Given** an invalid or unrecognized log level specified by the operator, **When** media-cron initializes, **Then** it rejects the invalid value with a clear diagnostic message listing valid levels and exits with a configuration error code.

---

### User Story 3 - Configurable Log Destinations (Priority: P3)

A system administrator operating media-cron as a scheduled background service or container needs logs persisted to a designated file path (e.g., `/var/log/media-cron/media-cron.log`) for historical auditing and troubleshooting. The administrator needs to configure the destination to a file, to the console, or to both simultaneously (mirroring logs to both file and console for container monitoring).

**Why this priority**: Essential for non-interactive production environments where console outputs are lost once the process terminates. Enables persistent audit trails and integration with log monitoring tools.

**Independent Test**: Configure the logging destination to a designated file path; run a media-cron command; verify the file is created, contains the complete log entries with appropriate timestamps and levels, and that directory paths are created automatically if needed.

**Acceptance Scenarios**:

1. **Given** a destination configured as a file path, **When** media-cron executes, **Then** all qualifying log messages are appended exclusively to the specified log file, and routine console output is silenced unless dual logging is enabled.
2. **Given** a configured destination file in a directory that does not yet exist, **When** the logging system initializes, **Then** it automatically creates the missing parent directory structure if permissions permit.
3. **Given** a configuration specifying dual destinations (both console and file), **When** operations run, **Then** log records are emitted simultaneously to both the console stream and the persistent log file.
4. **Given** a file destination path that is unwritable due to filesystem permissions or invalid mounts, **When** media-cron starts, **Then** the process immediately reports a descriptive permission failure to the console and aborts with a non-zero exit code to prevent silent unlogged operations.
5. **Given** a configured file destination with log rotation enabled, **When** the log file reaches the configured maximum file size, **Then** the file is rotated with historical backups retained according to the retention limit without data loss.

---

### User Story 4 - Comprehensive Contextual Logging Across Pipeline Operations (Priority: P4)

A media collector processes a mixed batch of media (audiobooks, music, video, books). During execution, the operator needs every stage of the pipeline—file discovery, media classification, provider lookups, file transfers/symlinks, torrent client seeding relocation, and review staging—to produce clear, contextual log records that identify which file is affected, which operation was executed, and the outcome.

**Why this priority**: Solves the core user problem: "troubleshooting and monitoring is difficult without proper logging." Ensures uniform, rich context across all media types and processing stages.

**Independent Test**: Ingest a sample batch of varied media files; verify that the emitted log records follow every file from discovery through identification, transfer, and completion, with consistent identifiers and status markers.

**Acceptance Scenarios**:

1. **Given** incoming files scanned during intake, **When** files are evaluated, **Then** the log records the file path, detected media type, and the reason for processing or skipping.
2. **Given** external client interactions (e.g., torrent client status updates, media server library rescans, metadata provider lookups), **When** requests succeed or fail, **Then** the log captures the target service, duration, outcome, and error response if applicable.
3. **Given** file transfer operations (copy, move, hardlink, symlink), **When** each transfer is attempted, **Then** the log records the exact source path, destination path, transfer mode, and operation result.
4. **Given** an unexpected exception or critical failure during processing, **When** the error occurs, **Then** the log records the failing component and context, providing a full stack trace if in `DEBUG` mode and a concise summary if in normal operational mode.
5. **Given** an execution running in dry-run mode, **When** operations are planned, **Then** every planned action is logged with an explicit dry-run indicator without modifying any filesystem state.

---

### User Story 5 - Structured and Machine-Readable Log Formatting (Priority: P5)

An operator deploying media-cron in a containerized environment (e.g., Docker, Kubernetes CronJob) uses a log aggregator (such as Fluentbit, Promtail, or Datadog). The operator configures the log format to `json` so that every log line is a structured, machine-parsable object containing standardized fields for automated ingestion, search, and alerting.

**Why this priority**: Adheres to Project Constitution Principle IV (Structured Observability) and Principle V (Container-Native & Environment Isolation). Enables seamless integration into centralized monitoring stacks.

**Independent Test**: Set the log format configuration to `json`; execute a command; verify that every emitted log record is a valid single-line JSON object containing standard schema fields.

**Acceptance Scenarios**:

1. **Given** a configuration specifying `json` format, **When** media-cron emits log entries, **Then** each record is output as a valid, single-line JSON object containing timestamp, severity level, component name, and message.
2. **Given** the default configuration or an explicit `text` format, **When** media-cron emits log entries, **Then** output is formatted in clean, human-readable text suitable for terminal viewing.
3. **Given** structured log records in JSON format, When operational context (such as file paths, media types, or error codes) is present, Then the context is emitted as structured key-value properties rather than embedded unstructured text strings.

---

### Edge Cases

- **Unwritable or Missing Destination Directory**: What happens if the configured log file path resides on a read-only filesystem or a directory lacking write permissions? The system must fail fast during startup, emit a clear diagnostic error to standard error, and exit with a distinct configuration error code rather than proceeding silently without logs.
- **Concurrent Media-Cron Executions**: How does the logging subsystem handle multiple cron instances or background processes writing to the same log file? Log file writes must operate in append mode with atomic line flushes so that interleaved entries do not corrupt each other or overwrite previous records.
- **Disk Exhaustion During Run**: How does the system respond if the storage volume containing the log file runs out of space during processing? The system must attempt to emit an alert to the console/standard error stream and safely abort ongoing file transfers to prevent data corruption.
- **Handling of Sensitive Information**: What happens if configuration files or environment variables contain passwords or API tokens for torrent clients or media servers? The logging subsystem must sanitize and redact sensitive values (passwords, tokens, secret keys) before records are emitted to any destination.
- **High-Volume / Rapid-Fire Logging**: What happens during large-scale scans involving tens of thousands of files? The logging subsystem must maintain minimal overhead at standard `INFO` level, avoiding excessive I/O bottlenecks while still recording summary statistics and batch milestones.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a centralized logging subsystem that is universally applied across all media-cron CLI commands, library modules, and background processing pipelines.
- **FR-002**: System MUST default logging destination to the console via standard error (`stderr`) at `INFO` severity level when no explicit logging configuration is supplied, keeping standard output (`stdout`) dedicated to command payloads and structured outputs.
- **FR-003**: System MUST support configurable logging levels: `DEBUG`, `INFO`, `WARNING`, and `ERROR`.
- **FR-004**: System MUST allow configuring the logging level via CLI arguments (e.g., `--log-level`, `-v`/`--verbose`, `-q`/`--quiet`), environment variables, and the media-cron configuration file.
- **FR-005**: System MUST enforce a strict configuration precedence order: CLI arguments take highest priority, followed by environment variables, followed by configuration file settings, falling back to built-in defaults.
- **FR-006**: System MUST support configurable local log destinations, allowing output to be directed to:
  - `console` (standard terminal error stream `stderr`)
  - A persistent local file path (exclusive file output by default, suppressing routine console output)
  - Both `console` and local file simultaneously when explicitly requested (e.g., via `destination: both` in configuration or `--console` flag alongside file destination)
  Remote network transports (e.g., syslog, network sockets, HTTP collectors) are strictly out of scope for the internal logging engine.
- **FR-007**: System MUST automatically create any missing parent directories for a configured file destination when filesystem permissions permit.
- **FR-008**: System MUST support log file size rotation and retention policies (maximum file size and number of rotated backup files) when logging to a file destination.
- **FR-009**: System MUST emit comprehensive log events across all core pipeline stages: initialization, configuration loading, media file discovery, classification, metadata identification, file transfers, client integration updates, review staging, and process completion.
- **FR-010**: System MUST include consistent contextual metadata in every log record: an ISO-8601 timestamp, severity level, module/component identifier, and a descriptive message.
- **FR-011**: System MUST support both human-readable text format (default for console) and structured machine-readable JSON format (for automated log collection).
- **FR-012**: System MUST automatically redact sensitive parameters (passwords, API tokens, auth credentials) from all emitted log records across all destinations and formats.
- **FR-013**: System MUST display full error stack traces only when the log level is set to `DEBUG`; at `INFO`, `WARNING`, and `ERROR` levels, the system MUST emit concise, actionable error messages without noisy stack traces.
- **FR-014**: System MUST clearly identify simulated operations in log records when executing under dry-run mode.
- **FR-015**: System MUST validate logging configuration at startup and return distinct non-zero exit codes if the configuration or file destination is invalid.

### Key Entities *(include if feature involves data)*

- **LoggingConfiguration**: Represents the operational logging parameters, including active log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`), destination mode (`console`, `file`, or `both`), log file path, rotation thresholds (max size, backup retention count), and output format (`text` or `json`).
- **LogRecord**: Represents an individual operational event, encapsulating the event timestamp, severity level, origin component/subsystem name, primary event message, optional structured contextual attributes (e.g., file path, media category, duration), and optional exception diagnostics.
- **LogDestination**: Represents the output channel for log events, abstracting terminal streams (stdout/stderr) and persistent filesystem targets with rotation handling.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of media-cron operations and CLI entry points emit logging through the centralized subsystem without unhandled silent failures.
- **SC-002**: When invoked with no logging configuration or flags, 100% of commands immediately emit legible `INFO` level output to the console with zero setup required.
- **SC-003**: Specifying a log level or destination via CLI arguments, environment variables, or config file applies uniformly across 100% of pipeline modules.
- **SC-004**: System logging introduces less than 3% overhead to total job execution duration under standard `INFO` level operational workloads.
- **SC-005**: 100% of configured credentials, tokens, and passwords are confirmed redacted from emitted log records in both text and JSON formats.
- **SC-006**: When file destination is configured, log records persist accurately and can be searched and parsed by standard system utilities without formatting corruption.

---

## Assumptions

- **Console Stream Convention**: When console logging is enabled, all log records regardless of severity level are directed to standard error (`stderr`), keeping standard output (`stdout`) cleanly isolated for command data and structured JSON payloads in accordance with UNIX conventions and Project Constitution Principle I.
- **File Destination Output Mode**: When a file destination is configured without explicit dual-logging settings, routine logging is written exclusively to the file target while terminal stderr only receives fatal startup errors or missing-file diagnostics.
- **Local Target Scope**: Remote log streaming protocols (syslog, socket daemons, HTTP endpoints) are out of scope for the internal logging engine; container runtimes and log collectors handle remote forwarding from standard error streams or mounted log files.
- **Default Formatting**: The default formatting is standardized human-readable text for terminal visibility; structured JSON format is opt-in for automated monitoring stacks.
- **File Rotation Defaults**: When a file destination is configured without explicit rotation limits, sensible defaults (e.g., 10 megabytes per file, retaining up to 5 backups) are applied to protect disk storage.
- **Fail-Fast on Inaccessible Destination**: If a designated log file destination cannot be created or opened for writing due to permission or mount errors, the application halts immediately with a clear error on standard error to prevent untracked execution in production.
- **Redaction Scope**: Sensitive keys matching standard credential patterns (e.g., `password`, `token`, `secret`, `api_key`) are automatically masked with asterisks or redaction markers in log parameters.
- **Clock Synchronization**: Timestamps utilize local system time with standard ISO-8601 offset notation or UTC as configured.
