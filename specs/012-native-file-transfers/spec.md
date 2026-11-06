# Feature Specification: High-Speed OS-Native and Custom Utility File Transfers

**Feature Branch**: `012-native-file-transfers`
**Created**: 2026-11-05
**Status**: Draft
**Input**: User description: "**problem** transferring large files via python file streaming is very slow **solution** Support using OS native, such as cp, mv in linux, or user specified utilities with python native tooling as a fallback."

---

## Clarifications

### Session 2026-11-05
- Q: Should file transfer settings (strategy and custom copy/move commands) be configurable only globally, or also allow per-destination endpoint overrides? (FR-001, FR-003) → A: Global transfer config with optional per-destination endpoint overrides.
- Q: What default flags should the OS-native copy utility (`cp`) use when transferring files and directories? (FR-002, FR-005) → A: Use `cp -r --reflink=auto` (with automatic retry as `cp -r` if `--reflink` is unsupported by the host `cp` binary).
- Q: When a user-specified custom move command succeeds, should the system automatically clean up the source if the custom tool left it behind? (FR-003) → A: Verify destination exists and matches source size, then automatically delete any remaining source file/directory if the custom command did not already remove it.
- Q: When an external transfer utility fails, should the system skip the built-in Python fallback if the failure is due to insufficient destination disk space? (FR-007) → A: Abort immediately without attempting Python fallback when destination disk space is insufficient (`ENOSPC`), while falling back to built-in streaming for missing binaries, unsupported flags, or other command failures.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accelerated File Transfers via OS-Native Utilities (Priority: P1) 🎯 MVP

An operator or scheduled media pipeline transfers large media files (such as multi-gigabyte video files, lossless audio albums, or audiobook archives) between source, staging, seed, review, and destination library directories. Instead of relying on slow application-level stream buffering, the system delegates file copy and move operations to operating-system native utilities (such as `cp` and `mv` on Linux/POSIX environments). This allows the system to leverage OS-level kernel optimizations, copy-on-write reflinks, and optimal filesystem buffers for maximum transfer throughput.

**Why this priority**: Directly resolves the core performance bottleneck when moving or copying large media payloads across local and network-attached storage volumes.

**Independent Test**: Configure a media organization run with a large media file in copy or move mode using the native transfer strategy. Verify that the transfer executes via the OS-native utility (`cp` or `mv`), the destination file matches the source identically, and transfer throughput matches native OS performance.

**Acceptance Scenarios**:

1. **Given** a file or directory queued for copying (such as staging intake, seed relocation, or copy-mode organization) on a host with standard OS utilities available, **When** the copy operation executes, **Then** the system performs the transfer using the OS-native copy utility (`cp`) and preserves file content integrity.
2. **Given** a file or directory queued for moving (such as move-mode organization or cross-volume relocation) on a host with standard OS utilities available, **When** the move operation executes, **Then** the system performs the transfer using the OS-native move utility (`mv`) and removes the source file only upon verified completion.
3. **Given** a dry-run execution, **When** file transfers are planned, **Then** the system logs the selected transfer strategy and planned commands without executing any external utility or modifying the filesystem.

---

### User Story 2 - User-Specified Custom Transfer Utilities (Priority: P2)

A systems administrator managing specialized storage (such as NFS mounts, SMB shares, ZFS datasets, or mergerfs pools) wants to use a custom file transfer tool or specific command flags (such as `rsync`, `rclone`, or `cp --reflink=always`) to optimize how files are copied or moved. The administrator configures custom copy and move commands via configuration files, environment variables, or CLI flags, and the system executes those custom commands with the source and destination paths for all media transfers.

**Why this priority**: Gives operators full control to tune file transfer behavior for their specific storage topology and hardware capabilities.

**Independent Test**: Configure a custom copy command template (e.g., a custom utility with specific flags and `{src}` / `{dst}` placeholders) in the configuration. Run the pipeline and verify that the custom command is executed with the exact source and destination paths.

**Acceptance Scenarios**:

1. **Given** a user-configured custom copy command in configuration or CLI options, **When** a copy operation is performed, **Then** the system invokes the custom command with the resolved source and destination paths.
2. **Given** a user-configured custom move command in configuration or CLI options, **When** a move operation is performed, **Then** the system invokes the custom command with the resolved source and destination paths.
3. **Given** source or destination file paths containing spaces, brackets, quotes, unicode characters, or shell metacharacters (e.g., `Show Name (2026) - S01E01 [1080p] & More!.mkv`), **When** an OS-native or custom utility is invoked, **Then** the paths are passed safely as discrete arguments without shell injection or filename splitting errors.

---

### User Story 3 - Automatic Fallback to Built-In File Transfer (Priority: P3)

The media pipeline executes in an environment where a configured custom utility is not installed, an OS-native flag is unsupported by the target filesystem, or the external utility execution fails. Rather than failing the media transfer immediately, the system automatically falls back to built-in application file transfer tooling, cleans up any incomplete target artifacts left by the failed external command, emits a clear warning log explaining the fallback reason, and completes the file transfer reliably.

**Why this priority**: Ensures high reliability and portability across diverse environments (minimal containers, BSD/macOS variants, or misconfigured custom commands) so media processing never halts unnecessarily.

**Independent Test**: Configure an unavailable or failing custom transfer command with fallback enabled. Run a media transfer and verify that the system logs a warning for the failed external command, removes any partial artifact, and completes the transfer using the built-in fallback mechanism.

**Acceptance Scenarios**:

1. **Given** a configured native or custom transfer executable that is missing from the system environment, **When** a transfer is attempted, **Then** the system emits a warning log and seamlessly completes the transfer using the built-in fallback mechanism.
2. **Given** an external transfer utility that exits with a non-zero status code during execution, **When** fallback is triggered, **Then** the system removes any partial destination file created by the failed attempt before re-running the transfer via the built-in fallback mechanism.
3. **Given** both the primary utility and the built-in fallback fail (for example, due to exhausted disk space or permission denial on the destination), **When** the fallback fails, **Then** the system cleans up any partial destination artifacts, logs a descriptive error, and marks the item transfer as failed.

---

### User Story 4 - Transfer Strategy Observability and Telemetry (Priority: P4)

An operator reviewing execution logs or troubleshooting slow transfers wants clear visibility into which transfer engine (`native`, `custom`, or `builtin` fallback) executed each transfer, how long each transfer took, the effective throughput rate, and whether any fallbacks occurred during the batch.

**Why this priority**: Enables operators to verify that native or custom acceleration is functioning as expected and quickly diagnose environment issues causing fallbacks.

**Independent Test**: Run a media batch containing both native transfers and a simulated fallback event. Inspect the structured logs and batch summary output to verify that transfer strategy, duration, throughput, and fallback counts are recorded.

**Acceptance Scenarios**:

1. **Given** a completed file transfer, **When** operational logs are emitted, **Then** the log record includes the active transfer backend (`native`, `custom`, or `builtin`), file size, elapsed duration, and throughput rate.
2. **Given** a batch execution where one or more operations fell back to the built-in transfer mechanism, **When** the batch summary is produced, **Then** the summary reports the count of native/custom transfers and fallback occurrences.

---

### Edge Cases

- **Special Characters and Whitespace in Paths**: Media files frequently contain spaces, parentheses, single/double quotes, ampersands, and non-ASCII unicode characters. Command invocation MUST pass file paths directly as argument lists without shell interpolation to prevent command injection and syntax errors.
- **Partial Artifacts from Interrupted External Commands**: If an external utility fails midway or times out, it may leave a partial file or directory at the destination. The system MUST purge any incomplete destination artifact before attempting the built-in fallback or aborting.
- **Directory Transfers vs Single-File Transfers**: Multi-file media releases (such as music albums or season packs) may transfer entire directories or individual files. OS-native copy commands MUST include recursive handling when copying directories so directory structures are preserved identically to built-in behavior.
- **Hardlink Mode Compatibility**: When the pipeline is configured for `hardlink` mode on the same filesystem, atomic inode linking remains instant. When hardlinking across different filesystems fails and falls back to copying, or when operating in `copy` or `move` modes (including staging intake, review isolation, and remote mount transfers), the configured native/custom transfer strategy MUST be used.
- **Hung or Unresponsive External Processes**: Network filesystem stalls (e.g., unresponsive NFS/SMB mounts) can cause external transfer commands to hang indefinitely. The system MUST support a configurable timeout for external transfer commands so stalled processes are terminated cleanly.
- **Missing Parent Directories**: Before invoking an external `cp`, `mv`, or custom command, the system MUST ensure the destination parent directory exists so external utilities do not fail due to missing target folders.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support three configurable file transfer strategies for copy and move operations: `native` (OS-native utilities such as `cp` and `mv`), `custom` (user-defined external command templates), and `builtin` (standard internal application file streaming).
- **FR-002**: By default, the system MUST attempt OS-native utilities (`native` strategy) on supported POSIX/Linux environments and automatically fall back to `builtin` internal file streaming if native utilities are unavailable or fail.
- **FR-003**: Users MUST be able to configure custom command templates and transfer strategies globally (via configuration file, environment variables, or CLI flags) as well as via optional per-destination endpoint overrides, supporting explicit placeholders (`{src}` and `{dst}`) or standard positional appending of source and destination paths. For custom move operations, if the custom utility exits with code 0 but leaves the source path intact (e.g., `rsync --remove-source-files` leaving directories or copy-like tools), the system MUST verify that the destination exists and matches the source size before removing the remaining source files/directories.
- **FR-004**: All external utility invocations (`native` and `custom`) MUST pass source and destination paths safely as discrete process arguments without invoking an intermediate command shell, preventing shell injection and handling filenames with spaces, quotes, and special characters.
- **FR-005**: When executing OS-native copy operations (`cp`), the system MUST default to `cp -r --reflink=auto` to preserve directory hierarchies recursively, leverage Copy-on-Write clones where supported, and avoid ownership/permission errors on network shares (automatically retrying with `cp -r` if the host `cp` implementation does not support `--reflink`).
- **FR-006**: The system MUST ensure target parent directories exist before invoking any external copy or move utility.
- **FR-007**: When an external transfer utility (`native` or `custom`) is unavailable on the host or exits with a non-zero exit code, and fallback is enabled (the default), the system MUST check whether the failure was caused by insufficient destination disk space (`ENOSPC` / "No space left on device"); if disk space is exhausted, the system MUST clean up partial destination artifacts and abort the item transfer immediately without attempting the `builtin` fallback. For all other tool/command failures, the system MUST log a warning containing the command exit status and error output, remove any partial destination artifact, and retry the operation using the `builtin` transfer mechanism.
- **FR-008**: Users MUST be able to disable automatic fallback (strict mode) via configuration if they require transfers to fail immediately when a custom or native utility fails.
- **FR-009**: External utility executions MUST enforce a configurable timeout to prevent hung storage mounts from blocking cron executions indefinitely, terminating the subprocess and cleaning up partial destination files upon timeout.
- **FR-010**: The configured transfer strategy MUST apply consistently across all file copy and move phases in the application, including staging intake, library organization (`copy` and `move` modes, plus cross-device `hardlink` fallbacks), seed relocation, and unrecognized file staging.
- **FR-011**: In dry-run mode, the system MUST NOT execute any external copy or move utility or modify any files on disk, while accurately logging the transfer strategy and command that would be executed.
- **FR-012**: The system MUST record structured log events and batch summary metrics detailing the transfer strategy used (`native`, `custom`, `builtin`), transfer duration, bytes transferred, and number of fallback events.

### Key Entities *(include if feature involves data)*

- **TransferConfig**: Configuration model defining the active transfer strategy (`native`, `custom`, `builtin`), custom copy/move command templates, fallback toggle (`fallback_enabled`), and subprocess execution timeout (`timeout_seconds`).
- **TransferOperation**: Represents a single file or directory copy/move request containing source path, destination path, operation type (`copy` or `move`), and dry-run state.
- **TransferOutcome**: Telemetry record capturing the result of a transfer operation, including the effective backend used, whether a fallback occurred, elapsed duration, bytes transferred, and any diagnostic error message.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Large file transfers (1 GB or larger) using the `native` strategy achieve at least 90% of the raw throughput of direct operating system `cp`/`mv` commands on the same storage volume, eliminating user-space streaming bottlenecks.
- **SC-002**: 100% of file transfers involving filenames with spaces, quotes, brackets, unicode characters, or shell metacharacters complete without argument parsing errors or security vulnerabilities.
- **SC-003**: 100% of transfer operations where the primary external utility is missing or fails (with fallback enabled) automatically recover via the built-in transfer mechanism without leaving corrupted partial files or aborting the batch.
- **SC-004**: 100% of dry-run executions report the planned transfer strategy without invoking external copy/move commands or altering filesystem state.
- **SC-005**: Structured logs and batch summaries accurately report the transfer backend used and count of fallback events for 100% of processed media items.

---

## Assumptions

- Host environments running Linux or POSIX containers typically provide standard coreutils (`cp` and `mv`) on the system `PATH`.
- When users specify a custom move command (e.g., `rsync --remove-source-files` or a custom script), either the custom command removes the source file upon success or the system verifies destination integrity and removes the source file if the custom tool only performs a copy.
- File metadata preservation (such as modification timestamps and basic permissions) is desirable when supported by the target filesystem, but failures to preserve ownership/permissions on network mounts (such as SMB/NFS with root squashing) should not cause transfers to fail if the file data itself transferred completely.
- Existing atomic staging and hash/size verification protections (from `011-resume-failed-transfers`) continue to work seamlessly alongside native and custom transfer engines.
