# Feature Specification: Fast Failure Recovery and Transfer Resumption

**Feature Branch**: `011-resume-failed-transfers`

**Created**: 2026-10-15

**Status**: Ready

**Input**: User description: "If our staging or destination directory is not empty and files within those directories line up with our current queue of files, this can indicate that a previous run has failed. We should hash all of the source files and see if they match what is currently in our staging or destination directories. If the hashes of the files in the staging directory match our source, we should continue with those files rather than recopying. If hashes do not line up, we should delete the files/folders that line up with our queue and start from scratch."

## Clarifications

### Session 2026-10-15
- Q: Should the system perform an initial file size check before computing full content hashes to immediately detect incomplete or modified files? (FR-002) → A: Size-first fast rejection: compare file sizes first; if sizes differ, immediately treat as a mismatch and delete/re-copy without hashing.
- Q: When a destination file matches the source and the transfer step is bypassed, should the system still execute remaining post-transfer actions such as torrent seeding relocation or source cleanup? (FR-007) → A: Complete all post-transfer actions: mark destination transfer satisfied, then execute torrent seeding relocation and source cleanup (if mode is move) normally.
- Q: When an existing multi-file release directory in staging has mostly valid files but at least one corrupted or missing file, should the system purge the entire release directory and restart from scratch, or perform an incremental repair of only the invalid files? (FR-010) → A: Clean directory restart: purge the entire queued item folder in staging and re-copy all constituent files from scratch.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resume Ingestion from Matching Staged Files (Priority: P1) 🎯 MVP

An operator or automated cron job initiates a media intake run after a previous run was aborted or encountered an unhandled failure midway through copying large files into the staging area. The system detects that existing files or directories in the staging directory correspond to items in the current processing queue. The system verifies the content integrity of these items against their source files using cryptographic content hashes. Because the hashes match, the system skips re-copying the data, immediately reuses the existing staged files, and proceeds directly to downstream organization, drastically reducing execution time and disk I/O.

**Why this priority**: Core value driver. Eliminates redundant, time-consuming file copy operations when previous runs staged data successfully before failing in later stages.

**Independent Test**: Place a large media payload in the source directory, pre-stage an identical copy in the staging area, and trigger the intake process. Verify that the system validates the content hash, logs that re-copying is skipped, leaves the staged file intact, and moves directly to media planning without rewriting the payload.

**Acceptance Scenarios**:

1. **Given** a queued media item at the source and an existing file with the identical name and relative path in the staging directory, **When** the content hashes of the source and staged file match, **Then** the system bypasses re-copying and marks the staged item as ready for subsequent pipeline stages.
2. **Given** a multi-file media release (such as an album or multi-file video pack) partially or fully staged, **When** all files in the release match their respective source files by content hash, **Then** the entire release directory in staging is retained and re-ingestion is skipped.
3. **Given** a dry-run execution with matching files already in staging, **When** the inspection runs, **Then** the system reports that existing staged files match the source and would be reused without re-copying.

---

### User Story 2 - Clean Purge and Restart on Corrupted or Incomplete Staged Files (Priority: P2)

A previous run was killed or failed midway through writing a large file or directory into the staging area, leaving a truncated, partial, or corrupted file in the staging directory. When the pipeline runs again, it compares the content hashes between the source files and the existing staged files. Detecting a hash mismatch, the system safely deletes the corrupted or incomplete files/folders associated with that queued item and restarts the transfer cleanly from scratch.

**Why this priority**: Prevents silent corruption and downstream pipeline failures caused by partial file transfers from interrupted executions.

**Independent Test**: Place a valid media file in the source directory and create a truncated/corrupted version with the same name in the staging directory. Execute the pipeline; verify that the system detects the hash mismatch, removes the corrupt staged file, copies a fresh copy from the source, and verifies the new copy.

**Acceptance Scenarios**:

1. **Given** an existing file in staging matching a queued item name whose content hash differs from the source file (e.g., partial or modified content), **When** the verification runs, **Then** the system deletes the mismatched staged file and performs a clean copy from the source.
2. **Given** an existing directory in staging for a multi-file queued item where one or more files are missing or have mismatched content hashes, **When** verification occurs, **Then** the system purges the entire invalid directory in staging for that item and re-copies the complete item from the source.
3. **Given** a dry-run execution with corrupted files in staging, **When** the inspection runs, **Then** the system flags the hash mismatch and reports that the staged item would be deleted and re-copied, without altering the filesystem.

---

### User Story 3 - Bypass Redundant Transfers for Already-Organized Destination Files (Priority: P3)

A previous execution succeeded in transferring organized media to the target destination library or drop spool, but failed immediately afterward (for example, during torrent client seeding relocation, notification dispatch, or lock release). On the subsequent run, the system checks whether the destination target already contains files matching the source item's content hash. Upon confirming an identical hash match at the destination, the system skips writing to the destination again and advances directly to remaining post-transfer tasks (such as torrent client relocation, source cleanup, or library notifications).

**Why this priority**: Ensures end-to-end recovery across all phases of the pipeline, preventing duplicate writes, false overwrite conflicts, or unnecessary file transfers when a failure occurs near the end of a run.

**Independent Test**: Place a media item in the source queue and ensure an identical matching file exists at the calculated target destination path. Run the pipeline; verify that the transfer step is recorded as already satisfied, no duplicate copy is performed, and any remaining post-transfer operations (e.g., updating torrent seeding state) proceed successfully.

**Acceptance Scenarios**:

1. **Given** a queued media item whose calculated destination path already exists and possesses an identical content hash, **When** transfer planning and execution take place, **Then** the system records the destination file as valid, bypasses transferring data to destination, and completes remaining post-transfer tasks.
2. **Given** a dry-run execution where the destination already contains matching content, **When** planning executes, **Then** the system reports that the destination file already exists with matching content hash and that transfer will be bypassed.

---

### User Story 4 - Purge and Re-transfer Corrupted Destination Files (Priority: P4)

An interrupted previous run left a partial or corrupted file at the target destination path. When the subsequent run checks the destination target against the source item, the content hashes do not match. The system removes the invalid file at the destination and re-executes the transfer from scratch to guarantee destination integrity.

**Why this priority**: Protects media library integrity by ensuring corrupted destination artifacts left by crashes or failed disk writes are never left in place or treated as valid media assets.

**Independent Test**: Place a corrupted/truncated media file at the target destination location and execute the organization pipeline with the valid source item. Verify that the invalid destination file is removed and replaced with the verified source payload.

**Acceptance Scenarios**:

1. **Given** an existing destination file whose content hash does not match the source media item, **When** the transfer step is evaluated, **Then** the system removes the invalid destination file and executes a fresh transfer from the verified source or staging asset.
2. **Given** a destination file that cannot be removed due to unexpected locks or permission restrictions, **When** deletion fails, **Then** the system logs a descriptive operational error, halts processing for that specific item to prevent data loss, and marks the item result as failed.

---

### User Story 5 - Observability and Recovery Telemetry (Priority: P5)

An operator monitoring automated jobs through console logs or log aggregators needs clear visibility into recovery events. The operator can see whether existing items in staging or destination were detected, the duration and results of hash comparisons, the number of bytes saved by resuming instead of re-copying, and clear audit records of any purged partial files.

**Why this priority**: Provides essential diagnosability and observability into automated recovery decisions, verifying that the system is operating safely and quantifying performance savings.

**Independent Test**: Run a batch containing both resumable items and mismatched items; inspect structured logs and summary output to verify that recovery decisions, byte savings, and purge actions are explicitly recorded.

**Acceptance Scenarios**:

1. **Given** an execution that resumes processing from existing staged files, **When** the batch completes, **Then** the execution summary and logs report the count of resumed items and the total volume of data skipped from re-copying.
2. **Given** an execution that purges invalid files due to hash mismatch, **When** purges occur, **Then** the system emits warning-level log records identifying the exact purged paths and the reason for deletion.
3. **Given** an unconfigured or standard run, **When** hash verification is in progress for large files, **Then** informational progress logs prevent the appearance of an unresponsive or frozen process.

---

### Edge Cases

- **Unrelated Files in Staging/Destination**: What happens when staging or destination directories contain files or subfolders that do not correspond to any item in the current queue? The system MUST NOT delete or touch files that do not correspond to current queue items, preserving external files or assets from other unrelated workflows.
- **Empty (0-Byte) Files**: What happens when a previous crash left a 0-byte file in staging or destination? The 0-byte file will fail hash comparison against non-empty source files and MUST be deleted and recreated. If the source file itself is legitimately 0 bytes, hashes match and the file is accepted.
- **Source File Modified During Verification**: What happens if the source file is modified or actively downloading while hash verification is performed? If the source file size or content changes during verification, the verification MUST fail, the staging candidate MUST be discarded, and the item MUST be deferred or flagged as unstable.
- **Permission Errors During Purge**: What happens if the process has insufficient filesystem permissions to delete a corrupted staging or destination artifact? The system MUST log an explicit error, avoid proceeding with a dirty target, mark the specific item as failed, and proceed with other queued items without crashing.
- **Hardlink and Same-Inode Detection**: What happens if a destination file shares the same filesystem inode as the source file (e.g. existing hardlink)? Same-inode files are by definition identical; the system can immediately confirm match without full hash calculation overhead.
- **Insufficient Disk Space**: What happens if disk space is exhausted before or after a purge? The system validates available space prior to copying, ensuring that purging corrupt artifacts frees necessary space before fresh copies are attempted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST inspect the configured staging directory prior to initiating file transfers from the source, identifying any existing files or directories whose paths match items in the current processing queue.
- **FR-002**: When an item matching a queued source item is found in the staging directory, the system MUST perform an initial file size comparison; if sizes differ, the system MUST immediately treat the item as a mismatch without computing hashes. If sizes match, the system MUST compute and compare the content hashes of the source files and the corresponding staged files.
- **FR-003**: If all files for a queued item in the staging directory match the source item's content hashes, the system MUST retain the staged files, skip copying from the source, and advance the item directly to subsequent pipeline stages (identification and planning).
- **FR-004**: If any file for a queued item in the staging directory does not match the corresponding source file's content hash, or if the staged item is incomplete, the system MUST delete the invalid staged files/directories associated with that queued item and perform a fresh copy from the source.
- **FR-005**: The system MUST inspect the calculated target destination path before executing transfer operations (copy, move, hardlink).
- **FR-006**: When an existing file or directory exists at the target destination path, the system MUST perform an initial file size comparison; if sizes differ, the system MUST immediately treat the item as a mismatch without computing hashes. If sizes match, the system MUST verify whether its content hash matches the source file.
- **FR-007**: If the destination file matches the source item's content hash, the system MUST mark the destination transfer as satisfied, bypass writing data to the destination, and execute all configured post-transfer actions (including torrent client seeding relocation, source cleanup when operating in move mode, and notification dispatch).
- **FR-008**: If an existing destination file does not match the source item's content hash, the system MUST remove the invalid destination file prior to initiating the fresh transfer.
- **FR-009**: The system MUST strictly confine deletion operations to files and directories that correspond directly to items in the active queue, and MUST NOT modify or delete unrelated files found in staging or destination.
- **FR-010**: For multi-file media releases (such as directories containing multiple tracks or video files), hash verification MUST evaluate all constituent files; the item is resumed only if 100% of constituent files match, and the entire queued item directory in staging MUST be purged and re-copied from scratch if any constituent file fails, is corrupted, or is missing.
- **FR-011**: In dry-run mode, the system MUST perform verification checks and report all detected matches, planned bypasses, and scheduled purges without deleting, moving, or writing any files on disk.
- **FR-012**: The system MUST emit structured telemetry and log records detailing verification outcomes, including number of items resumed, number of corrupted items purged, and total data transfer volume avoided.

### Key Entities *(include if feature involves data)*

- **Queued Media Item**: A file or multi-file release package detected at a source location awaiting intake, organization, or transfer.
- **Staged Media Item**: A temporary replica of a queued item residing in the staging directory prior to identification and library placement.
- **Destination Media Target**: The resolved target path in the media library or spool directory where an organized media asset is placed.
- **Verification State**: The computed integrity status of an existing candidate file or directory relative to its source (`MATCH`, `MISMATCH`, `MISSING`, `CORRUPTED`), determining whether to resume or purge.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of redundant data transfer bytes are eliminated when identical matching files already exist in staging or destination directories.
- **SC-002**: 100% of partial, truncated, or corrupted staging and destination artifacts corresponding to queued items are purged and replaced with intact verified copies.
- **SC-003**: Resuming an interrupted batch with pre-staged files reduces pipeline intake duration by at least 80% compared to a clean intake for multi-gigabyte files.
- **SC-004**: 0% of unrelated or unqueued files residing in staging or destination directories are deleted or modified during recovery.
- **SC-005**: 100% of recovery and cleanup actions executed in live mode are accurately reported in dry-run mode without modifying filesystem state.

## Assumptions

- Source files remain static and immutable during the verification and transfer lifecycle (e.g., downloads have been marked complete by the upstream source or torrent client).
- The host filesystem supports standard file reading, size querying, and deletion operations with appropriate read/write permissions for the media-cron process.
- Cryptographic content hash algorithms (such as standard secure digests) provide sufficient collision resistance to guarantee file equivalence without needing byte-by-byte visual diffing.
- Fast-path verification (such as matching filesystem inode or file size preliminary checks) may precede full hash verification to optimize performance when files are identical hardlinks.
- Existing downstream post-transfer operations (e.g., moving completed torrents to seeding directories or updating external services) are safe to execute when a destination transfer is resumed.
