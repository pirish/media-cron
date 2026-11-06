# Contract: Transfer Executor Interface

**Feature**: `012-native-file-transfers`
**Module**: `media_cron.transfer` (`base.py`, `executor.py`, `models.py`)

---

## 1. Protocol Definition (`media_cron/transfer/base.py`)

```python
from pathlib import Path
from typing import Protocol, runtime_checkable
from media_cron.transfer.models import TransferConfig, TransferOutcome, TransferSummary


@runtime_checkable
class TransferExecutorProtocol(Protocol):
    """Protocol for executing file and directory copy/move operations."""

    @property
    def config(self) -> TransferConfig:
        """Return the active TransferConfig for this executor."""
        ...

    def copy(
        self,
        src: Path,
        dst: Path,
        *,
        dry_run: bool = False,
        override_config: TransferConfig | None = None,
    ) -> TransferOutcome:
        """Copy a file or directory from src to dst using the configured transfer strategy."""
        ...

    def move(
        self,
        src: Path,
        dst: Path,
        *,
        dry_run: bool = False,
        override_config: TransferConfig | None = None,
    ) -> TransferOutcome:
        """Move a file or directory from src to dst using the configured transfer strategy."""
        ...

    def get_summary(self) -> TransferSummary:
        """Return aggregated TransferSummary metrics for all operations executed by this instance."""
        ...
```

---

## 2. Behavioral Invariants

1. **Shell-Free Execution (`FR-004`, `SC-002`)**:
   - External commands (`native` and `custom`) MUST be executed via `subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=active_config.timeout_seconds)`.
   - `src` and `dst` paths MUST be injected into `argv` as discrete strings after `shlex.split()`, never interpolated into a shell string.

2. **Parent Directory Guarantee (`FR-006`)**:
   - When `dry_run=False`, `dst.parent.mkdir(parents=True, exist_ok=True)` MUST be executed before running any external or built-in transfer.

3. **OS-Native Command Resolution (`FR-005`)**:
   - `copy`: Primary command is `["cp", "-r", "--reflink=auto", str(src), str(dst)]`.
   - If `cp` fails with an unrecognized/invalid option error for `--reflink`, the executor MUST clean up any partial `dst` and immediately retry with `["cp", "-r", str(src), str(dst)]` while still within the `native` strategy.
   - `move`: Command is `["mv", str(src), str(dst)]`.

4. **Custom Command Template Resolution & Move Cleanup (`FR-003`)**:
   - Tokenizes `copy_command` or `move_command` using `shlex.split()`.
   - If `{src}` and `{dst}` placeholders exist in tokens, replaces `{src}` with `str(src)` and `{dst}` with `str(dst)`. Otherwise appends `[str(src), str(dst)]`.
   - For `move` under `custom` strategy: after exit code `0`, verifies `dst.exists()` and `compute_path_size(dst) == source_bytes`. If `src.exists()` is still `True`, deletes `src` (`src.unlink()` for files/symlinks, `shutil.rmtree(src)` for directories). If `dst` is missing or size mismatches, purges `dst` and treats the custom command as failed.

5. **Disk Space Exhaustion (`ENOSPC`) Fast-Abort (`FR-007`)**:
   - Before starting any copy or cross-device move, checks `shutil.disk_usage(dst.parent).free < source_bytes`.
   - Also inspects `OSError.errno == errno.ENOSPC` and subprocess `stderr` for `"No space left on device"` (case-insensitive).
   - When `ENOSPC` is detected, cleans up any partial artifact at `dst` and raises `TransferDiskFullError` immediately **without** attempting the `builtin` fallback, regardless of `fallback_enabled`.

6. **Automatic Fallback & Partial Cleanup (`FR-007`, `FR-008`, `FR-009`)**:
   - When a `native` or `custom` command fails (missing binary `FileNotFoundError`, non-zero exit code not caused by `ENOSPC`, or `subprocess.TimeoutExpired`):
     - Any partial file or directory at `dst` that did not exist prior to the transfer MUST be removed (`_cleanup_partial(dst)`).
     - If `fallback_enabled=False`, raises `TransferTimeoutError` (on timeout) or `TransferExecutionError`.
     - If `fallback_enabled=True`, emits a `WARNING` log with the command, failure reason, and `stderr`, then executes the `builtin` strategy (`shutil.copytree(src, dst, dirs_exist_ok=True)` for directories, `shutil.copy2(src, dst)` for files, or `shutil.move(str(src), str(dst))` for moves) and returns `TransferOutcome(effective_strategy=TransferStrategy.BUILTIN, fallback_used=True, ...)`.

7. **Dry-Run Invariant (`FR-011`, `SC-004`)**:
   - When `dry_run=True`, no directories are created, no files are modified, and `subprocess.run` is never called.
   - The executor resolves the exact `command_executed` list, logs an `INFO` message describing the planned strategy and command, increments nothing on disk, and returns a `TransferOutcome` with `dry_run=True`.
