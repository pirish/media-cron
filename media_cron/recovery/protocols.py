from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from media_cron.recovery.models import RecoverySummary, VerificationResult


@runtime_checkable
class TransferVerifierProtocol(Protocol):
    """Protocol for verifying file integrity, fast rejection, and safe restart."""

    @property
    def summary(self) -> RecoverySummary:
        """Returns the aggregate recovery telemetry for this verifier session."""
        ...

    def compute_sha256(self, file_path: Path, chunk_size: int = 1048576) -> str:
        """Computes hexadecimal SHA-256 digest of a local file using streaming chunks."""
        ...

    def verify_item(
        self,
        source_path: Path,
        target_path: Path,
    ) -> VerificationResult:
        """Evaluates whether an existing candidate target matches the source payload."""
        ...

    def purge_item(
        self,
        target_path: Path,
        allowed_parent_roots: list[Path],
        dry_run: bool = False,
    ) -> bool:
        """Safely removes an invalid or corrupt candidate file or directory."""
        ...
