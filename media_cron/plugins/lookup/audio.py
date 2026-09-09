from __future__ import annotations

import re

from media_cron.config import AudiobookConfig
from media_cron.metadata.aggregator import AudiobookBundleAggregator
from media_cron.metadata.identifier import AudiobookIdentifier
from media_cron.models import DiscoveredItem, MediaAsset, MediaCategory
from media_cron.plugins.base import LookupPlugin
from media_cron.plugins.registry import default_registry

try:
    from tinytag import TinyTag
except ImportError:
    TinyTag = None

AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".m4b", ".aac", ".ogg", ".opus", ".wav"}


class AudioTagLookup(LookupPlugin):
    """Extracts audio metadata using TinyTag and external audiobook services with regex fallback."""

    def __init__(
        self,
        identifier: AudiobookIdentifier | None = None,
        aggregator: AudiobookBundleAggregator | None = None,
    ) -> None:
        if aggregator is not None:
            self.aggregator = aggregator
            self.identifier = aggregator.identifier
        else:
            self.identifier = identifier or AudiobookIdentifier()
            self.aggregator = AudiobookBundleAggregator(identifier=self.identifier)

    def configure(self, config: AudiobookConfig) -> None:
        """Reconfigures the underlying identifier and aggregator with pipeline configuration."""
        self.identifier.config = config
        if hasattr(self, "aggregator"):
            self.aggregator.identifier.config = config
            self.aggregator._bundle_cache.clear()

    @property
    def plugin_name(self) -> str:
        return "audio_tag"

    def can_handle(self, item: DiscoveredItem) -> bool:
        return item.source_path.suffix.lower() in AUDIO_EXTENSIONS

    def enrich(self, item: DiscoveredItem) -> MediaAsset:
        path = item.source_path
        ext = path.suffix.lower()

        artist: str | None = None
        album: str | None = None
        title: str | None = None
        track: int | None = None
        year: int | None = None
        bitrate: int | None = None
        genre: str | None = None

        if TinyTag and path.exists():
            try:
                tag = TinyTag.get(str(path))
                artist = tag.artist or tag.albumartist
                album = tag.album
                title = tag.title
                track = tag.track
                genre = tag.genre
                if tag.year:
                    try:
                        year = int(str(tag.year)[:4])
                    except (ValueError, TypeError):
                        pass
                if tag.bitrate:
                    bitrate = int(tag.bitrate)
            except Exception:
                pass

        # Check if audiobook per FR-013
        is_audiobook = False
        if ext == ".m4b":
            is_audiobook = True
        elif any(kw in str(path).lower() for kw in ["audiobook", "audio book", "audiobooks"]):
            is_audiobook = True
        elif genre:
            genre_lower = genre.lower()
            if any(
                kw in genre_lower
                for kw in ["audiobook", "audio book", "spoken word", "speech", "audio books"]
            ):
                is_audiobook = True

        category = MediaCategory.AUDIO_BOOK if is_audiobook else MediaCategory.AUDIO_MUSIC

        if is_audiobook:
            if self.aggregator.is_multi_file_bundle(path):
                bundle = self.aggregator.get_bundle(path)
                match = bundle.matched_metadata
                if not track:
                    stem_match = re.match(r"^(?:(\d+)[\s._-]+)?", path.stem)
                    if stem_match and stem_match.group(1):
                        try:
                            track = int(stem_match.group(1))
                        except ValueError:
                            pass
            else:
                has_local_tags = bool(title or artist)
                query_title = title or album
                query_author = artist

                if not query_title:
                    parsed_title, parsed_author = self.identifier.parse_filename(path.stem)
                    query_title = parsed_title
                    if not query_author:
                        query_author = parsed_author

                match = self.identifier.identify(
                    title=query_title,
                    author=query_author,
                    year=year,
                    has_local_tags=has_local_tags,
                    path=path,
                )

            return MediaAsset(
                path=path,
                category=category,
                raw_title=path.name,
                clean_title=match.title,
                extension=ext,
                file_size=item.file_size,
                year=match.year or year,
                artist=artist,
                album=album,
                track_number=track,
                author=match.author,
                narrator=match.narrator,
                series_title=match.series,
                volume=match.volume,
                bitrate_kbps=bitrate,
                confidence=match.confidence,
                identification_source=match.provider,
                is_valid=True,
            )

        # Standard music fallback to filename parsing
        if not title:
            stem = path.stem
            match_re = re.match(r"^(?:(\d+)[\s._-]+)?(?:(.*?)\s*[\s._-]+)?([^-_.].*)$", stem)
            if match_re:
                if match_re.group(1) and not track:
                    try:
                        track = int(match_re.group(1))
                    except ValueError:
                        pass
                if match_re.group(2) and not artist:
                    artist = re.sub(r"[._]", " ", match_re.group(2)).strip()
                title = re.sub(r"[._]", " ", match_re.group(3)).strip()
            else:
                title = re.sub(r"[._]", " ", stem).strip()

        return MediaAsset(
            path=path,
            category=category,
            raw_title=path.name,
            clean_title=title or path.stem,
            extension=ext,
            file_size=item.file_size,
            year=year,
            artist=artist,
            album=album,
            track_number=track,
            author=None,
            bitrate_kbps=bitrate,
            is_valid=True,
        )


default_registry.register_lookup("audio_tag", AudioTagLookup)
