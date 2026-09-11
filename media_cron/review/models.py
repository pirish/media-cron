import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class ReviewStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    REINGESTED = "reingested"
    DISCARDED = "discarded"


class ReviewAction(StrEnum):
    ORGANIZE_NOW = "organize"
    REINGEST = "reingest"
    DISCARD = "discard"
    SKIP = "skip"


@dataclass
class UnrecognizedFile:
    relative_path: Path
    size_bytes: int
    extension: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": str(self.relative_path),
            "size_bytes": self.size_bytes,
            "extension": self.extension,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnrecognizedFile":
        return cls(
            relative_path=Path(data["relative_path"]),
            size_bytes=int(data["size_bytes"]),
            extension=str(data["extension"]),
        )


@dataclass
class UserAnnotation:
    category: str
    title: str
    creator: str | None = None
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "title": self.title,
            "creator": self.creator,
            "year": self.year,
            "season": self.season,
            "episode": self.episode,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserAnnotation":
        return cls(
            category=str(data["category"]),
            title=str(data["title"]),
            creator=data.get("creator"),
            year=int(data["year"]) if data.get("year") is not None else None,
            season=int(data["season"]) if data.get("season") is not None else None,
            episode=int(data["episode"]) if data.get("episode") is not None else None,
            notes=data.get("notes"),
        )


@dataclass
class ReviewManifest:
    item_id: str
    created_at: datetime
    original_path: str
    is_directory: bool
    total_size_bytes: int
    files: list[UnrecognizedFile]
    detected_category_hint: str | None = None
    failure_reasons: list[str] = field(default_factory=list)
    status: ReviewStatus = ReviewStatus.PENDING
    user_annotation: UserAnnotation | None = None
    resolved_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "created_at": self.created_at.isoformat(),
            "original_path": self.original_path,
            "is_directory": self.is_directory,
            "total_size_bytes": self.total_size_bytes,
            "files": [f.to_dict() for f in self.files],
            "detected_category_hint": self.detected_category_hint,
            "failure_reasons": list(self.failure_reasons),
            "status": self.status.value,
            "user_annotation": self.user_annotation.to_dict() if self.user_annotation else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewManifest":
        created_at = datetime.fromisoformat(data["created_at"])
        resolved_at = (
            datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None
        )
        files = [UnrecognizedFile.from_dict(f) for f in data.get("files", [])]
        user_ann = (
            UserAnnotation.from_dict(data["user_annotation"])
            if data.get("user_annotation")
            else None
        )
        status = ReviewStatus(data["status"]) if "status" in data else ReviewStatus.PENDING

        return cls(
            item_id=str(data["item_id"]),
            created_at=created_at,
            original_path=str(data["original_path"]),
            is_directory=bool(data.get("is_directory", False)),
            total_size_bytes=int(data.get("total_size_bytes", 0)),
            files=files,
            detected_category_hint=data.get("detected_category_hint"),
            failure_reasons=list(data.get("failure_reasons", [])),
            status=status,
            user_annotation=user_ann,
            resolved_at=resolved_at,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ReviewManifest":
        return cls.from_dict(json.loads(json_str))
