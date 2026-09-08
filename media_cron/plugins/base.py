from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, runtime_checkable

from media_cron.models import DiscoveredItem, MediaAsset, OperationPlan, OperationResult


@runtime_checkable
class InputPlugin(Protocol):
    """Protocol for ingesting media candidates from a source location."""

    @property
    def plugin_name(self) -> str:
        """Unique identifier for the input plugin."""
        ...

    def discover(
        self, source_path: Path, staging_path: Path, dry_run: bool = False
    ) -> Iterable[DiscoveredItem]:
        """
        Discovers items from source and moves/stages them into staging_path.

        Args:
            source_path: The configured source directory or endpoint.
            staging_path: The dedicated staging directory where files are isolated.
            dry_run: If True, discover in-place without moving files to staging.

        Returns:
            An iterable of DiscoveredItem objects located in staging_path (or source_path if dry-run).
        """
        ...


@runtime_checkable
class LookupPlugin(Protocol):
    """Protocol for extracting metadata and normalizing media assets."""

    @property
    def plugin_name(self) -> str:
        """Unique identifier for the lookup plugin."""
        ...

    def can_handle(self, item: DiscoveredItem) -> bool:
        """Returns True if this plugin can extract metadata for the item."""
        ...

    def enrich(self, item: DiscoveredItem) -> MediaAsset:
        """Extracts metadata and constructs a validated MediaAsset."""
        ...


@runtime_checkable
class OutputPlugin(Protocol):
    """Protocol for executing file placement, seeding, or pruning."""

    @property
    def plugin_name(self) -> str:
        """Unique identifier for the output plugin."""
        ...

    def execute(self, plan: OperationPlan) -> OperationResult:
        """
        Executes a planned file operation (hardlink, move, copy, delete, upgrade).

        Args:
            plan: The operation plan specifying source, destination, mode, and dry-run.

        Returns:
            OperationResult indicating status and details.
        """
        ...
