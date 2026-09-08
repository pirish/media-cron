import re

from media_cron.models import DiscoveredItem, MediaAsset, MediaCategory
from media_cron.plugins.base import LookupPlugin
from media_cron.plugins.registry import default_registry

try:
    from tinytag import TinyTag
except ImportError:
    TinyTag = None

AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".m4b", ".aac", ".ogg", ".opus", ".wav"}


class AudioTagLookup(LookupPlugin):
    """Extracts audio metadata using TinyTag with regex fallback."""

    @property
    def plugin_name(self) -> str:
        return "audio_tag"

    def can_handle(self, item: DiscoveredItem) -> bool:
        return item.source_path.suffix.lower() in AUDIO_EXTENSIONS

    def enrich(self, item: DiscoveredItem) -> MediaAsset:
        path = item.source_path
        ext = path.suffix.lower()
        is_audiobook = ext == ".m4b" or "audiobook" in str(path).lower()
        category = MediaCategory.AUDIO_BOOK if is_audiobook else MediaCategory.AUDIO_MUSIC

        artist: str | None = None
        album: str | None = None
        title: str | None = None
        track: int | None = None
        year: int | None = None
        bitrate: int | None = None

        if TinyTag and path.exists():
            try:
                tag = TinyTag.get(str(path))
                artist = tag.artist or tag.albumartist
                album = tag.album
                title = tag.title
                track = tag.track
                if tag.year:
                    try:
                        year = int(str(tag.year)[:4])
                    except (ValueError, TypeError):
                        pass
                if tag.bitrate:
                    bitrate = int(tag.bitrate)
            except Exception:
                pass

        # Fallback to filename parsing
        if not title:
            stem = path.stem
            # Pattern: 01 - Artist - Title or 01. Title
            match = re.match(r"^(?:(\d+)[\s._-]+)?(?:(.*?)\s*[\s._-]+)?([^-_.].*)$", stem)
            if match:
                if match.group(1) and not track:
                    try:
                        track = int(match.group(1))
                    except ValueError:
                        pass
                if match.group(2) and not artist:
                    artist = re.sub(r"[._]", " ", match.group(2)).strip()
                title = re.sub(r"[._]", " ", match.group(3)).strip()
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
            author=artist if is_audiobook else None,
            bitrate_kbps=bitrate,
            is_valid=True,
        )


default_registry.register_lookup("audio_tag", AudioTagLookup)
