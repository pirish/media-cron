import re
from collections import Counter
from pathlib import Path

from media_cron.metadata.identifier import AudiobookIdentifier
from media_cron.metadata.models import AudiobookBundle

try:
    from tinytag import TinyTag
except ImportError:
    TinyTag = None

AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".m4b", ".aac", ".ogg", ".opus", ".wav"}


class AudiobookBundleAggregator:
    """Aggregates multi-file chapter tracks and disc subfolders into cohesive AudiobookBundle works."""

    DISC_PATTERN = re.compile(r"^(?:cd|disc|part|disk)\s*(\d+)?$", re.IGNORECASE)

    def __init__(self, identifier: AudiobookIdentifier | None = None) -> None:
        self.identifier = identifier or AudiobookIdentifier()
        self._bundle_cache: dict[Path, AudiobookBundle] = {}

    def is_disc_folder(self, path: Path) -> bool:
        """Determines if a directory represents a disc/part subfolder (e.g., CD1, Disc 2)."""
        return bool(self.DISC_PATTERN.match(path.name))

    def resolve_bundle_root(self, file_path: Path) -> Path:
        """Resolves the top-level audiobook folder, traversing up from disc subfolders if present."""
        parent = file_path.parent
        if self.is_disc_folder(parent):
            return parent.parent
        return parent

    def find_audio_files(self, directory: Path) -> list[Path]:
        """Finds all audio files within a directory and its subdirectories."""
        audio_files = []
        if not directory.exists() or not directory.is_dir():
            return []
        for p in directory.rglob("*"):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                audio_files.append(p)
        return sorted(audio_files)

    def is_multi_file_bundle(self, file_path: Path) -> bool:
        """Returns True if the file belongs to a directory containing multiple audio tracks."""
        root = self.resolve_bundle_root(file_path)
        audio_files = self.find_audio_files(root)
        return len(audio_files) > 1

    def extract_album_consensus(self, audio_files: list[Path]) -> tuple[str | None, str | None]:
        """Extracts consensus album and artist tags across files in a bundle."""
        if not TinyTag:
            return None, None

        albums: list[str] = []
        artists: list[str] = []

        for path in audio_files:
            try:
                tag = TinyTag.get(str(path))
                if tag.album:
                    albums.append(tag.album.strip())
                author = tag.artist or tag.albumartist
                if author:
                    artists.append(author.strip())
            except Exception:
                continue

        consensus_album = Counter(albums).most_common(1)[0][0] if albums else None
        consensus_artist = Counter(artists).most_common(1)[0][0] if artists else None

        return consensus_album, consensus_artist

    def get_bundle(self, file_path: Path) -> AudiobookBundle:
        """Resolves or retrieves the cached AudiobookBundle for an audio file."""
        root = self.resolve_bundle_root(file_path)
        if root in self._bundle_cache:
            return self._bundle_cache[root]

        audio_files = self.find_audio_files(root)
        is_multi = len(audio_files) > 1

        seed_title: str = ""
        seed_author: str | None = None
        has_local_tags: bool = False

        if is_multi:
            album_consensus, artist_consensus = self.extract_album_consensus(audio_files)
            if album_consensus:
                seed_title = album_consensus
                seed_author = artist_consensus
                has_local_tags = True
            else:
                # Fallback to parent directory name
                parsed_title, parsed_author = self.identifier.parse_filename(root.name)
                seed_title = parsed_title or root.name
                seed_author = parsed_author
        else:
            seed_title = file_path.stem
            seed_author = None

        total_size = sum(f.stat().st_size for f in audio_files if f.exists())

        matched = self.identifier.identify(
            title=seed_title,
            author=seed_author,
            has_local_tags=has_local_tags,
            path=root,
        )

        bundle = AudiobookBundle(
            root_path=root,
            is_multi_file=is_multi,
            files=audio_files,
            seed_title=seed_title,
            seed_author=seed_author,
            matched_metadata=matched,
            total_size_bytes=total_size,
        )

        self._bundle_cache[root] = bundle
        return bundle
