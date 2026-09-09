import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

# Exit code constants
EXIT_SUCCESS = 0
EXIT_PARTIAL_OR_LOCKED = 1
EXIT_CONFIG_ERROR = 2
EXIT_FATAL_ERROR = 3


class MediaCategory(StrEnum):
    VIDEO_MOVIE = "video_movie"
    VIDEO_SERIES = "video_series"
    AUDIO_MUSIC = "audio_music"
    AUDIO_BOOK = "audio_book"
    BOOK_EBOOK = "book_ebook"
    UNKNOWN = "unknown"


class TransferMode(StrEnum):
    HARDLINK = "hardlink"
    MOVE = "move"
    COPY = "copy"


class OperationType(StrEnum):
    ORGANIZE = "ORGANIZE"
    SEED_RELOCATE = "SEED_RELOCATE"
    PURGE_JUNK = "PURGE_JUNK"
    PURGE_SAMPLE = "PURGE_SAMPLE"
    UPGRADE_REPLACE = "UPGRADE_REPLACE"
    SKIP_COLLISION = "SKIP_COLLISION"
    QUARANTINE_CORRUPT = "QUARANTINE_CORRUPT"
    TORRENT_STAGE_COPY = "TORRENT_STAGE_COPY"
    TORRENT_RELOCATE = "TORRENT_RELOCATE"
    TORRENT_TAG = "TORRENT_TAG"


class OperationStatus(StrEnum):
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


@dataclass
class DiscoveredItem:
    source_path: Path
    file_size: int
    modified_time: float
    is_archive: bool = False
    is_directory: bool = False


@dataclass
class MediaAsset:
    path: Path
    category: MediaCategory
    raw_title: str
    clean_title: str
    extension: str
    file_size: int
    year: int | None = None
    series_title: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    artist: str | None = None
    album: str | None = None
    track_number: int | None = None
    author: str | None = None
    narrator: str | None = None
    volume: str | None = None
    resolution: str | None = None
    bitrate_kbps: int | None = None
    confidence: float | None = None
    identification_source: str | None = None
    udc_code: str | None = None
    isbn: str | None = None
    is_valid: bool = True
    integrity_error: str | None = None
    subtitle_files: list[Path] = field(default_factory=list)
    ancillary_files: list[Path] = field(default_factory=list)


@dataclass
class OperationPlan:
    op_type: OperationType
    transfer_mode: TransferMode
    source_path: Path
    reason: str
    plan_id: uuid.UUID = field(default_factory=uuid.uuid4)
    destination_path: Path | None = None
    dry_run: bool = False


@dataclass
class OperationResult:
    plan: OperationPlan
    status: OperationStatus
    message: str = ""
    error: str | None = None


@dataclass
class BatchSummary:
    started_at: datetime
    completed_at: datetime
    total_scanned: int = 0
    processed_count: int = 0
    upgraded_count: int = 0
    junk_purged_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    errors: list[str] = field(default_factory=list)
    operations: list[OperationResult] = field(default_factory=list)
    batch_id: uuid.UUID = field(default_factory=uuid.uuid4)
    dry_run: bool = False
    exit_code: int = EXIT_SUCCESS
    torrent_summary: dict | None = None
    audiobook_summary: dict | None = None
    books_summary: dict | None = None

    def to_dict(self) -> dict:
        data = {
            "batch_id": str(self.batch_id),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "dry_run": self.dry_run,
            "total_scanned": self.total_scanned,
            "processed_count": self.processed_count,
            "upgraded_count": self.upgraded_count,
            "junk_purged_count": self.junk_purged_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "exit_code": self.exit_code,
            "operations": [
                {
                    "plan_id": str(r.plan.plan_id),
                    "op_type": r.plan.op_type.value,
                    "source_path": str(r.plan.source_path),
                    "destination_path": str(r.plan.destination_path)
                    if r.plan.destination_path
                    else None,
                    "status": r.status.value,
                    "reason": r.plan.reason,
                }
                for r in self.operations
            ],
            "errors": self.errors,
        }
        if self.torrent_summary is not None:
            data["torrent_summary"] = self.torrent_summary
        if self.audiobook_summary is not None:
            data["audiobook_summary"] = self.audiobook_summary
        if self.books_summary is not None:
            data["books_summary"] = self.books_summary
        return data
