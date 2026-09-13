# Contract: Video Spool Engine Interface

**Feature**: `006-video-organization`
**Date**: 2026-09-09
**Status**: Complete

---

## 1. Protocol Definition

Defines the contract for staging and transferring video releases into external drop directories with atomic inotify safety:

```python
from pathlib import Path
from typing import Protocol
from media_cron.metadata.models import VideoReleaseBundle, VideoSpoolResult


class VideoSpoolEngineProtocol(Protocol):
    """Protocol for atomic drop-folder video release spooling and command hook execution."""

    def spool_release(
        self,
        bundle: VideoReleaseBundle,
        spool_dir: Path,
        post_command: str | None = None,
        dry_run: bool = False,
    ) -> VideoSpoolResult:
        """Deposits a release bundle into spool_dir using atomic staging and executes post-command."""
        ...
```

---

## 2. Inotify Safety Guarantees

1. **Hidden Directory Staging**:
   - Files are written to `<spool_dir>/.incoming_<bundle.root_path.name>_<uuid4().hex[:8]>/`.
   - Internal directory hierarchy (e.g., `Subs/`, `CD1/`) is recreated inside the hidden directory.
2. **Transfer Precedence**:
   - Tries `os.link()` (hardlink) first for instant transfer and active seeding compatibility.
   - Falls back to `shutil.copy2()` when source and spool directory reside on different filesystems.
3. **Atomic Promotion**:
   - Only after all primary videos and companion assets are completely transferred without errors, the hidden folder is atomically renamed to `<spool_dir>/<bundle.root_path.name>` via `os.replace`.
4. **Cleanup on Failure**:
   - If an error occurs during file transfers, the partial hidden directory is completely deleted and source files remain untouched.
5. **Post-Command Hook**:
   - Executed via `subprocess.run(..., shell=True)` after successful promotion.
   - Substitutes `{release_path}` with the absolute target path.
6. **Destination Collision Handling**:
   - If `<spool_dir>/<bundle.root_path.name>` already exists in the drop directory, the engine aborts promotion, deletes the temporary hidden staging folder, leaves the source files intact in staging, and returns `VideoSpoolResult(success=True, skipped=True, skip_reason="Target directory already exists in drop folder")`.
