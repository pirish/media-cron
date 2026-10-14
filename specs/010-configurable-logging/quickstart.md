# Quickstart Validation Guide: Configurable Logging Subsystem

**Branch**: `010-configurable-logging` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

---

## Prerequisites & Setup

Ensure the test environment is active and dependencies are installed:

```bash
# In media-cron project root
source .venv/bin/activate
mkdir -p /tmp/media-cron-test/src /tmp/media-cron-test/dest
```

---

## Scenario 1: Default Out-of-the-Box Console Logging

**Goal**: Verify that running any media-cron command without logging arguments defaults to `INFO` level output sent to `stderr`, while `stdout` remains clean for command payloads.

### Run Command
```bash
media-cron run --dry-run --source /tmp/media-cron-test/src --destination /tmp/media-cron-test/dest
```

### Verification & Expected Outcome
- **Standard Error (`stderr`)**: Contains formatted `[INFO]` log entries showing pipeline startup, source scanning, and completion summary with ISO timestamps:
  ```text
  2026-10-14 12:00:00 [INFO] media_cron.pipeline: Initializing media organization pipeline (dry_run=True)
  2026-10-14 12:00:00 [INFO] media_cron.pipeline: Ingestion scan completed: 0 items discovered
  ```
- **Standard Output (`stdout`)**: Contains the human-readable text batch summary or empty output, completely free of log lines.
- **Piping Verification**:
  ```bash
  # Standard output can be piped cleanly without log pollution
  media-cron run --dry-run --json --source /tmp/media-cron-test/src --destination /tmp/media-cron-test/dest 2>/dev/null | jq .exit_code
  # Expected stdout: 0
  ```

---

## Scenario 2: Increasing Verbosity for Troubleshooting (`--verbose`)

**Goal**: Verify that providing `-v` / `--verbose` or `--log-level debug` exposes granular internal diagnostics (e.g., skip reasons, file evaluation details).

### Run Command
```bash
media-cron run --dry-run -v --source /tmp/media-cron-test/src --destination /tmp/media-cron-test/dest
```

### Verification & Expected Outcome
- **Standard Error (`stderr`)**: Displays granular `[DEBUG]` entries alongside `[INFO]` entries:
  ```text
  2026-10-14 12:00:01 [DEBUG] media_cron.config: Active configuration resolved
  2026-10-14 12:00:01 [DEBUG] media_cron.pipeline: Evaluating file candidates in /tmp/media-cron-test/src
  2026-10-14 12:00:01 [INFO] media_cron.pipeline: Ingestion scan completed
  ```
- **Exit Code**: `0`.

---

## Scenario 3: Persistent File Logging with Auto-Directory Creation

**Goal**: Verify that specifying a log file path in a non-existent subdirectory automatically creates the folder hierarchy and logs exclusively to the file, silencing routine console output.

### Run Command
```bash
LOG_TARGET="/tmp/media-cron-test/nested/logs/execution.log"
rm -rf /tmp/media-cron-test/nested

media-cron run --dry-run \
  --log-file "$LOG_TARGET" \
  --source /tmp/media-cron-test/src \
  --destination /tmp/media-cron-test/dest
```

### Verification & Expected Outcome
- **Directory & File Creation**: `/tmp/media-cron-test/nested/logs/` is automatically created, and `execution.log` exists.
- **Standard Error (`stderr`)**: Completely silent during successful run (routine console output suppressed).
- **Log File Content**:
  ```bash
  cat "$LOG_TARGET"
  ```
  File contains all `[INFO]` log entries from the execution.

---

## Scenario 4: Dual Logging (File + Console Mirroring)

**Goal**: Verify that setting destination to `both` (or passing `--console` alongside `--log-file`) mirrors log entries to both the file and terminal `stderr`.

### Run Command
```bash
LOG_TARGET="/tmp/media-cron-test/dual.log"

media-cron run --dry-run \
  --log-file "$LOG_TARGET" \
  --console \
  --source /tmp/media-cron-test/src \
  --destination /tmp/media-cron-test/dest
```

### Verification & Expected Outcome
- **Standard Error (`stderr`)**: Emits formatted log entries directly to the terminal.
- **Log File Content**: The identical log entries are appended to `/tmp/media-cron-test/dual.log`.

---

## Scenario 5: Machine-Readable JSON Logging & Credential Redaction

**Goal**: Verify that setting `--log-format json` produces single-line JSON records compliant with the schema, and sensitive values (e.g., passwords or tokens) are masked.

### Run Command
```bash
# Execute with JSON logging format and test client authentication failure
MEDIA_CRON_QBITTORRENT_PASSWORD="SuperSecretPassword123" \
media-cron run --dry-run \
  --log-format json \
  --torrent-client qbittorrent \
  --source /tmp/media-cron-test/src \
  --destination /tmp/media-cron-test/dest 2>/tmp/media-cron-test/stderr_json.log
```

### Verification & Expected Outcome
- **Single-Line JSON Schema**: Every line in `/tmp/media-cron-test/stderr_json.log` is a valid JSON document conforming to [json-log-schema.md](contracts/json-log-schema.md):
  ```bash
  jq -c '{timestamp: .timestamp, level: .level, logger: .logger, message: .message}' /tmp/media-cron-test/stderr_json.log
  ```
- **Credential Redaction**: Verify that sensitive passwords do NOT appear in the logs:
  ```bash
  grep "SuperSecretPassword123" /tmp/media-cron-test/stderr_json.log || echo "PASS: Password redacted"
  ```
  Output must show `PASS: Password redacted`.
