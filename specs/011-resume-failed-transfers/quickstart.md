# Quickstart Validation Guide: Fast Failure Recovery and Transfer Resumption

**Branch**: `011-resume-failed-transfers`
**Date**: 2026-10-15
**Spec Reference**: [spec.md](spec.md) | **Contracts**: [recovery-protocol.md](contracts/recovery-protocol.md)

---

## Prerequisites & Test Environment Setup

Activate the virtual environment and initialize isolated temporary test directories:

```bash
# In media-cron project root
source .venv/bin/activate

# Setup clean test sandbox
export TEST_BASE="/tmp/media-cron-recovery-test"
rm -rf "$TEST_BASE"
mkdir -p "$TEST_BASE/src" "$TEST_BASE/staging" "$TEST_BASE/dest"
```

---

## Scenario 1: Fast Resume from Matching Staging Payload (User Story 1 - P1)

**Goal**: Verify that an interrupted run leaving a complete, valid file in staging is recognized, hashes verified, and physical re-copying is completely skipped.

### Step 1: Create Source and Pre-Staged Payloads
```bash
# Create a 20MB test media file
dd if=/dev/urandom of="$TEST_BASE/src/Test.Movie.2026.1080p.mkv" bs=1M count=20 status=none

# Pre-stage an identical copy in staging (simulating a previous run that staged the file before crashing)
cp "$TEST_BASE/src/Test.Movie.2026.1080p.mkv" "$TEST_BASE/staging/Test.Movie.2026.1080p.mkv"
```

### Step 2: Run Media-Cron
```bash
media-cron run \
  --source "$TEST_BASE/src" \
  --staging "$TEST_BASE/staging" \
  --destination "$TEST_BASE/dest"
```

### Verification & Expected Outcome
- **Logs (`stderr`)**: Shows the staging candidate was inspected, file sizes and SHA-256 hashes matched, and re-copying was bypassed:
  ```text
  [INFO] media_cron.recovery: Staged item 'Test.Movie.2026.1080p.mkv' verified matching; resuming without re-copying (20971520 bytes saved)
  ```
- **Telemetry (`stdout`)**:
  - `Staged Resumed: 1`
  - `Data Transfer Saved: 20.00 MB`
- **Filesystem**: The pre-staged file is processed and organized to the destination library without re-reading the source.

---

## Scenario 2: Detection and Clean Purge of Corrupt Staging Artifact (User Story 2 - P2)

**Goal**: Verify that a truncated or corrupted file left in staging is rejected via size-first fast check, safely purged, and cleanly copied from scratch.

### Step 1: Create Corrupted Staging Candidate
```bash
# Clean directories
rm -rf "$TEST_BASE/staging/*" "$TEST_BASE/dest/*"

# Create valid 20MB source file
dd if=/dev/urandom of="$TEST_BASE/src/Corrupt.Sample.2026.mkv" bs=1M count=20 status=none

# Create a truncated 5MB partial copy in staging (simulating a write interrupted midway)
dd if="$TEST_BASE/src/Corrupt.Sample.2026.mkv" of="$TEST_BASE/staging/Corrupt.Sample.2026.mkv" bs=1M count=5 status=none
```

### Step 2: Run Media-Cron
```bash
media-cron run \
  --source "$TEST_BASE/src" \
  --staging "$TEST_BASE/staging" \
  --destination "$TEST_BASE/dest"
```

### Verification & Expected Outcome
- **Logs (`stderr`)**: Shows size mismatch detected instantly, invalid staging artifact purged, and clean copy performed:
  ```text
  [WARNING] media_cron.recovery: Corrupted candidate '.../staging/Corrupt.Sample.2026.mkv' rejected by file size (5242880 != 20971520); purging and restarting
  [INFO] media_cron.recovery: Purged invalid candidate '.../staging/Corrupt.Sample.2026.mkv' prior to clean restart
  ```
- **Telemetry (`stdout`)**:
  - `Corrupt Purged: 1`
- **Destination Verification**: The final destination file is exactly 20,971,520 bytes and its SHA-256 hash matches the source file.

---

## Scenario 3: Destination Transfer Bypass with Full Post-Transfer Execution (User Story 3 - P3)

**Goal**: Verify that when the destination file already exists with matching content hash, transfer is bypassed and post-transfer operations (e.g. source cleanup in move mode) are executed normally.

### Step 1: Setup Existing Matching File at Destination
```bash
rm -rf "$TEST_BASE/staging/*" "$TEST_BASE/dest/*"
mkdir -p "$TEST_BASE/dest/Test Movie (2026)"

# Place identical payload at destination
cp "$TEST_BASE/src/Test.Movie.2026.1080p.mkv" "$TEST_BASE/dest/Test Movie (2026)/Test Movie (2026).mkv"
```

### Step 2: Run Media-Cron
```bash
media-cron run \
  --source "$TEST_BASE/src" \
  --staging "$TEST_BASE/staging" \
  --destination "$TEST_BASE/dest"
```

### Verification & Expected Outcome
- **Logs (`stderr`)**:
  ```text
  [INFO] media_cron.recovery: Destination file '.../Test Movie (2026).mkv' verified matching; bypassing transfer and completing post-transfer lifecycle
  ```
- **Telemetry (`stdout`)**:
  - `Destination Bypassed: 1`
  - `Data Transfer Saved: 20.00 MB`

---

## Scenario 4: Corrupt Destination Artifact Purge and Replacement (User Story 4 - P4)

**Goal**: Verify that a corrupted destination file left by a previous crash is safely removed and replaced with a verified intact transfer.

### Step 1: Setup Corrupt Destination File
```bash
# Overwrite destination file with 1MB corrupt content
dd if=/dev/urandom of="$TEST_BASE/dest/Test Movie (2026)/Test Movie (2026).mkv" bs=1M count=1 status=none
```

### Step 2: Run Media-Cron
```bash
media-cron run \
  --source "$TEST_BASE/src" \
  --staging "$TEST_BASE/staging" \
  --destination "$TEST_BASE/dest"
```

### Verification & Expected Outcome
- **Logs (`stderr`)**:
  ```text
  [WARNING] media_cron.recovery: Corrupted candidate '.../Test Movie (2026).mkv' rejected by file size (1048576 != 20971520); purging and restarting
  [INFO] media_cron.recovery: Purged invalid candidate '.../Test Movie (2026).mkv' prior to clean restart
  ```
- **Filesystem Verification**: Destination file is replaced with the full 20MB verified source file.

---

## Scenario 5: Dry-Run Visibility and Non-Destructive Simulation (User Story 5 - P5)

**Goal**: Verify that `--dry-run` accurately evaluates staging and destination recovery decisions without mutating any disk state.

### Step 1: Setup Mixed Staging State
```bash
# Leave 1MB corrupt file in destination
dd if=/dev/urandom of="$TEST_BASE/dest/Test Movie (2026)/Test Movie (2026).mkv" bs=1M count=1 status=none
```

### Step 2: Run Dry-Run
```bash
media-cron run --dry-run \
  --source "$TEST_BASE/src" \
  --staging "$TEST_BASE/staging" \
  --destination "$TEST_BASE/dest"
```

### Verification & Expected Outcome
- **Logs (`stderr`)**: Shows planned purge and restart with `[DRY-RUN]` prefix:
  ```text
  [INFO] media_cron.recovery: [DRY-RUN] Would purge corrupt candidate '.../Test Movie (2026).mkv' and restart transfer
  ```
- **Filesystem Verification**: The 1MB destination file is **not** deleted and remains untouched on disk.
- **Exit Code**: `0`.
