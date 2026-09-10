from pathlib import Path
from typing import Protocol, runtime_checkable

from media_cron.config import ExternalProviderConfig
from media_cron.metadata.models import (
    MediaServerConfig,
    MediaServerRescanResult,
    MetadataMatch,
    MusicCatalogMatch,
    MusicReleaseBundle,
    MusicSpoolResult,
    VideoReleaseBundle,
    VideoSpoolResult,
)


class ProviderError(Exception):
    """Base error for metadata providers."""

    pass


class ProviderUnavailableError(ProviderError):
    """Raised when external provider endpoint is unreachable or DNS fails."""

    pass


class ProviderTimeoutError(ProviderError):
    """Raised when external provider request exceeds timeout."""

    pass


class ProviderRateLimitError(ProviderError):
    """Raised when external provider throttles requests (HTTP 429)."""

    pass


@runtime_checkable
class MetadataProviderProtocol(Protocol):
    """Protocol implemented by all external book/audiobook metadata providers."""

    @property
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'openlibrary', 'audnexus')."""
        ...

    def search(
        self,
        title: str,
        author: str | None = None,
        config: ExternalProviderConfig | None = None,
    ) -> list[MetadataMatch]:
        """Query the external service for matching book/audiobook candidates."""
        ...


class MetadataProviderRegistry:
    """Registry mapping provider names to their adapter implementation classes."""

    def __init__(self) -> None:
        self._providers: dict[str, type[MetadataProviderProtocol]] = {}

    def register(self, name: str, provider_cls: type[MetadataProviderProtocol]) -> None:
        self._providers[name.lower()] = provider_cls

    def get(self, name: str) -> type[MetadataProviderProtocol]:
        key = name.lower()
        if key not in self._providers:
            raise KeyError(
                f"Unknown metadata provider '{name}'. Available: {sorted(self._providers.keys())}"
            )
        return self._providers[key]

    def available_providers(self) -> list[str]:
        return sorted(self._providers.keys())


default_provider_registry = MetadataProviderRegistry()


@runtime_checkable
class MusicSpoolEngineProtocol(Protocol):
    """Protocol for depositing music releases into external manager drop folders."""

    def stage_bundle(
        self,
        bundle: MusicReleaseBundle,
        spool_dir: Path,
        dry_run: bool = False,
    ) -> Path:
        """Transfers all tracks and companion assets into a hidden staging folder (.incoming_<name>) on the spool filesystem."""
        ...

    def promote_bundle(
        self,
        staging_dir: Path,
        final_dir: Path,
        dry_run: bool = False,
    ) -> Path:
        """Atomically renames the staging folder to the final release path."""
        ...

    def execute_post_command(
        self,
        command_template: str,
        release_path: Path,
        timeout_seconds: int = 120,
    ) -> tuple[int, str]:
        """Executes a configured post-ingest command returning (exit_code, output)."""
        ...

    def spool_release(
        self,
        bundle: MusicReleaseBundle,
        spool_dir: Path,
        post_command: str | None = None,
        dry_run: bool = False,
    ) -> MusicSpoolResult:
        """Coordinates staging, promotion, and optional post-ingest hook execution."""
        ...


@runtime_checkable
class MusicMetadataProviderProtocol(Protocol):
    """Protocol for external music catalog providers (MusicBrainz, Discogs)."""

    @property
    def provider_name(self) -> str:
        """Return canonical provider identifier (e.g. 'musicbrainz', 'discogs')."""
        ...

    def search_release(
        self,
        artist: str,
        album: str,
        track_count: int | None = None,
        year: int | None = None,
        timeout_seconds: int = 10,
    ) -> list[MusicCatalogMatch]:
        """Query external catalog for matching music releases."""
        ...


@runtime_checkable
class VideoSpoolEngineProtocol(Protocol):
    """Protocol for depositing video releases into external manager drop folders."""

    def stage_bundle(
        self,
        bundle: VideoReleaseBundle,
        spool_dir: Path,
        dry_run: bool = False,
    ) -> Path:
        """Transfers all primary videos and companion assets into a hidden staging folder (.incoming_<name>) on the spool filesystem."""
        ...

    def promote_bundle(
        self,
        staging_dir: Path,
        final_dir: Path,
        dry_run: bool = False,
    ) -> Path | None:
        """Atomically renames the staging folder to the final release path. Returns None if skipped due to collision."""
        ...

    def execute_post_command(
        self,
        command_template: str,
        release_path: Path,
        timeout_seconds: int = 120,
    ) -> tuple[int, str]:
        """Executes a configured post-ingest command returning (exit_code, output)."""
        ...

    def spool_release(
        self,
        bundle: VideoReleaseBundle,
        spool_dir: Path,
        post_command: str | None = None,
        dry_run: bool = False,
    ) -> VideoSpoolResult:
        """Coordinates staging, promotion, and optional post-ingest hook execution."""
        ...


@runtime_checkable
class MediaServerClientProtocol(Protocol):
    """Protocol for media player/server library rescan notifications."""

    @property
    def server_type(self) -> str:
        """Returns the media server identifier: 'jellyfin', 'emby', or 'plex'."""
        ...

    def trigger_rescan(
        self,
        config: MediaServerConfig,
        library_id: str | None = None,
        path: str | None = None,
        dry_run: bool = False,
    ) -> MediaServerRescanResult:
        """Dispatches an authenticated HTTP rescan request to the media server."""
        ...
