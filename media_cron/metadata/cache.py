import hashlib
import json
import os
import time
from pathlib import Path

from media_cron.metadata.models import (
    MetadataCacheEntry,
    MetadataMatch,
    MusicCacheEntry,
    MusicCatalogMatch,
)


class MetadataCache:
    """Persistent file-based response cache for external metadata lookups."""

    def __init__(self, cache_file: Path | None = None, default_ttl: int = 2592000) -> None:
        self.cache_file = cache_file or Path(".media-cron-cache") / "audiobook_cache.json"
        self.default_ttl = default_ttl
        self._entries: dict[str, MetadataCacheEntry] = {}
        self._load()

    @staticmethod
    def generate_key(provider: str, title: str, author: str | None = None) -> str:
        norm_prov = provider.strip().lower()
        norm_title = " ".join(title.strip().lower().split())
        norm_author = " ".join(author.strip().lower().split()) if author else ""
        raw = f"{norm_prov}:{norm_title}:{norm_author}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load(self) -> None:
        if not self.cache_file.exists():
            return
        try:
            with open(self.cache_file, encoding="utf-8") as f:
                data = json.load(f)
            entries_data = data.get("entries", {})
            for key, edata in entries_data.items():
                self._entries[key] = MetadataCacheEntry.from_dict(edata)
        except Exception:
            # If cache file is corrupted or unreadable, start fresh
            self._entries = {}

    def _save(self) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 1,
                "entries": {k: v.to_dict() for k, v in self._entries.items()},
            }
            tmp_file = self.cache_file.with_name(f"{self.cache_file.name}.tmp.{os.getpid()}")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_file, self.cache_file)
        except Exception:
            # Non-fatal if saving cache fails
            pass

    def get(
        self,
        provider: str,
        title: str,
        author: str | None = None,
        current_time: float | None = None,
    ) -> MetadataMatch | None:
        key = self.generate_key(provider, title, author)
        entry = self._entries.get(key)
        if not entry:
            return None

        if entry.is_expired(current_time):
            del self._entries[key]
            self._save()
            return None

        return entry.match

    def put(
        self,
        provider: str,
        title: str,
        author: str | None = None,
        match: MetadataMatch | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        key = self.generate_key(provider, title, author)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        entry = MetadataCacheEntry(
            cache_key=key,
            provider=provider,
            query_title=title,
            query_author=author,
            created_at=time.time(),
            ttl_seconds=ttl,
            match=match,
        )
        self._entries[key] = entry
        self._save()


class MusicMetadataCache:
    """Persistent file-based response cache for external music metadata lookups."""

    def __init__(self, cache_file: Path | None = None, default_ttl: int = 2592000) -> None:
        self.cache_file = cache_file or Path(".media-cron-cache") / "music_cache.json"
        self.default_ttl = default_ttl
        self._entries: dict[str, MusicCacheEntry] = {}
        self._load()

    @staticmethod
    def generate_key(provider: str, artist: str, album: str) -> str:
        norm_prov = provider.strip().lower()
        norm_artist = " ".join(artist.strip().lower().split())
        norm_album = " ".join(album.strip().lower().split())
        raw = f"{norm_prov}:{norm_artist}:{norm_album}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load(self) -> None:
        if not self.cache_file.exists():
            return
        try:
            with open(self.cache_file, encoding="utf-8") as f:
                data = json.load(f)
            entries_data = data.get("entries", {})
            for key, edata in entries_data.items():
                self._entries[key] = MusicCacheEntry.from_dict(edata)
        except Exception:
            self._entries = {}

    def _save(self) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 1,
                "entries": {k: v.to_dict() for k, v in self._entries.items()},
            }
            tmp_file = self.cache_file.with_name(f"{self.cache_file.name}.tmp.{os.getpid()}")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_file, self.cache_file)
        except Exception:
            pass

    def get(
        self,
        provider: str,
        artist: str,
        album: str,
        current_time: float | None = None,
    ) -> list[MusicCatalogMatch] | None:
        key = self.generate_key(provider, artist, album)
        entry = self._entries.get(key)
        if not entry:
            return None

        if entry.is_expired(current_time):
            del self._entries[key]
            self._save()
            return None

        return entry.matches

    def get_match(
        self,
        provider: str,
        artist: str,
        album: str,
        current_time: float | None = None,
    ) -> MusicCatalogMatch | None:
        matches = self.get(provider, artist, album, current_time=current_time)
        if matches:
            return matches[0]
        return None

    def put(
        self,
        provider: str,
        artist: str,
        album: str,
        matches: list[MusicCatalogMatch] | None = None,
        match: MusicCatalogMatch | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        key = self.generate_key(provider, artist, album)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        if matches is not None:
            match_list = list(matches)
        elif match is not None:
            match_list = [match]
        else:
            match_list = []

        entry = MusicCacheEntry(
            cache_key=key,
            provider=provider,
            artist=artist,
            album=album,
            created_at=time.time(),
            ttl_seconds=ttl,
            matches=match_list,
        )
        self._entries[key] = entry
        self._save()
