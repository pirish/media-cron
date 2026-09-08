import re
from pathlib import Path

from media_cron.models import DiscoveredItem, MediaAsset, MediaCategory
from media_cron.plugins.base import LookupPlugin
from media_cron.plugins.registry import default_registry

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v"}
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".sub", ".vtt"}


class SceneVideoLookup(LookupPlugin):
    """Parses video filenames using scene regex heuristics."""

    @property
    def plugin_name(self) -> str:
        return "scene_video"

    def can_handle(self, item: DiscoveredItem) -> bool:
        return item.source_path.suffix.lower() in VIDEO_EXTENSIONS

    def _find_subtitles(self, video_path: Path) -> list[Path]:
        """Finds matching subtitle files in the same directory."""
        subs = []
        parent = video_path.parent
        stem = video_path.stem
        for p in parent.glob(f"{stem}*"):
            if p.suffix.lower() in SUBTITLE_EXTENSIONS:
                subs.append(p)
        return sorted(subs)

    def _parse_metadata(
        self, filename: str
    ) -> tuple[str, MediaCategory, int | None, str | None, int | None, int | None, str | None]:
        stem = Path(filename).stem

        # Detect resolution
        res_match = re.search(r"\b(2160p|1080p|720p|480p|4k|uhd)\b", stem, re.IGNORECASE)
        resolution = res_match.group(1).lower() if res_match else None

        # Detect TV Series (S01E02 or 1x02)
        tv_match = re.search(
            r"(.*?)(?:[\s._-]+)(?:s|season[\s._-]*)(\d{1,2})[\s._-]*(?:e|ep|episode[\s._-]*)(\d{1,2})",
            stem,
            re.IGNORECASE,
        )
        if not tv_match:
            tv_match = re.search(r"(.*?)(?:[\s._-]+)(\d{1,2})x(\d{1,2})", stem, re.IGNORECASE)

        if tv_match:
            raw_show = tv_match.group(1)
            clean_show = re.sub(r"[\._]", " ", raw_show).strip()
            season = int(tv_match.group(2))
            episode = int(tv_match.group(3))
            clean_title = f"{clean_show} - S{season:02d}E{episode:02d}"
            return (
                clean_title,
                MediaCategory.VIDEO_SERIES,
                None,
                clean_show,
                season,
                episode,
                resolution,
            )

        # Detect Movie (Title + Year)
        year_match = re.search(r"(.*?)(?:[\s._-]+)(19\d{2}|20\d{2})\b", stem, re.IGNORECASE)
        if year_match:
            raw_title = year_match.group(1)
            year = int(year_match.group(2))
            clean_title = re.sub(r"[\._]", " ", raw_title).strip()
            return clean_title, MediaCategory.VIDEO_MOVIE, year, None, None, None, resolution

        # Fallback title cleanup
        cleaned = re.sub(r"[\._]", " ", stem)
        # Remove common scene junk
        cleaned = re.sub(
            r"\b(1080p|720p|2160p|480p|bluray|web-dl|webrip|hdtv|x264|x265|hevc|aac\d*|ddp\d*|atmos|remux|repack|proper)\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        return cleaned or stem, MediaCategory.VIDEO_MOVIE, None, None, None, None, resolution

    def enrich(self, item: DiscoveredItem) -> MediaAsset:
        path = item.source_path
        clean_title, category, year, show, season, ep, res = self._parse_metadata(path.name)
        subs = self._find_subtitles(path)

        return MediaAsset(
            path=path,
            category=category,
            raw_title=path.name,
            clean_title=clean_title,
            extension=path.suffix.lower(),
            file_size=item.file_size,
            year=year,
            series_title=show,
            season_number=season,
            episode_number=ep,
            resolution=res,
            is_valid=True,
            subtitle_files=subs,
        )


# Register default
default_registry.register_lookup("scene_video", SceneVideoLookup)
