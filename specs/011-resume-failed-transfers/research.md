# Research & Technical Decisions: Fast Failure Recovery and Transfer Resumption

**Feature Branch**: `011-resume-failed-transfers`
**Date**: 2026-10-15
**Spec Reference**: [spec.md](spec.md)

---

## 1. Hashing Algorithm & File Streaming Architecture

### Decision
Use Python's standard library `hashlib.sha256()` with a 1MB (1,048,576 bytes) read buffer chunk size, executed through a streaming generator that updates the hash digest incrementally.

### Rationale
- **Zero New Dependencies**: `hashlib` is built directly into Python 3.11+, maintaining strict compliance with Media-Cron Constitution Principle I (Library-First) and Principle V (Container-Native & Environment Isolation).
- **Constant Memory Footprint**: Streaming in 1MB chunks bounds memory consumption to <2MB resident RAM regardless of media file size (essential for handling 40GB+ 4K UHD video remuxes).
- **I/O Efficiency**: A 1MB chunk size provides optimal sequential disk throughput across modern NVMe SSDs, SATA SSDs, and spinning HDD arrays (ZFS, ext4, Btrfs), outperforming smaller 4KB/64KB buffers while avoiding the kernel context switching overhead of micro-reads.
- **Cryptographic Collision Resistance**: SHA-256 completely eliminates practical risk of hash collisions across millions of media files.

### Alternatives Considered
- **MD5 / CRC32**: While computationally faster, MD5 has known collision vulnerabilities and CRC32 is prone to accidental collisions on large media payloads.
- **xxHash / BLAKE3**: While offering higher CPU throughput on multi-gigabyte files, both require external third-party compiled C extensions (`xxhash` or `blake3` via PyPI), introducing packaging and platform compatibility burdens for container builds without proportional benefit (since file transfers are I/O bound, not CPU bound).
- **Full File In-Memory Reading (`f.read()`)**: Causes immediate Out-Of-Memory (OOM) fatal crashes when reading multi-gigabyte media files.

---

## 2. Multi-Stage Integrity Verification Pipeline

### Decision
Implement a three-stage short-circuit verification pipeline inside `TransferVerifier`:
1. **Same-Inode Short-Circuit**: If `target.stat().st_ino == source.stat().st_ino` and `target.stat().st_dev == source.stat().st_dev` (identical filesystem inode/device), immediately declare `MATCH` without reading data.
2. **Size-First Fast Rejection**: Compare `target.stat().st_size` against `source.stat().st_size`. If file sizes differ by even a single byte, immediately return `MISMATCH` without computing hashes.
3. **Full Content Hash Verification**: Only when file sizes match, stream both files through SHA-256 and compare digests.

### Rationale
- **Instantaneous Metadata Lookup**: Querying `stat()` metadata is an $O(1)$ filesystem operation taking microseconds.
- **Elimination of Wasted Read I/O**: Most aborted or crashed file operations leave partially written, truncated files. By rejecting size mismatches instantly, the system avoids reading tens of gigabytes of doomed data before purging and restarting.
- **Hardlink Optimization**: In environments utilizing hardlinks (`TransferMode.HARDLINK`), source and destination files share inodes, enabling zero-I/O verification.

### Alternatives Considered
- **Immediate Hash Calculation**: Computes SHA-256 over both files unconditionally. Rejected because hashing a truncated 30GB file wastes minutes of disk I/O when the size check alone proves mismatch in microseconds.
- **Size-Only Verification**: Comparing only file sizes without hashing. Rejected because it fails to detect bit-rot, corruption, or partially overwritten files that happen to match target size.

---

## 3. Modular Architecture: `media_cron.recovery` Package

### Decision
Encapsulate all recovery, hashing, and safe cleanup logic in a dedicated module: `media_cron/recovery/`:
- `media_cron/recovery/models.py`: Data models (`VerificationStatus`, `VerificationResult`, `FileIntegrityRecord`, `RecoverySummary`).
- `media_cron/recovery/protocols.py`: Formal protocol contract (`TransferVerifierProtocol`).
- `media_cron/recovery/verifier.py`: Concrete `TransferVerifier` implementation providing `verify_file()`, `verify_directory()`, `purge_item()`, and `compute_hash()`.

### Rationale
- **Adherence to Constitution Principle I (Library-First)**: Decouples integrity verification and recovery decisions from schedulers, CLI entrypoints, and specific input plugins.
- **Testability (Constitution Principle II)**: Allows extensive unit and contract testing with mock filesystem directories before wiring into pipeline and plugin layers.
- **Shared Code Across Pipeline Phases**: Both input staging (`TorrentInputPlugin`, `DirectoryScannerInputPlugin`) and output library organization (`LibraryOrganizerOutput`) invoke the identical verification contracts.

### Alternatives Considered
- **Embedding Recovery in Pipeline (`pipeline.py`)**: Monolithic, bloats `pipeline.py` (which is already ~1,400 lines), and makes independent unit testing difficult.
- **Embedding in Input Plugins Directly**: Duplicates verification logic across `torrent.py`, `directory.py`, and `organizer.py`.

---

## 4. Destination Transfer Bypass & Post-Transfer Lifecycle

### Decision
When an output organizer evaluates a destination path and discovers an existing file matching the source content hash:
1. Return `OperationResult` with `OperationStatus.SUCCESS`, `op_type=OperationType.ORGANIZE` (or `OperationType.UPGRADE_REPLACE`), and set message/metadata indicating `transfers_bypassed=True`.
2. Pipeline loop recognizes this successful outcome and executes all configured post-transfer actions:
   - Client seeding relocation (`TorrentClientSeedOutput` moving payload to `seed_dir`).
   - Source file cleanup if running in move mode (`TransferMode.MOVE`).
   - Downstream media server rescan notifications (Plex, Jellyfin, etc.).

### Rationale
- **Satisfies Clarified FR-007**: When a prior execution copied the destination file but crashed before torrent relocation or notification, re-running the pipeline must recognize the valid destination file and complete the lifecycle idempotently.
- **Prevents Infinite Retries**: If skipped operations did not trigger seeding relocation, the completed torrent would remain in active download queues indefinitely, repeatedly triggering re-runs.

### Alternatives Considered
- **Treating Match as `OperationStatus.SKIPPED`**: Existing pipeline logic treats `SKIPPED` as non-actionable and skips torrent relocation and cleanup, leaving unfinished torrents in limbo.
- **Unconditionally Overwriting Destination**: Causes destructive rewrites, file churn, and unnecessary wear on storage media.

---

## 5. Multi-File Release Directory Atomic Verification & Purge Strategy

### Decision
For multi-file releases (such as music albums, multi-disc audiobook sets, or multi-episode packs):
1. The verifier enumerates all source files and expects identical relative paths, sizes, and hashes in the candidate staging directory.
2. If **any** constituent file is missing, size-mismatched, or hash-mismatched, the entire candidate item directory in staging is marked `MISMATCH`.
3. In live mode, `verifier.purge_item(candidate_path)` safely removes the entire queued item folder using `shutil.rmtree()`, and the input plugin copies the entire release from scratch.
4. In dry-run mode, the purge and re-copy are logged with `[DRY-RUN]` without modifying filesystem state.

### Rationale
- **Satisfies Clarified FR-010**: Guarantees atomic release consistency. Partial directory transfers can leave orphan tracks, missing cover art, or corrupt subtitle sidecars that break metadata lookups and media server scrapers.
- **Simplicity & Predictability**: Cleaning the directory and starting fresh avoids edge cases with partial file overwrites or stale leftover files from previous crashed attempts.

### Alternatives Considered
- **Incremental File-by-File Repair**: Retaining valid files and copying only missing files. Rejected during clarification because it risks leaving stale files from older release revisions and complicates atomic rollback.

---

## 6. Safety Bounds & Path Traversal Prevention

### Decision
All file purge operations in `TransferVerifier.purge_item()` enforce strict containment checks:
1. Candidate path must be strictly located within `staging_dir` or the resolved `destination_path`.
2. Candidate path cannot equal `staging_dir`, destination root, or filesystem root (`/`).
3. Candidate path cannot contain `..` path traversal sequences.
4. Violations raise an explicit `SecurityViolationError` or `ValueError` and halt execution for that item without deleting anything.

### Rationale
- **Adherence to Constitution Principle III**: Non-destructive safety by default. Guarantees that accidental path misconfigurations or malformed queue inputs never delete external system directories or user data.

---

## 7. Structured Observability & Telemetry

### Decision
Add a `RecoverySummary` tracking object to `media_cron.pipeline` and `BatchSummary`:
- `items_resumed`: Count of queued items whose staging copy was validated and reused.
- `transfers_bypassed`: Count of items whose destination file was validated and write was bypassed.
- `items_purged`: Count of corrupted/incomplete candidate files or directories safely purged.
- `bytes_saved`: Total byte count of files whose physical transfer was avoided.

Emit clear log messages at each event:
- `INFO`: `"Resuming staged item '%s' (hash verified, %s bytes saved)"`
- `INFO`: `"Destination file '%s' verified matching; bypassing transfer and completing post-transfer lifecycle"`
- `WARNING`: `"Corrupted candidate '%s' detected (size/hash mismatch); safely purging and restarting transfer"`
- `INFO`: `"[DRY-RUN] Would resume '%s' from staging (%s bytes saved)"`

### Rationale
- Satisfies FR-012, SC-001, SC-003, and Constitution Principle IV. Provides operators with immediate visibility into recovery savings and audit trails of any deleted corrupt files.
