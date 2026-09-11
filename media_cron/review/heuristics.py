import re
from pathlib import Path

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".ogg", ".wav", ".opus", ".ape"}
AUDIOBOOK_EXTENSIONS = {".m4b"}
BOOK_EXTENSIONS = {".epub", ".mobi", ".azw3", ".pdf", ".cbz", ".cbr"}

TV_PATTERN = re.compile(
    r"([Ss]\d{1,2}[Ee]\d{1,3}|\d{1,2}[xX]\d{1,3}|season\s*\d+|episode\s*\d+)", re.IGNORECASE
)


def derive_category_hint(paths: list[Path]) -> str | None:
    """Heuristically guesses media category based on file extensions and name tokens."""
    if not paths:
        return None

    # Filter for candidate media files (ignore generic companion clutter like .jpg, .nfo)
    media_files = [
        p
        for p in paths
        if p.suffix.lower()
        in (VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | AUDIOBOOK_EXTENSIONS | BOOK_EXTENSIONS)
    ]
    candidates = media_files if media_files else paths

    for p in candidates:
        ext = p.suffix.lower()
        if ext in AUDIOBOOK_EXTENSIONS:
            return "audiobook"
        if ext in VIDEO_EXTENSIONS:
            if TV_PATTERN.search(p.name):
                return "tv"
            return "movie"
        if ext in AUDIO_EXTENSIONS:
            return "music"
        if ext in BOOK_EXTENSIONS:
            return "book"

    return None
