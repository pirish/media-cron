from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from media_cron.models import MediaCategory, MediaRouteSummary, TransferMode

__all__ = [
    "SupportedMediaType",
    "SourceEndpointType",
    "DestinationEndpointType",
    "MEDIA_TYPE_TO_CATEGORY",
    "CATEGORY_TO_MEDIA_TYPE",
    "SourceEndpointConfig",
    "DestinationEndpointConfig",
    "MediaRouteConfig",
    "ResolvedMediaRoute",
    "MediaRouteSummary",
]


class SupportedMediaType(StrEnum):
    MUSIC = "music"
    AUDIOBOOKS = "audiobooks"
    BOOKS = "books"
    MOVIES = "movies"
    TV = "tv"


class SourceEndpointType(StrEnum):
    DIRECTORY = "directory"
    TORRENT = "torrent"


class DestinationEndpointType(StrEnum):
    LIBRARY = "library"
    SPOOL = "spool"


MEDIA_TYPE_TO_CATEGORY: dict[SupportedMediaType, set[MediaCategory]] = {
    SupportedMediaType.MUSIC: {MediaCategory.AUDIO_MUSIC},
    SupportedMediaType.AUDIOBOOKS: {MediaCategory.AUDIO_BOOK},
    SupportedMediaType.BOOKS: {MediaCategory.BOOK_EBOOK},
    SupportedMediaType.MOVIES: {MediaCategory.VIDEO_MOVIE},
    SupportedMediaType.TV: {MediaCategory.VIDEO_SERIES},
}

CATEGORY_TO_MEDIA_TYPE: dict[MediaCategory, SupportedMediaType] = {
    MediaCategory.AUDIO_MUSIC: SupportedMediaType.MUSIC,
    MediaCategory.AUDIO_BOOK: SupportedMediaType.AUDIOBOOKS,
    MediaCategory.BOOK_EBOOK: SupportedMediaType.BOOKS,
    MediaCategory.VIDEO_MOVIE: SupportedMediaType.MOVIES,
    MediaCategory.VIDEO_SERIES: SupportedMediaType.TV,
}


@dataclass
class SourceEndpointConfig:
    type: SourceEndpointType = SourceEndpointType.DIRECTORY
    path: Path | None = None
    client_profile: str | None = None
    category: str | None = None
    tag: str | None = None
    exclude_categories: list[str] = field(default_factory=lambda: ["media-cron-done"])
    exclude_tags: list[str] = field(default_factory=lambda: ["media-cron-processed"])
    min_progress: float = 1.0


@dataclass
class DestinationEndpointConfig:
    type: DestinationEndpointType = DestinationEndpointType.LIBRARY
    path: Path | None = None
    template: str | None = None


@dataclass
class MediaRouteConfig:
    sources: list[SourceEndpointConfig] = field(default_factory=list)
    destination: DestinationEndpointConfig | None = None
    transfer_mode: str | None = None  # "hardlink" | "copy" | "move"


@dataclass
class ResolvedMediaRoute:
    media_type: SupportedMediaType
    source_endpoints: list[SourceEndpointConfig]
    destination_endpoint: DestinationEndpointConfig
    transfer_mode: TransferMode
    is_active: bool = True
    is_healthy: bool = True
    validation_error: str | None = None
