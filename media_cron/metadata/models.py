import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
            "raw_response": self.raw_response,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetadataMatch":
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
