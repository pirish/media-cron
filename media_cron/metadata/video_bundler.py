from __future__ import annotations

import hashlib
import re
from pathlib import Path

from media_cron.metadata.models import (
    VideoCompanionAsset,
    VideoCompanionType,
    VideoFormat,
    VideoReleaseBundle,
    VideoTrack,
)

TV_EPISODE_REGEX = re.compile(
    r"^(?P<show>.+?)[. _-]+[sS](?P<season>\d{1,2})[eE](?P<episode>\d{1,3})(?:-[eE]?(?P<episode_end>\d{1,3}))?(?:[. _-]+(?P<title>.*?))?(?:[. _-]+(?P<res>2160p|1080p|720p|480p|4k|uhd))?",
    re.IGNORECASE,
)
MOVIE_REGEX = re.compile(
    r"^(?P<title>.+?)[. _-]+[\(\[]?(?P<year>19\d\d|20\d\d)[\)\]]?(?:[. _-]+(?P<res>2160p|1080p|720p|480p|4k|uhd))?",
    re.IGNORECASE,
)
SAMPLE_REGEX = re.compile(r"\bsample\b", re.IGNORECASE)


class VideoReleaseBundleAggregator:
    """Clusters video tracks, subdirectories, and companion assets into VideoReleaseBundle objects."""

    def __init__(self, sample_size_threshold_mb: int = 50) -> None:
        self.sample_threshold_bytes = sample_size_threshold_mb * 1024 * 1024

    def parse_video_track(self, path: Path) -> VideoTrack:
        """Extracts metadata cues from a video file path."""
        stem = path.stem
        fmt = VideoFormat.from_path(path)
        try:
            file_size = path.stat().st_size if path.exists() else 0
        except OSError:
            file_size = 0

        is_sample = bool(SAMPLE_REGEX.search(stem)) and (file_size < self.sample_threshold_bytes)

        # Resolution detection
        res_match = re.search(r"\b(2160p|1080p|720p|480p|4k|uhd)\b", stem, re.IGNORECASE)
        resolution = res_match.group(1).lower() if res_match else None
        if resolution in ("4k", "uhd"):
            resolution = "2160p"

        # Quality source detection
        source_match = re.search(
            r"\b(bluray|blu-ray|web-dl|webrip|web|hdtv|dvdrip|remux)\b", stem, re.IGNORECASE
        )
        source_quality = source_match.group(1).upper() if source_match else None

        # Codec detection
        codec_match = re.search(r"\b(x265|h265|hevc|x264|h264|av1)\b", stem, re.IGNORECASE)
        video_codec = codec_match.group(1).lower() if codec_match else None

        tv_match = TV_EPISODE_REGEX.match(stem)
        if tv_match:
            show = tv_match.group("show").replace(".", " ").replace("_", " ").strip()
            season = int(tv_match.group("season"))
            episode = int(tv_match.group("episode"))
            end_ep = int(tv_match.group("episode_end")) if tv_match.group("episode_end") else None
            title = tv_match.group("title") or f"Episode {episode}"
            title = title.replace(".", " ").replace("_", " ").strip()
            return VideoTrack(
                path=path,
                title=title,
                file_size=file_size,
                format=fmt,
                show_title=show,
                season_number=season,
                episode_number=episode,
                episode_end_number=end_ep,
                resolution=resolution,
                source_quality=source_quality,
                video_codec=video_codec,
                is_sample=is_sample,
            )

        movie_match = MOVIE_REGEX.match(stem)
        if movie_match:
            title = movie_match.group("title").replace(".", " ").replace("_", " ").strip()
            year = int(movie_match.group("year"))
            return VideoTrack(
                path=path,
                title=title,
                file_size=file_size,
                format=fmt,
                year=year,
                resolution=resolution,
                source_quality=source_quality,
                video_codec=video_codec,
                is_sample=is_sample,
            )

        clean_title = stem.replace(".", " ").replace("_", " ").strip()
        return VideoTrack(
            path=path,
            title=clean_title,
            file_size=file_size,
            format=fmt,
            resolution=resolution,
            source_quality=source_quality,
            video_codec=video_codec,
            is_sample=is_sample,
        )

    def resolve_bundle_root(self, path: Path, base_dir: Path) -> Path:
        """Resolves the top-level release directory under base_dir."""
        if path == base_dir:
            return base_dir
        rel = path.relative_to(base_dir)
        if not rel.parts:
            return base_dir
        return base_dir / rel.parts[0]

    def get_bundle(self, path: Path) -> VideoReleaseBundle | None:
        """Convenience method returning the single bundle for a path, or None."""
        bundles = self.aggregate(path)
        return bundles[0] if bundles else None

    def aggregate(self, target: Path) -> list[VideoReleaseBundle]:
        """Scans a file or directory and groups files into VideoReleaseBundle releases."""
        if not target.exists():
            return []

        if target.is_file():
            fmt = VideoFormat.from_path(target)
            if fmt == VideoFormat.UNKNOWN:
                return []
            track = self.parse_video_track(target)
            if track.is_sample:
                return []
            bundle_id = f"video-{hashlib.sha256(str(target).encode()).hexdigest()[:12]}"
            return [
                VideoReleaseBundle(
                    bundle_id=bundle_id,
                    root_path=target.parent,
                    release_title=track.show_title or track.title,
                    is_series=bool(track.show_title),
                    show_title=track.show_title,
                    season_number=track.season_number,
                    year=track.year,
                    primary_videos=[track],
                    companion_assets=[],
                )
            ]

        all_files = [p for p in target.rglob("*") if p.is_file()]
        if not all_files:
            return []

        # Group by release folder
        # If target itself is a release directory (e.g. contains videos directly or in immediate subdirs)
        bundles_by_root: dict[Path, dict[str, list]] = {}

        # Determine if target is a single release folder or a container of releases
        direct_videos = [
            p
            for p in target.iterdir()
            if p.is_file() and VideoFormat.from_path(p) != VideoFormat.UNKNOWN
        ]
        single_release = bool(direct_videos) or not any(p.is_dir() for p in target.iterdir())

        for file_path in all_files:
            if single_release:
                root = target
            else:
                rel = file_path.relative_to(target)
                root = target / rel.parts[0]

            if root not in bundles_by_root:
                bundles_by_root[root] = {"videos": [], "companions": []}

            fmt = VideoFormat.from_path(file_path)
            if fmt != VideoFormat.UNKNOWN:
                track = self.parse_video_track(file_path)
                if not track.is_sample:
                    bundles_by_root[root]["videos"].append(track)
            else:
                companion_type = VideoCompanionType.from_path(file_path)
                if companion_type != VideoCompanionType.UNKNOWN:
                    asset = VideoCompanionAsset.from_path(file_path)
                    bundles_by_root[root]["companions"].append(asset)

        results: list[VideoReleaseBundle] = []
        for root, data in bundles_by_root.items():
            videos: list[VideoTrack] = data["videos"]
            companions: list[VideoCompanionAsset] = data["companions"]
            if not videos:
                continue

            # Determine title & series cues from primary tracks
            is_series = any(v.show_title is not None for v in videos)
            show_title = next((v.show_title for v in videos if v.show_title), None)
            season_num = next(
                (v.season_number for v in videos if v.season_number is not None), None
            )
            year = next((v.year for v in videos if v.year is not None), None)
            release_title = show_title or (videos[0].title if videos else root.name)

            bundle_id = f"video-{hashlib.sha256(str(root).encode()).hexdigest()[:12]}"
            bundle = VideoReleaseBundle(
                bundle_id=bundle_id,
                root_path=root,
                release_title=release_title,
                is_series=is_series,
                show_title=show_title,
                season_number=season_num,
                year=year,
                primary_videos=videos,
                companion_assets=companions,
            )
            results.append(bundle)

        return results
