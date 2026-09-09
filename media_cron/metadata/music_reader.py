from __future__ import annotations

import re
from pathlib import Path

from media_cron.metadata.models import MusicFormat, MusicTrack

try:
    from tinytag import TinyTag
except ImportError:
    TinyTag = None

DISC_PATTERN = re.compile(r"^(?:cd|disc|disk)\s*(\d+)?$", re.IGNORECASE)


class MusicMetadataReader:
    """Extracts embedded tags from audio tracks with regex filename parsing fallback."""

    def read(self, path: Path) -> MusicTrack:
        """Reads metadata from an audio file and returns a structured MusicTrack entity."""
        fmt = MusicFormat.from_path(path)
        file_size = path.stat().st_size if path.exists() else 0

        title: str | None = None
        artist: str | None = None
        album: str | None = None
        album_artist: str | None = None
        track_number: int | None = None
        disc_number: int | None = None
        year: int | None = None
        genre: str | None = None
        duration: float | None = None
        bitrate: int | None = None

        # 1. Attempt embedded tag extraction via TinyTag
        if TinyTag and path.exists():
            try:
                tag = TinyTag.get(str(path))
                if tag.title:
                    title = tag.title.strip()
                if tag.artist:
                    artist = tag.artist.strip()
                if tag.albumartist:
                    album_artist = tag.albumartist.strip()
                if tag.album:
                    album = tag.album.strip()
                if tag.track:
                    try:
                        track_number = int(str(tag.track).split("/")[0])
                    except (ValueError, TypeError):
                        pass
                if tag.disc:
                    try:
                        disc_number = int(str(tag.disc).split("/")[0])
                    except (ValueError, TypeError):
                        pass
                if tag.year:
                    try:
                        year = int(str(tag.year)[:4])
                    except (ValueError, TypeError):
                        pass
                if tag.genre:
                    genre = tag.genre.strip()
                if tag.duration:
                    duration = float(tag.duration)
                if tag.bitrate:
                    bitrate = int(tag.bitrate)
            except Exception:
                pass

        # 2. Disc number detection from directory structure (e.g. CD1, Disc 2)
        if disc_number is None:
            parent_match = DISC_PATTERN.match(path.parent.name)
            if parent_match and parent_match.group(1):
                try:
                    disc_number = int(parent_match.group(1))
                except ValueError:
                    pass

        # 3. Regex filename heuristics for missing tags
        stem = path.stem
        if not track_number:
            track_match = re.match(r"^(\d+)[\s._-]+", stem)
            if track_match:
                try:
                    track_number = int(track_match.group(1))
                except ValueError:
                    pass

        if not title or not artist:
            # Pattern: "01 - Artist - Title" or "01 - Title" or "Artist - Title"
            m_triple = re.match(r"^(?:(\d+)[\s._-]+)?(?:(.*?)\s*-\s*)?([^-]+)$", stem)
            if m_triple:
                g_num, g_art, g_tit = m_triple.groups()
                if not track_number and g_num:
                    try:
                        track_number = int(g_num)
                    except ValueError:
                        pass
                if not artist and g_art:
                    artist = g_art.strip()
                if not title and g_tit:
                    title = g_tit.strip()

        if not title:
            # Strip leading track digits from stem
            cleaned_title = re.sub(r"^\d+[\s._-]+", "", stem).strip()
            title = cleaned_title if cleaned_title else stem

        return MusicTrack(
            path=path,
            format=fmt,
            file_size=file_size,
            title=title,
            artist=artist or "Unknown Artist",
            album=album or "Unknown Album",
            album_artist=album_artist or artist,
            track_number=track_number,
            disc_number=disc_number or 1,
            year=year,
            genre=genre,
            duration_seconds=duration,
            bitrate_kbps=bitrate,
            is_valid=True,
        )
