from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

from media_cron.metadata.models import (
    CompanionAssetType,
    MusicCompanionAsset,
    MusicFormat,
    MusicReleaseBundle,
    MusicTrack,
)

try:
    from tinytag import TinyTag
except ImportError:
    TinyTag = None

DISC_PATTERN = re.compile(r"^(?:cd|disc|disk)\s*(\d+)?$", re.IGNORECASE)


class MusicReleaseBundleAggregator:
    """Clusters tracks, disc subdirectories, and companion assets into MusicReleaseBundle objects."""

    def __init__(self) -> None:
        self._bundle_cache: dict[Path, MusicReleaseBundle] = {}

    def is_disc_folder(self, path: Path) -> bool:
        """Determines if a folder is a multi-disc subfolder (e.g. CD1, Disc 2)."""
        return bool(DISC_PATTERN.match(path.name))

    def resolve_bundle_root(self, path: Path) -> Path:
        """Traverses up from disc subfolders or audio files to locate the release root directory."""
        curr = path if path.is_dir() else path.parent
        if self.is_disc_folder(curr):
            return curr.parent
        return curr

    def _parse_folder_name(self, folder_name: str) -> tuple[str | None, str, int | None]:
        """Parses artist, album, and year from directory names like 'Artist - Album (Year)'."""
        year: int | None = None
        # Extract 4-digit year in parentheses or brackets e.g. (1977)
        year_match = re.search(r"[\(\[](\d{4})[\)\]]", folder_name)
        cleaned = folder_name
        if year_match:
            try:
                year = int(year_match.group(1))
                cleaned = re.sub(r"[\(\[]\d{4}[\)\]]", "", cleaned).strip()
            except ValueError:
                pass

        if " - " in cleaned:
            parts = cleaned.split(" - ", 1)
            artist = parts[0].strip()
            album = parts[1].strip()
            return artist, album, year
        return None, cleaned.strip(), year

    def aggregate(self, directory: Path) -> list[MusicReleaseBundle]:
        """Scans a directory and groups tracks into MusicReleaseBundle releases."""
        if not directory.exists():
            return []

        # Find all files recursively
        all_files = (
            [p for p in directory.rglob("*") if p.is_file()] if directory.is_dir() else [directory]
        )

        # Filter audio files
        audio_files: list[Path] = []
        companion_files: list[Path] = []
        for p in all_files:
            fmt = MusicFormat.from_path(p)
            if fmt != MusicFormat.UNKNOWN:
                audio_files.append(p)
            else:
                asset_type = CompanionAssetType.from_path(p)
                if asset_type in (
                    CompanionAssetType.COVER_ART,
                    CompanionAssetType.CUE_SHEET,
                    CompanionAssetType.RIP_LOG,
                    CompanionAssetType.PLAYLIST,
                ):
                    companion_files.append(p)

        if not audio_files:
            return []

        # Group audio files and companion files by bundle root
        bundles_by_root: dict[Path, dict[str, list[Path]]] = {}
        for af in audio_files:
            root = self.resolve_bundle_root(af)
            if root not in bundles_by_root:
                bundles_by_root[root] = {"audio": [], "companion": []}
            bundles_by_root[root]["audio"].append(af)

        for cf in companion_files:
            root = self.resolve_bundle_root(cf)
            if root in bundles_by_root:
                bundles_by_root[root]["companion"].append(cf)
            else:
                # If companion is in directory, assign to the closest root
                for r in bundles_by_root:
                    if cf.is_relative_to(r):
                        bundles_by_root[r]["companion"].append(cf)
                        break

        results: list[MusicReleaseBundle] = []
        for root, files in bundles_by_root.items():
            if root in self._bundle_cache:
                results.append(self._bundle_cache[root])
                continue

            tracks: list[MusicTrack] = []
            disc_numbers: set[int] = set()
            album_titles: list[str] = []
            artists: list[str] = []
            years: list[int] = []
            genres: list[str] = []

            for af in sorted(files["audio"]):
                fmt = MusicFormat.from_path(af)
                file_size = af.stat().st_size if af.exists() else 0
                title = af.stem
                artist = ""
                album = ""
                album_artist: str | None = None
                track_num: int | None = None
                disc_num: int | None = None
                year: int | None = None
                genre: str | None = None
                duration: float | None = None
                bitrate: int | None = None

                # Check if file is inside a disc subfolder (e.g. CD1, Disc 2)
                parent = af.parent
                if self.is_disc_folder(parent):
                    disc_m = DISC_PATTERN.match(parent.name)
                    if disc_m and disc_m.group(1):
                        try:
                            disc_num = int(disc_m.group(1))
                            disc_numbers.add(disc_num)
                        except ValueError:
                            pass

                if TinyTag and af.exists():
                    try:
                        tag = TinyTag.get(str(af))
                        if tag.title:
                            title = tag.title
                        if tag.artist:
                            artist = tag.artist
                        if tag.albumartist:
                            album_artist = tag.albumartist
                        if tag.album:
                            album = tag.album
                        if tag.track:
                            track_num = int(tag.track)
                        if tag.disc:
                            disc_num = int(tag.disc)
                            disc_numbers.add(disc_num)
                        if tag.year:
                            try:
                                year = int(str(tag.year)[:4])
                            except (ValueError, TypeError):
                                pass
                        if tag.genre:
                            genre = tag.genre
                        if tag.duration:
                            duration = float(tag.duration)
                        if tag.bitrate:
                            bitrate = int(tag.bitrate)
                    except Exception:
                        pass

                if not track_num:
                    track_m = re.match(r"^(\d+)[\s._-]+", af.stem)
                    if track_m:
                        try:
                            track_num = int(track_m.group(1))
                        except ValueError:
                            pass

                if album:
                    album_titles.append(album)
                if artist:
                    artists.append(artist)
                if year:
                    years.append(year)
                if genre:
                    genres.append(genre)

                tracks.append(
                    MusicTrack(
                        path=af,
                        format=fmt,
                        file_size=file_size,
                        title=title,
                        artist=artist or "Unknown Artist",
                        album=album or "Unknown Album",
                        album_artist=album_artist,
                        track_number=track_num,
                        disc_number=disc_num or 1,
                        year=year,
                        genre=genre,
                        duration_seconds=duration,
                        bitrate_kbps=bitrate,
                    )
                )

            # Build companion assets
            companions: list[MusicCompanionAsset] = []
            for cf in sorted(files["companion"]):
                asset_type = CompanionAssetType.from_path(cf)
                file_size = cf.stat().st_size if cf.exists() else 0
                companions.append(
                    MusicCompanionAsset(
                        path=cf,
                        asset_type=asset_type,
                        file_size=file_size,
                    )
                )

            # Consensus metadata
            parsed_artist, parsed_album, parsed_year = self._parse_folder_name(root.name)
            final_album = (
                Counter(album_titles).most_common(1)[0][0] if album_titles else parsed_album
            )
            final_artist = (
                Counter(artists).most_common(1)[0][0]
                if artists
                else (parsed_artist or "Unknown Artist")
            )
            final_year = Counter(years).most_common(1)[0][0] if years else parsed_year
            final_genre = Counter(genres).most_common(1)[0][0] if genres else None

            distinct_artists = {
                t.artist for t in tracks if t.artist and t.artist != "Unknown Artist"
            }
            is_compilation = len(distinct_artists) > 1 or final_artist.lower() in (
                "various artists",
                "various",
            )

            total_discs = max(max(disc_numbers, default=1), 1)

            bundle_id = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
            bundle = MusicReleaseBundle(
                bundle_id=bundle_id,
                root_path=root,
                album_title=final_album,
                album_artist=final_artist,
                tracks=tracks,
                companion_assets=companions,
                year=final_year,
                genre=final_genre,
                is_compilation=is_compilation,
                total_discs=total_discs,
            )
            self._bundle_cache[root] = bundle
            results.append(bundle)

        return results

    def get_bundle(self, path: Path) -> MusicReleaseBundle | None:
        """Retrieves cached or newly computed bundle containing path."""
        root = self.resolve_bundle_root(path)
        if root in self._bundle_cache:
            return self._bundle_cache[root]
        bundles = self.aggregate(root)
        return bundles[0] if bundles else None
