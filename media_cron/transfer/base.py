from __future__ import annotations

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
