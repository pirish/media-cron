# Quickstart & Validation Guide: High-Speed OS-Native and Custom Utility File Transfers

**Feature**: `012-native-file-transfers`
**Date**: 2026-11-05

---

## Scenario 1: Default OS-Native (`cp` / `mv`) Acceleration (US1)

By default, `media-cron` uses `transfer.strategy: native`, invoking `cp -r --reflink=auto` for copies and `mv` for moves.

```bash
# Run media-cron in copy mode with default native strategy
uv run media-cron \
  --source /tmp/media-test/downloads \
  --dest /tmp/media-test/library \
  --mode copy \
  --transfer-strategy native \
  --json-logs
```

**Expected Verification**:
- Files and directories are copied via `cp -r --reflink=auto` (or `cp -r` if `--reflink` is unsupported).
- Structured logs emit `strategy=native`, `duration_ms`, and `throughput_mbps`.
- Batch summary JSON reports `"native_count": <N>, "fallback_count": 0`.

---

## Scenario 2: User-Specified Custom Transfer Command with Special Characters (US2)

Operators can specify custom commands using `{src}` and `{dst}` placeholders (or positional appending) via CLI, environment variables, or `config.yaml`:

```bash
# Create a media file with spaces, quotes, brackets, and ampersands
mkdir -p /tmp/media-test/downloads /tmp/media-test/library
dd if=/dev/zero of="/tmp/media-test/downloads/The Matrix (1999) [1080p] & Extras!.mkv" bs=1M count=10

# Execute using a custom copy command
uv run media-cron \
  --source /tmp/media-test/downloads \
  --dest /tmp/media-test/library \
  --mode copy \
  --transfer-strategy custom \
  --copy-cmd "cp -r {src} {dst}"
```

**Expected Verification**:
- Path arguments are passed directly via `subprocess.run(..., shell=False)` without shell splitting or injection.
- If a custom `--move-cmd` leaves the source file behind after exiting `0`, `media-cron` verifies the destination exists and matches the source byte size, then cleans up the remaining source path automatically.

---

## Scenario 3: Per-Destination Route Transfer Override (US2 / Clarifications Q1)

Configure `config.yaml` with a global `native` strategy and a custom override for a specific route destination:

```yaml
transfer:
  strategy: native
  fallback_enabled: true

routes:
  movie:
    enabled: true
    destination:
      path: /tmp/media-test/nas-movies
      mode: copy
      transfer:
        strategy: custom
        copy_command: "cp -r {src} {dst}"
```

**Expected Verification**:
- Movie transfers to `/tmp/media-test/nas-movies` use the route-specific `custom` command while all other routes and staging transfers use the global `native` strategy.

---

## Scenario 4: Automatic Built-In Fallback vs Disk Full (`ENOSPC`) Fast-Abort (US3 / Clarifications Q4)

```bash
# 1. Missing or failing custom tool automatically falls back to Python builtin (shutil)
uv run media-cron \
  --source /tmp/media-test/downloads \
  --dest /tmp/media-test/library \
  --mode copy \
  --transfer-strategy custom \
  --copy-cmd "nonexistent-transfer-tool {src} {dst}"
```

**Expected Verification**:
- Emits a `WARNING` log noting `nonexistent-transfer-tool` was not found, cleans up any partial target file, completes the transfer via `builtin` (`shutil`), and increments `transfer_summary.fallback_count`.
- Conversely, if the failure is due to insufficient destination disk space (`ENOSPC` / `"No space left on device"`), `media-cron` cleans up partial artifacts and aborts the transfer immediately without attempting the `builtin` fallback.

---

## Scenario 5: Dry-Run Telemetry Inspection (US1 / US4)

```bash
uv run media-cron \
  --source /tmp/media-test/downloads \
  --dest /tmp/media-test/library \
  --mode move \
  --transfer-strategy native \
  --dry-run
```

**Expected Verification**:
- Logs the planned `mv` / `cp` commands and strategy without spawning any external process or modifying the filesystem.

---

## Running the Automated Test Suite

```bash
uv run pytest tests/unit/test_transfer_models.py \
              tests/unit/test_transfer_executor.py \
              tests/contract/test_transfer_contracts.py \
              tests/integration/test_native_file_transfers.py -v
```
