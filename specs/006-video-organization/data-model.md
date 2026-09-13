# Data Model: Video Organization, Drop-Folder Spooling, and Media Server Rescan

**Feature**: `006-video-organization`
**Date**: 2026-09-09
**Status**: Complete

---

## 1. Domain Entities & Enums

### VideoWorkflowMode
Represents the operational pipeline mode for video processing:
```python
from enum import Enum


class VideoWorkflowMode(str, Enum):
    SPOOL = (
        "spool"  # Deposit release bundles into external manager drop directory (e.g. *arr stack)
    )
    DIRECT = "direct"  # Internal metadata parsing and structured library organization
    HYBRID = "hybrid"  # Enrich/sanitize tags, then deposit into drop directory
```

### VideoFormat
Categorizes supported container formats:
```python
class VideoFormat(str, Enum):
    MKV = "mkv"
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    WMV = "wmv"
    M4V = "m4v"
    TS = "ts"
    UNKNOWN = "unknown"

    @classmethod
    def from_path(cls, path: Path) -> VideoFormat:
        ext = path.suffix.lower().lstrip(".")
        for fmt in cls:
            if fmt.value == ext:
                return fmt
        return cls.UNKNOWN
```

### VideoCompanionType
Classifies non-video sidecar assets clustered with a release:
```python
class VideoCompanionType(str, Enum):
    SUBTITLE = "subtitle"  # .srt, .vtt, .ass, .ssa, .sub, .idx
    ARTWORK = "artwork"  # poster.jpg, fanart.jpg, banner.jpg, folder.jpg, cover.jpg
    METADATA_NFO = "metadata_nfo"  # .nfo metadata files
    UNKNOWN = "unknown"

    @classmethod
    def from_path(cls, path: Path) -> VideoCompanionType:
        ext = path.suffix.lower()
        name = path.name.lower()
        if ext in (".srt", ".vtt", ".ass", ".ssa", ".sub", ".idx"):
            return cls.SUBTITLE
        if ext in (".jpg", ".jpeg", ".png") and any(
            k in name for k in ("poster", "fanart", "banner", "folder", "cover", "thumb")
        ):
            return cls.ARTWORK
        if ext == ".nfo":
            return cls.METADATA_NFO
        return cls.UNKNOWN
```

### VideoCompanionAsset
Represents a valid sidecar file belonging to a video release:
```python
@dataclass
class VideoCompanionAsset:
    path: Path
    asset_type: VideoCompanionType
    file_size: int
    language: str | None = None  # e.g., 'en', 'es', 'fr' parsed from stem (.en.srt)
    descriptor: str | None = None  # e.g., 'forced', 'sdh' parsed from stem (.en.forced.srt)
```

### VideoTrack
Represents an individual video asset with parsed metadata:
```python
@dataclass
class VideoTrack:
    path: Path
    title: str
    file_size: int
    format: VideoFormat
    show_title: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    episode_end_number: int | None = None
    year: int | None = None
    resolution: str | None = None  # e.g., '2160p', '1080p', '720p', '480p'
    source_quality: str | None = None  # e.g., 'BluRay', 'WEB-DL', 'HDTV'
    video_codec: str | None = None  # e.g., 'x265', 'h264', 'HEVC', 'AV1'
    audio_codec: str | None = None  # e.g., 'DTS-HD', 'AAC', 'Atmos', 'DD5.1'
    is_sample: bool = False
    is_valid: bool = True
```

### VideoReleaseBundle
Aggregates tracks, companion files, and directory structure for a cohesive release:
```python
@dataclass
class VideoReleaseBundle:
    bundle_id: str
    root_path: Path
    release_title: str
    is_series: bool = False
    show_title: str | None = None
    season_number: int | None = None
    year: int | None = None
    primary_videos: list[VideoTrack] = field(default_factory=list)
    companion_assets: list[VideoCompanionAsset] = field(default_factory=list)
```

### VideoSpoolResult
Captures the output of a drop-folder spooling operation:
```python
@dataclass
class VideoSpoolResult:
    bundle_id: str
    source_dir: Path
    target_dir: Path
    file_count: int
    bytes_transferred: int
    mode: str  # 'hardlink' or 'copy'
    success: bool
    skipped: bool = False  # True if target directory already exists in drop folder
    skip_reason: str | None = None  # e.g., "Target directory already exists in drop folder"
    post_command_executed: bool = False
    post_command_exit_code: int | None = None
    error: str | None = None
```

---

## 2. Media Server Entities

### MediaServerType
Enum representing supported player/server targets:
```python
class MediaServerType(str, Enum):
    JELLYFIN = "jellyfin"
    EMBY = "emby"
    PLEX = "plex"
```

### MediaServerConfig
Configuration entity for the active media server:
```python
@dataclass
class MediaServerConfig:
    enabled: bool = False
    provider: str = "jellyfin"  # "jellyfin", "emby", "plex"
    url: str = ""  # e.g. "http://localhost:8096"
    token: str = ""  # API key or X-Plex-Token
    library_id: str | None = None  # Optional specific section/library ID
    timeout_seconds: float = 5.0
    max_retries: int = 0  # Configurable retry count (default 0 for fail-fast)
```

### MediaServerRescanResult
Represents the result of a media server notification ping:
```python
@dataclass
class MediaServerRescanResult:
    server_type: str
    endpoint: str
    status_code: int | None
    duration_seconds: float
    success: bool
    error: str | None = None
```

---

## 3. Configuration Model Extension

Added to `MediaCronConfig` under `media_cron/config.py`:
```python
@dataclass
class VideoConfig:
    enabled: bool = True
    workflow_mode: str = "direct"  # "spool" | "direct" | "hybrid"
    spool_dir: Path | None = None
    post_ingest_command: str | None = None
    preserve_companions: bool = True
    library_movies_dir: str = "Movies"
    library_tv_dir: str = "TV"
    media_server: MediaServerConfig = field(default_factory=MediaServerConfig)
```
