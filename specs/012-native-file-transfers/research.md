# Phase 0 Research: High-Speed OS-Native and Custom Utility File Transfers

**Feature**: `012-native-file-transfers`
**Date**: 2026-11-05
**Status**: Complete

---

## 1. OS-Native Utility Selection & Default Flags

### Decision
- **Copy (`native` strategy)**: Invoke `cp -r --reflink=auto <src> <dst>` as the primary command on POSIX/Linux hosts. If the host `cp` binary exits with an unrecognized/unsupported option error (e.g., BSD/macOS `cp` or BusyBox `cp` without `--reflink`), automatically retry once with `cp -r <src> <dst>` before considering the native command failed.
- **Move (`native` strategy)**: Invoke `mv <src> <dst>`.

### Rationale
- Python's `shutil.copy2` and `shutil.copytree` copy data through user-space buffers (unless `os.sendfile` applies to single local files) and call `copystat()`, which frequently triggers `EPERM` / `EACCES` on SMB/CIFS or root-squashed NFS shares.
- GNU coreutils `cp -r --reflink=auto` uses kernel-space `copy_file_range` / `ioctl(FICLONE)` to perform instant Copy-on-Write clones on Btrfs, XFS, and ZFS when source and destination share a filesystem, and automatically degrades to optimal kernel buffer copying across mounts without failing on metadata/ownership preservation errors on network shares.
- Standard `mv` performs an instant atomic `rename(2)` within the same mount point and delegates to optimized kernel copying + removal across mount boundaries.

### Alternatives Considered
- `cp -a` (archive mode): Rejected because `-a` implies `--preserve=all` (ownership, timestamps, xattrs, ACLs), which routinely fails with non-zero exit codes on SMB/NFS shares where the container UID cannot chown files.
- `rsync -a` as the default `native` tool: Rejected because `rsync` is not guaranteed to be installed in minimal container images, whereas POSIX `cp` and `mv` are part of base `coreutils`. Users who prefer `rsync` can configure it via the `custom` strategy.

---

## 2. Shell-Safe Custom Command Template Tokenization

### Decision
- Parse user-configured custom command templates (`copy_command`, `move_command`) using Python's `shlex.split(template)` into an argument list, then inject `str(src)` and `str(dst)` as discrete list elements—never formatting paths into the raw string before `shlex.split()`, and always executing via `subprocess.run(argv, shell=False, ...)`.
- Support two placeholder conventions:
  1. **Explicit tokens**: If `{src}` and `{dst}` appear in the tokenized list, replace exact `{src}` tokens with `str(src)` and `{dst}` tokens with `str(dst)` (also supporting embedded prefix/suffix tokens like `--source={src}` via token-level replacement after `shlex.split()`).
  2. **Positional append**: If neither `{src}` nor `{dst}` is present in the template (e.g., `rsync -a --info=progress2`), append `[str(src), str(dst)]` to the end of the parsed argument list.
  3. **Validation**: If only one of `{src}` or `{dst}` is present without the other, raise a `ValueError` during `TransferConfig` validation.

### Rationale
- Media filenames regularly contain spaces, single/double quotes, parentheses, brackets, ampersands, and non-ASCII characters (e.g., `Show Name (2026) - S01E01 [1080p] & More!.mkv`).
- String-interpolating paths prior to `shlex.split()` or executing with `shell=True` would cause word-splitting bugs or command injection vulnerabilities (`FR-004`, `SC-002`).
- Tokenizing the command template first with `shlex.split()` and substituting path arguments directly into the `argv` array guarantees 100% immunity to shell metacharacter injection.

### Alternatives Considered
- `subprocess.run(..., shell=True)` with `shlex.quote()`: Rejected because Constitution Technical Stack and `FR-004` strictly forbid shell interpolation and require `shell=False`.

---

## 3. Fallback Lifecycle & Disk Space Exhaustion (`ENOSPC`) Fast-Abort

### Decision
- Before invoking any transfer (and when inspecting external utility failures), detect insufficient destination disk space (`ENOSPC`):
  1. **Pre-flight check**: Calculate source byte size (file size or recursive directory sum) and compare against `shutil.disk_usage(dst.parent).free`. If `free < source_bytes`, raise `TransferDiskFullError` (wrapping `OSError(errno.ENOSPC, "No space left on device")`) immediately without invoking external or fallback transfers.
  2. **Post-failure check**: If `subprocess.run` exits non-zero and `stderr` contains `"No space left on device"` (or `ENOSPC`) or `shutil.disk_usage(dst.parent).free < source_bytes`, purge any partial artifact at `dst` and abort immediately without attempting the `builtin` Python fallback (`FR-007`).
- For all other failures when `fallback_enabled=True` (e.g., `FileNotFoundError` for missing binary, non-zero exit code from unsupported flags, or `subprocess.TimeoutExpired`):
  1. Log a structured `WARNING` containing the failed command, exit code/reason, and `stderr`.
  2. Purge any partial destination file or directory created by the failed attempt (`_cleanup_partial(dst)`).
  3. Execute the `builtin` transfer (`shutil.copy2` / `shutil.copytree` for copies, `shutil.move` for moves).
  4. Record `fallback_used=True` and `effective_strategy=TransferStrategy.BUILTIN` in `TransferOutcome`.

### Rationale
- Attempting a slow Python `shutil` stream after `cp` or `rsync` already failed with `ENOSPC` wastes I/O and time on an operation guaranteed to fail again.
- Cleaning up partial destination artifacts before fallback (or before raising on failure/timeout) guarantees idempotency and prevents corrupted half-written media files from polluting staging or library directories (`FR-007`, `FR-009`, Principle III).

### Alternatives Considered
- Unconditional fallback on all non-zero exit codes: Rejected during `/speckit-clarify` (Q4) because disk-full errors cannot be resolved by switching from `cp` to Python `shutil`.

---

## 4. Custom Move Source Cleanup & Integrity Verification

### Decision
- When executing a `MOVE` operation via the `CUSTOM` strategy and the custom command exits with return code `0`:
  1. Verify that `dst` exists on disk.
  2. If `src` still exists on disk (for example, the user configured `rsync -a` or `rsync -a --remove-source-files`, which leaves empty source directories behind, or a custom copy tool):
     - Compute the total byte size of `dst` and verify it matches the pre-recorded `source_bytes` (`dst_bytes == source_bytes`).
     - If verified, automatically remove the remaining `src` file (`src.unlink()`) or directory tree (`shutil.rmtree(src)`).
     - If `dst` does not exist or `dst_bytes != source_bytes`, treat the custom move as failed (clean up `dst` and trigger fallback or raise error).

### Rationale
- Clarified in `/speckit-clarify` (Q3 / `FR-003`). Many administrators use `rsync` or `rclone copy` as a custom transfer command; verifying destination existence and size before removing any leftover source path prevents both duplicate reprocessing on subsequent cron runs and accidental data loss if a misconfigured command exited `0` without writing the target.

### Alternatives Considered
- Requiring custom move commands to always delete the source themselves: Rejected because `rsync --remove-source-files` famously leaves empty source directory trees behind, which would cause directory-mode inputs to leave empty folders in `/downloads`.

---

## 5. Configuration Hierarchy & Call-Site Unification

### Decision
- **Configuration Model**:
  - Add `TransferConfig` to `media_cron/transfer/models.py` and attach it as `transfer: TransferConfig` on `MediaCronConfig` (`media_cron/config.py`).
  - Support optional `transfer: TransferConfig | None = None` on `DestinationEndpointConfig` (`media_cron/routing/models.py`) so individual routes (e.g., a slow SMB archive mount vs a local ZFS pool) can override the global transfer strategy or custom commands (`FR-003`).
  - Expose global environment variables (`MEDIA_CRON_TRANSFER_STRATEGY`, `MEDIA_CRON_TRANSFER_COPY_COMMAND`, `MEDIA_CRON_TRANSFER_MOVE_COMMAND`, `MEDIA_CRON_TRANSFER_FALLBACK_ENABLED`, `MEDIA_CRON_TRANSFER_TIMEOUT_SECONDS`) and CLI flags (`--transfer-strategy`, `--copy-cmd`, `--move-cmd`, `--no-transfer-fallback`, `--transfer-timeout`).
- **Call-Site Integration**:
  - Centralize all copy and move operations in `FileTransferExecutor` (`media_cron/transfer/executor.py`) and wire it into all 8 file-transfer components:
    1. `media_cron/plugins/input/directory.py` (staging move)
    2. `media_cron/plugins/input/torrent.py` (staging file/directory copy)
    3. `media_cron/plugins/output/organizer.py` (`copy`, `move`, and cross-device `hardlink` `EXDEV` fallback)
    4. `media_cron/plugins/output/seed.py` (cross-device `hardlink` `EXDEV` fallback copy)
    5. `media_cron/metadata/music_spooler.py` (hidden staging copy)
    6. `media_cron/metadata/video_spooler.py` (hidden staging copy)
    7. `media_cron/metadata/converter.py` (converted ebook move)
    8. `media_cron/review/manager.py` (unrecognized item staging copy/move and review resolution move)

### Rationale
- Providing a single `FileTransferExecutor` with a default singleton/factory while allowing per-route override injection keeps all 8 call sites clean, testable, and backward-compatible with existing unit/integration tests.
