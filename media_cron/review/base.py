from pathlib import Path
from typing import Protocol, runtime_checkable

from media_cron.config import MediaCronConfig
from media_cron.review.models import (
    ReviewAction,
    ReviewManifest,
    ReviewStatus,
    UserAnnotation,
)


@runtime_checkable
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
        """Atomically stages an unrecognized file or directory into the review directory."""
        ...

    def resolve_item(
        self,
        item_id: str,
        annotation: UserAnnotation,
        action: ReviewAction,
        config: MediaCronConfig,
        dry_run: bool = False,
    ) -> ReviewManifest:
        """Applies a resolution action to a reviewed item."""
        ...

    def purge_items(
        self,
        older_than_days: int,
        dry_run: bool = False,
    ) -> list[str]:
        """Purges items in the review directory older than the specified age threshold."""
        ...
