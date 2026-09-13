# Contract: ReviewManager Interface

**Protocol**: `ReviewManagerProtocol`
**Module**: `media_cron.review.base`
**Implementation**: `media_cron.review.manager.ReviewManager`

---

## Protocol Definition

```python
from typing import Protocol
from pathlib import Path
from media_cron.review.models import (
    ReviewManifest,
    ReviewStatus,
    ReviewAction,
    UserAnnotation,
)
from media_cron.config import MediaCronConfig


class ReviewManagerProtocol(Protocol):
    """Protocol governing the staging, inspection, and manual resolution of unrecognized media."""

    @property
    def review_dir(self) -> Path:
        """Returns the configured review root directory."""
        ...

    def list_items(
        self,
        status: ReviewStatus | None = None,
    ) -> list[ReviewManifest]:
        """Lists all items staged in the review directory, optionally filtered by status."""
        ...

    def get_item(self, item_id: str) -> ReviewManifest:
        """Retrieves a specific review manifest by item ID. Raises FileNotFoundError if missing."""
        ...

    def stage_unrecognized(
        self,
        source_paths: list[Path],
        config: MediaCronConfig,
        failure_reasons: list[str] | None = None,
        dry_run: bool = False,
    ) -> ReviewManifest:
        """Atomically stages an unrecognized file or directory into the review directory.

        - Uses hidden staging directory (.staging_<item_id>) on the review filesystem.
        - Checks torrent seeding status to force non-destructive copy/hardlink when seeding.
        - Writes manifest.json.
        - Atomically promotes directory using os.replace.
        """
        ...

    def resolve_item(
        self,
        item_id: str,
        annotation: UserAnnotation,
        action: ReviewAction,
        config: MediaCronConfig,
        dry_run: bool = False,
    ) -> ReviewManifest:
        """Applies a resolution action to a reviewed item.

        - ORGANIZE_NOW: Formats destination library path using existing organizer templates,
          transfers files, triggers optional media server rescan (Jellyfin/Emby/Plex),
          and updates status to RESOLVED.
        - REINGEST: Writes .media-cron-hint.json and moves files back to staging directory,
          updating status to REINGESTED.
        - DISCARD: Safely deletes the item directory from review_dir after confirmation,
          updating status to DISCARDED.
        - SKIP: Leaves files untouched, preserving PENDING status.
        """
        ...

    def purge_items(
        self,
        older_than_days: int,
        dry_run: bool = False,
    ) -> list[str]:
        """Purges items in the review directory older than the specified age threshold.
        Returns the list of purged item IDs.
        """
        ...
```

---

## Invariants & Guarantees

1. **Atomic Promotion**: `stage_unrecognized` never exposes partially copied files or unwritten manifests to external watchers.
2. **Torrent Safety**: Never performs a destructive `move` on a file associated with an active torrent seed; forces `copy` or `hardlink`.
3. **Idempotency**: Resolving an already-resolved item or re-running `list_items` is safe and idempotent.
4. **Dry-Run Safety**: When `dry_run=True`, operations simulate filesystem transfers and return simulated manifests without moving or deleting files.
