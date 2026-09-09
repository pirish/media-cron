from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from media_cron.config import MediaCronConfig, MusicConfig
from media_cron.metadata.models import (
    CompanionAssetType,
    MusicCompanionAsset,
    MusicFormat,
    MusicReleaseBundle,
    MusicTrack,
    MusicWorkflowMode,
)
from media_cron.metadata.music_bundler import DISC_PATTERN, MusicReleaseBundleAggregator
from media_cron.metadata.music_identifier import MusicIdentifier
from media_cron.metadata.music_reader import MusicMetadataReader
from media_cron.metadata.music_spooler import MusicSpoolEngine
from media_cron.models import DiscoveredItem, MediaAsset, MediaCategory
from media_cron.plugins.base import LookupPlugin
from media_cron.plugins.registry import default_registry

logger = logging.getLogger(__name__)

AUDIOBOOK_KEYWORDS = {"audiobook", "audio book", "audiobooks"}


class MusicLookupPlugin(LookupPlugin):
    """Enriches music releases, coordinates drop-folder spooling, and direct library organization."""

    def __init__(
        self,
        config: MusicConfig | None = None,
        bundler: MusicReleaseBundleAggregator | None = None,
        spooler: MusicSpoolEngine | None = None,
        reader: MusicMetadataReader | None = None,
        identifier: MusicIdentifier | None = None,
    ) -> None:
        self.config = config or MusicConfig()
        self.bundler = bundler or MusicReleaseBundleAggregator()
        self.spooler = spooler or MusicSpoolEngine()
        self.reader = reader or MusicMetadataReader()
        self.identifier = identifier or MusicIdentifier(config=self.config)
        self._custom_identifier = identifier is not None
        self.dry_run = False
        self.spooled_bundles: set[str] = set()
        self._identified_bundles: set[str] = set()

        # Telemetry metrics
        self.total_tracks = 0
        self.spooled_releases = 0
        self.organized_tracks = 0
        self.external_matches = 0
        self.confidence_scores: list[float] = []
        self.post_commands_run = 0
        self.errors = 0

    def configure(self, config: Any) -> None:
        """Configures music plugin settings and dry-run flag."""
        if isinstance(config, MusicConfig):
            self.config = config
        elif isinstance(config, MediaCronConfig):
            if hasattr(config, "music") and config.music:
                self.config = config.music
            if hasattr(config, "general") and hasattr(config.general, "dry_run"):
                self.dry_run = config.general.dry_run
        elif hasattr(config, "music") and isinstance(config.music, MusicConfig):
            self.config = config.music
            if hasattr(config, "general") and hasattr(config.general, "dry_run"):
                self.dry_run = config.general.dry_run

        # Auto-detect workflow mode if spool_dir is supplied
        if self.config.spool_dir and self.config.workflow_mode == MusicWorkflowMode.DIRECT:
            # Default to spool if spool_dir is explicitly specified
            self.config.workflow_mode = MusicWorkflowMode.SPOOL

        if not self._custom_identifier:
            self.identifier = MusicIdentifier(config=self.config)

    @property
    def plugin_name(self) -> str:
        return "music"

    def can_handle(self, item: DiscoveredItem) -> bool:
        """Determines if the item is an audio track or companion asset belonging to a music release."""
        if not self.config.enabled:
            return False

        path = item.source_path
        path_str = str(path).lower()

        # Exclude audiobooks
        if path.suffix.lower() == ".m4b" or any(kw in path_str for kw in AUDIOBOOK_KEYWORDS):
            return False

        from media_cron.plugins.lookup.audio import TinyTag

        if TinyTag and path.exists() and path.is_file():
            try:
                tag = TinyTag.get(str(path))
                if tag.genre:
                    g = tag.genre.lower()
                    if any(
                        kw in g
                        for kw in [
                            "audiobook",
                            "audio book",
                            "spoken word",
                            "speech",
                            "audio books",
                        ]
                    ):
                        return False
            except Exception:
                pass

        # Audio files
        fmt = MusicFormat.from_path(path)
        if fmt != MusicFormat.UNKNOWN:
            return True

        # Companion files
        if self.config.preserve_companions:
            asset_type = CompanionAssetType.from_path(path)
            if asset_type in (
                CompanionAssetType.COVER_ART,
                CompanionAssetType.CUE_SHEET,
                CompanionAssetType.RIP_LOG,
                CompanionAssetType.PLAYLIST,
            ):
                root = self.bundler.resolve_bundle_root(path)
                # Ensure directory contains audio files
                if any(
                    MusicFormat.from_path(p) != MusicFormat.UNKNOWN
                    for p in root.rglob("*")
                    if p.is_file()
                ):
                    return True

        return False

    def enrich(self, item: DiscoveredItem) -> MediaAsset:
        """Processes an item and coordinates bundle spooling or direct tag extraction."""
        path = item.source_path
        ext = path.suffix.lower()
        fmt = MusicFormat.from_path(path)
        is_audio = fmt != MusicFormat.UNKNOWN

        if is_audio:
            self.total_tracks += 1

        bundle = self.bundler.get_bundle(path)

        # External catalog lookup cascade if enabled
        if self.config.enable_external_lookup and bundle:
            if bundle.bundle_id not in self._identified_bundles:
                self._identified_bundles.add(bundle.bundle_id)
                artist = bundle.album_artist
                album = bundle.album_title
                track_count = len(bundle.tracks) if bundle.tracks else None
                year = bundle.year

                if (artist and artist != "Unknown Artist") or (album and album != "Unknown Album"):
                    try:
                        match = self.identifier.identify(
                            artist=artist,
                            album=album,
                            track_count=track_count,
                            year=year,
                        )
                        if match:
                            bundle.matched_catalog = match
                            bundle.confidence = match.confidence
                            self.external_matches += 1
                            self.confidence_scores.append(match.confidence)
                            if match.year:
                                bundle.year = match.year
                            if match.title and (
                                not bundle.album_title or bundle.album_title == "Unknown Album"
                            ):
                                bundle.album_title = match.title
                            if match.artist and (
                                not bundle.album_artist or bundle.album_artist == "Unknown Artist"
                            ):
                                bundle.album_artist = match.artist
                    except Exception as e:
                        logger.debug(f"External music catalog identification failed: {e}")

        if self.config.workflow_mode in (MusicWorkflowMode.SPOOL, MusicWorkflowMode.HYBRID):
            if bundle and bundle.bundle_id not in self.spooled_bundles:
                self.spooled_bundles.add(bundle.bundle_id)
                if self.config.spool_dir:
                    if self.dry_run:
                        self.spooled_releases += 1
                        if self.config.post_ingest_command:
                            self.post_commands_run += 1
                    else:
                        spool_result = self.spooler.spool_release(
                            bundle=bundle,
                            spool_dir=self.config.spool_dir,
                            post_command=self.config.post_ingest_command,
                            dry_run=False,
                        )
                        if spool_result.success:
                            self.spooled_releases += 1
                            if spool_result.post_command_executed:
                                self.post_commands_run += 1
                        else:
                            self.errors += 1
                            logger.error(
                                f"Failed to spool release {bundle.album_title}: {spool_result.error}"
                            )

            album_title = bundle.album_title if bundle else path.parent.name
            album_artist = bundle.album_artist if bundle else "Unknown Artist"
            year = bundle.year if bundle else None

            return MediaAsset(
                path=path,
                category=MediaCategory.AUDIO_MUSIC,
                raw_title=path.name,
                clean_title=path.stem,
                extension=ext,
                file_size=item.file_size,
                year=year,
                artist=album_artist,
                album=album_title,
                is_valid=True,
            )

        # Direct organization mode
        dest_rel: Path | None = None
        if is_audio:
            self.organized_tracks += 1
            track = self.reader.read(path)
            dest_rel = self.format_destination_path(track, bundle)
            return MediaAsset(
                path=path,
                category=MediaCategory.AUDIO_MUSIC,
                raw_title=path.name,
                clean_title=track.title,
                extension=ext,
                file_size=item.file_size,
                year=track.year or (bundle.year if bundle else None),
                artist=track.artist or (bundle.album_artist if bundle else "Unknown Artist"),
                album=track.album or (bundle.album_title if bundle else "Unknown Album"),
                track_number=track.track_number,
                destination_rel_path=dest_rel,
                is_valid=True,
            )
        else:
            # Companion asset
            if bundle:
                companion = MusicCompanionAsset(
                    path=path,
                    asset_type=CompanionAssetType.from_path(path),
                    file_size=item.file_size,
                )
                dest_rel = self.format_companion_destination_path(companion, bundle)

            return MediaAsset(
                path=path,
                category=MediaCategory.AUDIO_MUSIC,
                raw_title=path.name,
                clean_title=path.stem,
                extension=ext,
                file_size=item.file_size,
                year=bundle.year if bundle else None,
                artist=bundle.album_artist if bundle else "Unknown Artist",
                album=bundle.album_title if bundle else "Unknown Album",
                destination_rel_path=dest_rel,
                is_valid=True,
            )

    def format_destination_path(
        self,
        track: MusicTrack,
        bundle: MusicReleaseBundle | None = None,
    ) -> Path:
        """Formats the direct library destination relative path for a track."""
        if bundle and bundle.is_compilation:
            album_artist = self.config.compilation_artist or "Various Artists"
        else:
            album_artist = (
                (bundle.album_artist if bundle else track.album_artist)
                or track.artist
                or "Unknown Artist"
            )

        album = (bundle.album_title if bundle else track.album) or "Unknown Album"
        year = (bundle.year if bundle else track.year) or track.year

        year_suffix = f" ({year})" if year else ""
        album_folder = f"{album}{year_suffix}"

        track_num = track.track_number or 1
        filename = f"{track_num:02d} - {track.title}{track.path.suffix}"

        library_dir = self.config.library_dir or "Music"
        total_discs = bundle.total_discs if bundle else 1
        disc_num = track.disc_number or 1

        if total_discs > 1 or disc_num > 1:
            disc_folder = f"CD{disc_num}"
            return Path(library_dir) / album_artist / album_folder / disc_folder / filename

        return Path(library_dir) / album_artist / album_folder / filename

    def format_companion_destination_path(
        self,
        companion: MusicCompanionAsset,
        bundle: MusicReleaseBundle,
    ) -> Path:
        """Formats the direct library destination relative path for companion assets."""
        if bundle.is_compilation:
            album_artist = self.config.compilation_artist or "Various Artists"
        else:
            album_artist = bundle.album_artist or "Unknown Artist"

        year_suffix = f" ({bundle.year})" if bundle.year else ""
        album_folder = f"{bundle.album_title}{year_suffix}"
        library_dir = self.config.library_dir or "Music"

        parent_name = companion.path.parent.name
        if DISC_PATTERN.match(parent_name):
            return (
                Path(library_dir) / album_artist / album_folder / parent_name / companion.path.name
            )

        return Path(library_dir) / album_artist / album_folder / companion.path.name

    def get_summary(self) -> dict[str, Any]:
        """Returns aggregated telemetry dictionary for BatchSummary.music_summary."""
        avg_conf = (
            sum(self.confidence_scores) / len(self.confidence_scores)
            if self.confidence_scores
            else 1.0
        )
        return {
            "total_tracks": self.total_tracks,
            "releases_bundled": len(self.bundler._bundle_cache),
            "spooled_releases": self.spooled_releases,
            "organized_tracks": self.organized_tracks,
            "external_matches": self.external_matches,
            "average_confidence": round(avg_conf, 2),
            "post_commands_run": self.post_commands_run,
            "errors": self.errors,
        }


default_registry.register_lookup("music", MusicLookupPlugin)
