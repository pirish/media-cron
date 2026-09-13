# Contract: Music Spool Engine Interface

**Feature**: `005-music-organization`
**Date**: 2026-09-09
**Status**: Complete

---

## 1. Protocol Definition

Every drop-folder spooler implementation must adhere to this runtime-checkable protocol:

```python
from pathlib import Path
from typing import Protocol, runtime_checkable
from media_cron.metadata.models import MusicReleaseBundle, MusicSpoolResult


@runtime_checkable
class MusicSpoolEngineProtocol(Protocol):
    """Protocol for depositing music releases into external manager drop folders."""

    def stage_bundle(
        self,
        bundle: MusicReleaseBundle,
        spool_dir: Path,
        dry_run: bool = False,
    ) -> Path:
        """
        Transfers all tracks and companion assets into a hidden temporary
        staging folder (.incoming_<name>) on the spool filesystem.

        Returns the temporary staging directory path.
        """
        ...

    def promote_bundle(
        self,
        staging_dir: Path,
        final_dir: Path,
        dry_run: bool = False,
    ) -> Path:
        """
        Atomically renames the staging folder to the final release path.

        Returns the finalized release directory path.
        """
        ...

    def execute_post_command(
        self,
        command_template: str,
        release_path: Path,
        timeout_seconds: int = 120,
    ) -> tuple[int, str]:
        """
        Executes a configured post-ingest command (e.g. beet import {release_path}),
        returning (exit_code, stdout_stderr_output).
        """
        ...

    def spool_release(
        self,
        bundle: MusicReleaseBundle,
        spool_dir: Path,
        post_command: str | None = None,
        dry_run: bool = False,
    ) -> MusicSpoolResult:
        """
        Coordinates staging, promotion, and optional post-ingest hook execution.
        """
        ...
```
