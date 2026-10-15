from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class VerificationStatus(StrEnum):
    """Integrity evaluation status between source and candidate target."""

    MATCH = "match"
    SIZE_MISMATCH = "size_mismatch"
    HASH_MISMATCH = "hash_mismatch"
    MISSING = "missing"
    CORRUPTED = "corrupted"


@dataclass(frozen=True)
class FileIntegrityRecord:
    """Verification details for a single file within an item."""

    relative_path: Path
    source_path: Path
    target_path: Path
    source_size: int
    target_size: int | None
    source_hash: str | None
    target_hash: str | None
    status: VerificationStatus
    is_same_inode: bool = False


@dataclass
class VerificationResult:
    """Aggregate verification outcome for a queued item."""

    item_name: str
    source_root: Path
    target_root: Path
    is_directory: bool
    overall_status: VerificationStatus
    file_records: list[FileIntegrityRecord] = field(default_factory=list)
    total_source_bytes: int = 0
    bytes_saved: int = 0
    can_resume: bool = False
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.can_resume is False and self.overall_status == VerificationStatus.MATCH:
            self.can_resume = True
        if self.bytes_saved == 0 and self.can_resume:
            self.bytes_saved = self.total_source_bytes


@dataclass
class RecoverySummary:
    """Session telemetry tracking resumed and purged items."""

    items_scanned: int = 0
    items_resumed: int = 0
    transfers_bypassed: int = 0
    items_purged: int = 0
    bytes_saved: int = 0
    purge_errors: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "items_scanned": self.items_scanned,
            "items_resumed": self.items_resumed,
            "transfers_bypassed": self.transfers_bypassed,
            "items_purged": self.items_purged,
            "bytes_saved": self.bytes_saved,
            "purge_errors": self.purge_errors,
        }
