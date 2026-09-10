from __future__ import annotations

import re
from pathlib import Path

from media_cron.models import DiscoveredItem, MediaAsset, MediaCategory
from media_cron.plugins.base import LookupPlugin
from media_cron.plugins.registry import default_registry

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v"}
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".sub", ".vtt"}

ISO_LANG_MAP = {
    "en": "en",
    "eng": "en",
    "english": "en",
    "es": "es",
    "spa": "es",
    "spanish": "es",
    "fr": "fr",
    "fra": "fr",
    "fre": "fr",
    "french": "fr",
    "de": "de",
    "deu": "de",
    "ger": "de",
    "german": "de",
    "it": "it",
    "ita": "it",
    "italian": "it",
    "ja": "ja",
    "jpn": "ja",
    "japanese": "ja",
    "zh": "zh",
    "chi": "zh",
    "zho": "zh",
    "chinese": "zh",
    "pt": "pt",
    "por": "pt",
    "portuguese": "pt",
    "ru": "ru",
    "rus": "ru",
    "russian": "ru",
    "ko": "ko",
    "kor": "ko",
    "korean": "ko",
    "ar": "ar",
    "ara": "ar",
    "arabic": "ar",
    "hi": "hi",
    "hin": "hi",
    "hindi": "hi",
    "nl": "nl",
    "dut": "nl",
    "dutch": "nl",
    "sv": "sv",
    "swe": "sv",
    "swedish": "sv",
    "no": "no",
    "nor": "no",
    "norwegian": "no",
    "da": "da",
    "dan": "da",
    "danish": "da",
    "fi": "fi",
    "fin": "fi",
    "finnish": "fi",
    "pl": "pl",
    "pol": "pl",
    "polish": "pl",
}

MODIFIER_TAGS = {"forced", "sdh", "cc", "commentary", "hi"}


class SceneVideoLookup(LookupPlugin):
    """Parses video filenames using scene regex heuristics."""

    @property
    def plugin_name(self) -> str:
        return "scene_video"

    def can_handle(self, item: DiscoveredItem) -> bool:
        return item.source_path.suffix.lower() in VIDEO_EXTENSIONS

    def _find_subtitles(self, video_path: Path) -> list[Path]:
        """Finds matching subtitle files in the same directory or Subs/ subdirectories."""
        subs: set[Path] = set()
        parent = video_path.parent
        stem = video_path.stem

        if parent.exists() and parent.is_dir():
            # Check for direct sibling subtitles
            all_video_siblings = [
                p for p in parent.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
            ]
            is_lone_video = len(all_video_siblings) <= 1

            for p in parent.iterdir():
                if p.is_file() and p.suffix.lower() in SUBTITLE_EXTENSIONS:
                    if is_lone_video or p.name.startswith(stem):
                        subs.add(p)

            # Check for Subs / Subtitles subdirectories
            for subs_dir_name in ("Subs", "subs", "Subtitles", "subtitles"):
                subs_dir = parent / subs_dir_name
                if subs_dir.exists() and subs_dir.is_dir():
                    for p in subs_dir.glob("*"):
                        if p.is_file() and p.suffix.lower() in SUBTITLE_EXTENSIONS:
                            subs.add(p)

        return sorted(subs)

    def format_subtitle_destination(self, base_dest: Path, sub_path: Path) -> Path:
        """Formats sidecar subtitle destination keeping language and modifier tags intact."""
        stem = sub_path.stem
        tokens = re.split(r"[._ -]", stem)
        tags: list[str] = []

        # Check from right to left for modifier and language tags
        for tok in reversed(tokens):
            tok_lower = tok.lower()
            if tok_lower in MODIFIER_TAGS:
                tags.append(tok_lower)
            elif tok_lower in ISO_LANG_MAP:
                tags.append(ISO_LANG_MAP[tok_lower])
            elif tok_lower in (
                "2160p",
                "1080p",
                "720p",
                "480p",
                "4k",
                "uhd",
                "bluray",
                "webdl",
                "web-dl",
                "webrip",
                "hdtv",
                "x264",
                "x265",
                "hevc",
                "av1",
                "dvdrip",
                "remux",
            ):
                break
            elif tok_lower.isdigit() or not tok_lower:
                continue
            else:
                break

        tags.reverse()
        tag_suffix = ("." + ".".join(tags)) if tags else ""
        return base_dest.parent / f"{base_dest.stem}{tag_suffix}{sub_path.suffix.lower()}"

    def _parse_metadata(
        self, filename: str
    ) -> tuple[
        str, MediaCategory, int | None, str | None, int | None, int | None, int | None, str | None
    ]:
        stem = Path(filename).stem

        # Detect resolution
        res_match = re.search(r"\b(2160p|1080p|720p|480p|4k|uhd)\b", stem, re.IGNORECASE)
        resolution = res_match.group(1).lower() if res_match else None
        if resolution in ("4k", "uhd"):
            resolution = "2160p"

        # Detect TV Series (S01E02, S01E01-E02, 1x02, 1x01-02)
        tv_match = re.search(
            r"^(?P<show>.+?)[. _-]+(?:[sS]|season[. _-]*)(?P<season>\d{1,2})[. _-]*(?:[eE]|ep|episode[. _-]*)(?P<episode>\d{1,3})(?:-[eE]?(?P<episode_end>\d{1,3}))?(?:[. _-]+(?P<title>.*?))?(?:[. _-]+(?:2160p|1080p|720p|480p|4k|uhd))?$",
            stem,
            re.IGNORECASE,
        )
        if not tv_match:
            tv_match = re.search(
                r"^(?P<show>.+?)[. _-]+(?P<season>\d{1,2})x(?P<episode>\d{1,2})(?:-(?P<episode_end>\d{1,2}))?(?:[. _-]+(?P<title>.*?))?(?:[. _-]+(?:2160p|1080p|720p|480p|4k|uhd))?$",
                stem,
                re.IGNORECASE,
            )

        if tv_match:
            raw_show = tv_match.group("show")
            clean_show = re.sub(r"[\._]", " ", raw_show).strip(" ()[]")
            season = int(tv_match.group("season"))
            episode = int(tv_match.group("episode"))
            end_ep = int(tv_match.group("episode_end")) if tv_match.group("episode_end") else None
            ep_title = tv_match.group("title")
            if ep_title:
                cleaned_ep = re.sub(r"[\._]", " ", ep_title)
                cleaned_ep = re.sub(
                    r"\b(1080p|720p|2160p|480p|4k|uhd|bluray|web-dl|webrip|hdtv|x264|x265|hevc|aac\d*|ddp\d*|atmos|remux|repack|proper)\b.*$",
                    "",
                    cleaned_ep,
                    flags=re.IGNORECASE,
                ).strip(" ()[]-")
            else:
                cleaned_ep = ""

            clean_title = cleaned_ep if cleaned_ep else f"S{season:02d}E{episode:02d}"
            return (
                clean_title,
                MediaCategory.VIDEO_SERIES,
                None,
                clean_show,
                season,
                episode,
                end_ep,
                resolution,
            )

        # Detect Movie (Title + Year)
        year_match = re.search(
            r"^(?P<title>.+?)[. _-]+[\(\[]?(?P<year>19\d\d|20\d\d)[\)\]]?", stem, re.IGNORECASE
        )
        if year_match:
            raw_title = year_match.group("title")
            year = int(year_match.group("year"))
            clean_title = re.sub(r"[\._]", " ", raw_title).strip(" ()[]")
            return clean_title, MediaCategory.VIDEO_MOVIE, year, None, None, None, None, resolution

        # Fallback title cleanup
        cleaned = re.sub(r"[\._]", " ", stem)
        cleaned = re.sub(
            r"\b(1080p|720p|2160p|480p|4k|uhd|bluray|web-dl|webrip|hdtv|x264|x265|hevc|aac\d*|ddp\d*|atmos|remux|repack|proper)\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ()[]")
        return cleaned or stem, MediaCategory.VIDEO_MOVIE, None, None, None, None, None, resolution

    def enrich(self, item: DiscoveredItem) -> MediaAsset:
        path = item.source_path
        clean_title, category, year, show, season, ep, end_ep, res = self._parse_metadata(path.name)
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
            episode_end_number=end_ep,
            resolution=res,
            is_valid=True,
            subtitle_files=subs,
        )


default_registry.register_lookup("scene_video", SceneVideoLookup)
