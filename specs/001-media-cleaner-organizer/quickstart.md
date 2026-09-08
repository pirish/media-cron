# Quickstart Validation Guide: Media-Cron

This guide outlines runnable scenarios to validate the feature end-to-end against the [Data Model](data-model.md) and [Contracts](contracts/cli-interface.md).

---

## 1. Prerequisites

- Python 3.11+ installed
- Virtual environment created and activated
- Package dependencies installed:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -e ".[dev]"
  ```

---

## 2. Validation Scenarios

### Scenario A: Dry-Run Simulation (Zero Disk Modifications)

**Objective**: Verify that `--dry-run` accurately detects all operations without writing, moving, or deleting any files.

1. **Setup Test Staging Environment**:
   ```bash
   mkdir -p /tmp/mc-test/downloads/Movie.Sample.2024.1080p-GROUP
   mkdir -p /tmp/mc-test/staging
   mkdir -p /tmp/mc-test/library
   touch /tmp/mc-test/downloads/Movie.Sample.2024.1080p-GROUP/movie.mkv
   touch /tmp/mc-test/downloads/Movie.Sample.2024.1080p-GROUP/movie.en.srt
   touch /tmp/mc-test/downloads/Movie.Sample.2024.1080p-GROUP/sample.mp4
   touch /tmp/mc-test/downloads/Movie.Sample.2024.1080p-GROUP/release.nfo
   ```

2. **Run Dry-Run Command**:
   ```bash
   media-cron organize \
     --source /tmp/mc-test/downloads \
     --staging /tmp/mc-test/staging \
     --destination /tmp/mc-test/library \
     --dry-run \
     --format json
   ```

3. **Expected Outcome**:
   - Exit code `0`.
   - Output JSON specifies planned actions:
     - `movie.mkv` → `Movies/Movie Sample (2024)/Movie Sample (2024).mkv`
     - `movie.en.srt` → `Movies/Movie Sample (2024)/Movie Sample (2024).en.srt`
     - `sample.mp4` → `PURGE_SAMPLE`
     - `release.nfo` → `PURGE_JUNK`
   - All files in `/tmp/mc-test/downloads/` remain completely untouched.

---

### Scenario B: Live Pipeline Execution with Seeding & Staging

**Objective**: Verify staging directory isolation and seed directory relocation.

1. **Setup Environment**:
   ```bash
   mkdir -p /tmp/mc-test/seed
   ```

2. **Run Live Command**:
   ```bash
   media-cron organize \
     --source /tmp/mc-test/downloads \
     --staging /tmp/mc-test/staging \
     --destination /tmp/mc-test/library \
     --seed-dir /tmp/mc-test/seed \
     --mode hardlink
   ```

3. **Expected Outcome**:
   - Destination library contains:
     `/tmp/mc-test/library/Movies/Movie Sample (2024)/Movie Sample (2024).mkv`
     `/tmp/mc-test/library/Movies/Movie Sample (2024)/Movie Sample (2024).en.srt`
   - Seed directory contains original files preserved for seeding:
     `/tmp/mc-test/seed/Movie.Sample.2024.1080p-GROUP/movie.mkv`
   - Junk (`release.nfo`) and sample (`sample.mp4`) are removed.
   - Files share the same inode number (hardlinked, not duplicated).

---

### Scenario C: Concurrency Lock Contention

**Objective**: Verify that overlapping runs exit immediately without modifying files or causing race conditions.

1. **Acquire Lockfile Manually in Staging**:
   ```bash
   python -c "import fcntl, time, sys; f=open('/tmp/mc-test/staging/.media-cron.lock', 'w'); fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); time.sleep(15)" &
   ```

2. **Attempt Simultaneous Execution**:
   ```bash
   media-cron organize \
     --source /tmp/mc-test/downloads \
     --staging /tmp/mc-test/staging \
     --destination /tmp/mc-test/library
   ```

3. **Expected Outcome**:
   - Process outputs concurrency warning: `Staging directory is currently locked by another process.`
   - Exits immediately with exit code `1`.
   - Zero file operations performed.

---

## 3. Automated Verification Commands

Run full contract, integration, and unit tests:
```bash
pytest -v tests/unit
pytest -v tests/contract
pytest -v tests/integration
```
