import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class BookFormat(StrEnum):
    EPUB = "epub"
    MOBI = "mobi"
    AZW = "azw"
    AZW3 = "azw3"
    PDF = "pdf"
    FB2 = "fb2"
    CBZ = "cbz"
    TXT = "txt"
    UNKNOWN = "unknown"

    @classmethod
    def from_path(cls, path: Path) -> "BookFormat":
        suffix = path.suffix.lower()
        if suffix == ".epub":
            return cls.EPUB
        elif suffix == ".mobi":
            return cls.MOBI
        elif suffix == ".azw":
            return cls.AZW
        elif suffix in (".azw3", ".kf8"):
            return cls.AZW3
        elif suffix == ".pdf":
            return cls.PDF
        elif suffix == ".fb2":
            return cls.FB2
        elif suffix == ".cbz":
            return cls.CBZ
        elif suffix == ".txt":
            return cls.TXT
        return cls.UNKNOWN


class RetentionPolicy(StrEnum):
    PRESERVE = "preserve"
    ARCHIVE = "archive"
    REPLACE = "replace"


class ConversionState(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class UDCClassification:
    notation: str
    description: str
    parent_notation: str | None = None
    confidence: float = 1.0
    source: str = "summary_table"

    def to_dict(self) -> dict[str, Any]:
        return {
            "notation": self.notation,
            "description": self.description,
            "parent_notation": self.parent_notation,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UDCClassification":
        return cls(
            notation=data.get("notation", ""),
            description=data.get("description", ""),
            parent_notation=data.get("parent_notation"),
            confidence=float(data.get("confidence", 1.0)),
            source=data.get("source", "summary_table"),
        )


@dataclass
class MetadataMatch:
    title: str
    author: str
    year: int | None = None
    narrator: str | None = None
    series: str | None = None
    volume: str | None = None
    work_id: str | None = None
    provider: str = ""
    confidence: float = 0.0
    isbn: str | None = None
    subjects: list[str] = field(default_factory=list)
    udc_code: str | None = None
    udc_classification: UDCClassification | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "year": self.year,
            "narrator": self.narrator,
            "series": self.series,
            "volume": self.volume,
            "work_id": self.work_id,
            "provider": self.provider,
            "confidence": self.confidence,
            "isbn": self.isbn,
            "subjects": self.subjects,
            "udc_code": self.udc_code,
            "udc_classification": self.udc_classification.to_dict()
            if self.udc_classification
            else None,
            "raw_response": self.raw_response,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetadataMatch":
        udc_data = data.get("udc_classification")
        udc_obj = UDCClassification.from_dict(udc_data) if udc_data else None
        return cls(
            title=data.get("title", ""),
            author=data.get("author", ""),
            year=data.get("year"),
            narrator=data.get("narrator"),
            series=data.get("series"),
            volume=data.get("volume"),
            work_id=data.get("work_id"),
            provider=data.get("provider", ""),
            confidence=float(data.get("confidence", 0.0)),
            isbn=data.get("isbn"),
            subjects=list(data.get("subjects", [])),
            udc_code=data.get("udc_code"),
            udc_classification=udc_obj,
            raw_response=data.get("raw_response", {}),
        )


@dataclass
class AudiobookBundle:
    root_path: Path
    is_multi_file: bool = False
    files: list[Path] = field(default_factory=list)
    seed_title: str = ""
    seed_author: str | None = None
    matched_metadata: MetadataMatch | None = None
    total_size_bytes: int = 0


@dataclass
class MetadataCacheEntry:
    cache_key: str
    provider: str
    query_title: str
    query_author: str | None = None
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = 2592000
    match: MetadataMatch | None = None

    def is_expired(self, current_time: float | None = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return (now - self.created_at) > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "cache_key": self.cache_key,
            "provider": self.provider,
            "query_title": self.query_title,
            "query_author": self.query_author,
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
            "match": self.match.to_dict() if self.match else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetadataCacheEntry":
        match_data = data.get("match")
        match_obj = MetadataMatch.from_dict(match_data) if match_data else None
        return cls(
            cache_key=data["cache_key"],
            provider=data["provider"],
            query_title=data["query_title"],
            query_author=data.get("query_author"),
            created_at=float(data.get("created_at", time.time())),
            ttl_seconds=int(data.get("ttl_seconds", 2592000)),
            match=match_obj,
        )


@dataclass
class BookMetadata:
    title: str
    author: str
    series_name: str | None = None
    volume_number: str | None = None
    publisher: str | None = None
    publication_year: int | None = None
    isbn: str | None = None
    asin: str | None = None
    language: str | None = "en"
    subjects: list[str] = field(default_factory=list)
    description: str | None = None
    udc_code: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "series_name": self.series_name,
            "volume_number": self.volume_number,
            "publisher": self.publisher,
            "publication_year": self.publication_year,
            "isbn": self.isbn,
            "asin": self.asin,
            "language": self.language,
            "subjects": list(self.subjects),
            "description": self.description,
            "udc_code": self.udc_code,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BookMetadata":
        return cls(
            title=data.get("title", ""),
            author=data.get("author", ""),
            series_name=data.get("series_name"),
            volume_number=data.get("volume_number"),
            publisher=data.get("publisher"),
            publication_year=data.get("publication_year"),
            isbn=data.get("isbn"),
            asin=data.get("asin"),
            language=data.get("language", "en"),
            subjects=list(data.get("subjects", [])),
            description=data.get("description"),
            udc_code=data.get("udc_code"),
            extra=data.get("extra", {}),
        )


@dataclass
class ConversionJob:
    job_id: str
    source_path: Path
    source_format: BookFormat
    target_format: BookFormat = BookFormat.EPUB
    temp_target_path: Path | None = None
    final_target_path: Path | None = None
    retention_policy: RetentionPolicy = RetentionPolicy.PRESERVE
    archive_dir: Path | None = None
    state: ConversionState = ConversionState.PENDING
    engine_name: str = "calibre"
    error_message: str | None = None
    duration_seconds: float = 0.0
    output_size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "source_path": str(self.source_path),
            "source_format": self.source_format.value
            if isinstance(self.source_format, BookFormat)
            else str(self.source_format),
            "target_format": self.target_format.value
            if isinstance(self.target_format, BookFormat)
            else str(self.target_format),
            "temp_target_path": str(self.temp_target_path) if self.temp_target_path else None,
            "final_target_path": str(self.final_target_path) if self.final_target_path else None,
            "retention_policy": self.retention_policy.value
            if isinstance(self.retention_policy, RetentionPolicy)
            else str(self.retention_policy),
            "archive_dir": str(self.archive_dir) if self.archive_dir else None,
            "state": self.state.value
            if isinstance(self.state, ConversionState)
            else str(self.state),
            "engine_name": self.engine_name,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "output_size_bytes": self.output_size_bytes,
        }


@dataclass
class BookAsset:
    path: Path
    format: BookFormat
    file_size_bytes: int
    local_metadata: BookMetadata
    canonical_metadata: BookMetadata
    udc_classification: UDCClassification | None = None
    confidence: float = 0.0
    match_source: str = "local_tag"
    conversion_job: ConversionJob | None = None

    @property
    def is_already_standard(self) -> bool:
        return self.format == BookFormat.EPUB

    @property
    def title(self) -> str:
        return self.canonical_metadata.title

    @property
    def author(self) -> str:
        return self.canonical_metadata.author

    @property
    def isbn(self) -> str | None:
        return self.canonical_metadata.isbn

    @property
    def provider(self) -> str:
        return self.match_source
