# Data Model: Music Library Organization and Drop-Folder Ingestion

**Feature**: `005-music-organization`  
**Date**: 2026-09-09  
**Status**: Complete  

---

## 1. Domain Entities & Enums

### MusicWorkflowMode (Enum)
Defines the operational workflow pipeline mode for music processing.
```python
class MusicWorkflowMode(str, Enum):
    SPOOL = "spool"  # Deposit release bundles into external manager's drop directory
    DIRECT = "direct"  # Extract tags and organize directly into target music library
    HYBRID = "hybrid"  # Enrich/verify tags via external catalog, then deposit into drop directory
```

### MusicFormat (Enum)
Supported digital audio container formats.
```python
class MusicFormat(str, Enum):
    MP3 = "mp3"
    FLAC = "flac"
    M4A = "m4a"
    OGG = "ogg"
    OPUS = "opus"
    WAV = "wav"
    ALAC = "alac"
    AIFF = "aiff"
    UNKNOWN = "unknown"
```

### MusicTrack (Entity)
Represents an individual audio file within a music release.
```python
@dataclass
class MusicTrack:
    path: Path
    format: MusicFormat
    file_size: int
    title: str
    artist: str
    album: str
    album_artist: str | None = None
    track_number: int | None = None
    disc_number: int | None = None
    year: int | None = None
    genre: str | None = None
    duration_seconds: float | None = None
    bitrate_kbps: int | None = None
    musicbrainz_track_id: str | None = None
    musicbrainz_release_id: str | None = None
    is_valid: bool = True
```

### MusicCompanionAsset (Entity)
Represents a non-audio companion asset bundled within a release (artwork, cuesheet, log, playlist).
```python
class CompanionAssetType(str, Enum):
    COVER_ART = "cover_art"
    CUE_SHEET = "cue_sheet"
    RIP_LOG = "rip_log"
    PLAYLIST = "playlist"
    OTHER = "other"


@dataclass
class MusicCompanionAsset:
    path: Path
    asset_type: CompanionAssetType
    file_size: int
```

### MusicReleaseBundle (Entity)
Represents an album, EP, single, or multi-disc box set clustered as a coherent unit.
```python
@dataclass
class MusicReleaseBundle:
    bundle_id: str
    root_path: Path
    album_title: str
    album_artist: str
    tracks: list[MusicTrack] = field(default_factory=list)
    companion_assets: list[MusicCompanionAsset] = field(default_factory=list)
    year: int | None = None
    genre: str | None = None
    is_compilation: bool = False
    total_discs: int = 1
    confidence: float = 1.0
    matched_catalog: MusicCatalogMatch | None = None
```

### MusicCatalogMatch (Entity)
External catalog candidate from MusicBrainz or Discogs.
```python
@dataclass
class MusicCatalogMatch:
    title: str
    artist: str
    release_id: str
    provider: str
    confidence: float
    year: int | None = None
    track_count: int | None = None
    tracks: list[str] = field(default_factory=list)
```

### MusicSpoolResult (Entity)
Result of depositing a release bundle into the external manager's drop directory.
```python
@dataclass
class MusicSpoolResult:
    bundle_id: str
    source_dir: Path
    target_dir: Path
    file_count: int
    bytes_transferred: int
    mode: str
    success: bool
    post_command_executed: bool = False
    post_command_exit_code: int | None = None
    error: str | None = None
```

---

## 2. Configuration Models

### MusicConfig
Configures the music subsystem within `MediaCronConfig`.
```python
@dataclass
class MusicConfig:
    enabled: bool = True
    workflow_mode: MusicWorkflowMode = MusicWorkflowMode.DIRECT
    spool_dir: Path | None = None
    post_ingest_command: str | None = None
    enable_external_lookup: bool = False
    provider: str = "musicbrainz"
    discogs_token: str | None = None
    confidence_threshold: float = 0.85
    cache_ttl_days: int = 30
    hardlink_with_copy_fallback: bool = True
```

---

## 3. Relationships & State Lifecycle

```
[Discovered Audio Files + Assets]
            │
            ▼
 [MusicReleaseBundleAggregator]
            │
            ├─► Groups by parent directory & album tags
            ├─► Clusters multi-disc folders (CD1, CD2)
            └─► Collects companion assets (art, cue, log)
            │
            ▼
  [MusicReleaseBundle]
            │
    ┌───────┴────────────────────────┐
    ▼                                ▼
[Mode: SPOOL]                 [Mode: DIRECT]
    │                                │
    ├─► Create .incoming_<id>/       ├─► Read embedded tags (tinytag)
    ├─► Transfer tracks + assets     ├─► Optional Catalog Match (MusicBrainz)
    ├─► Atomic rename to final/      ├─► Format standard path (Artist/Album/)
    └─► Optional post_command        └─► Place tracks + cover art
```
