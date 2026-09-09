from __future__ import annotations

import difflib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from media_cron.metadata.base import (
    MusicMetadataProviderProtocol,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from media_cron.metadata.models import MusicCatalogMatch


class MusicBrainzProvider(MusicMetadataProviderProtocol):
    """MusicBrainz REST API metadata provider adhering to rate-limit and protocol requirements."""

    def __init__(
        self,
        base_url: str = "https://musicbrainz.org/ws/2",
        min_delay_seconds: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.min_delay_seconds = min_delay_seconds
        self._last_request_time = 0.0

    @property
    def provider_name(self) -> str:
        return "musicbrainz"

    def _throttle(self) -> None:
        if self.min_delay_seconds <= 0.0:
            return
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.min_delay_seconds:
            time.sleep(self.min_delay_seconds - elapsed)
        self._last_request_time = time.time()

    def _score_candidate(
        self,
        query_artist: str,
        query_album: str,
        query_track_count: int | None,
        query_year: int | None,
        cand_artist: str,
        cand_album: str,
        cand_track_count: int | None,
        cand_year: int | None,
    ) -> float:
        """Calculates normalized confidence score between 0.0 and 1.0."""
        art_sim = difflib.SequenceMatcher(
            None, query_artist.lower().strip(), cand_artist.lower().strip()
        ).ratio()
        alb_sim = difflib.SequenceMatcher(
            None, query_album.lower().strip(), cand_album.lower().strip()
        ).ratio()

        score = (art_sim * 0.45) + (alb_sim * 0.45)

        if query_year and cand_year and query_year == cand_year:
            score += 0.05
        if query_track_count and cand_track_count and query_track_count == cand_track_count:
            score += 0.05

        return min(round(score, 2), 1.0)

    def search_release(
        self,
        artist: str,
        album: str,
        track_count: int | None = None,
        year: int | None = None,
        timeout_seconds: int = 10,
    ) -> list[MusicCatalogMatch]:
        """Queries MusicBrainz release endpoint and returns ranked candidate matches."""
        query_parts = []
        if artist:
            query_parts.append(f'artist:"{artist}"')
        if album:
            query_parts.append(f'release:"{album}"')

        query_str = " AND ".join(query_parts)
        params = {"query": query_str, "fmt": "json", "limit": "5"}
        url = f"{self.base_url}/release/?{urllib.parse.urlencode(params)}"

        headers = {
            "User-Agent": "media-cron/0.5.0 ( https://github.com/pirish/media-cron )",
            "Accept": "application/json",
        }

        self._throttle()
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            if err.code == 429:
                raise ProviderRateLimitError(f"MusicBrainz rate limit exceeded: {err}") from err
            elif err.code >= 500:
                raise ProviderUnavailableError(f"MusicBrainz server unavailable: {err}") from err
            else:
                raise ProviderUnavailableError(f"MusicBrainz HTTP error {err.code}: {err}") from err
        except TimeoutError as err:
            raise ProviderTimeoutError(f"MusicBrainz request timed out: {err}") from err
        except Exception as err:
            raise ProviderUnavailableError(f"MusicBrainz query failed: {err}") from err

        releases = data.get("releases", [])
        candidates: list[MusicCatalogMatch] = []

        for rel in releases:
            rel_id = str(rel.get("id", ""))
            rel_title = str(rel.get("title", ""))

            # Artist credit
            artist_credits = rel.get("artist-credit", [])
            rel_artist = (
                "".join(ac.get("name", "") for ac in artist_credits if isinstance(ac, dict))
                or artist
            )

            # Release year
            rel_year: int | None = None
            date_str = str(rel.get("date", ""))
            if date_str and len(date_str) >= 4:
                try:
                    rel_year = int(date_str[:4])
                except ValueError:
                    pass

            # Track count and track titles
            rel_track_count = rel.get("track-count")
            track_titles: list[str] = []
            for media in rel.get("media", []):
                for tr in media.get("tracks", []):
                    if "title" in tr:
                        track_titles.append(str(tr["title"]))

            if rel_track_count is None and track_titles:
                rel_track_count = len(track_titles)

            confidence = self._score_candidate(
                query_artist=artist,
                query_album=album,
                query_track_count=track_count,
                query_year=year,
                cand_artist=rel_artist,
                cand_album=rel_title,
                cand_track_count=rel_track_count,
                cand_year=rel_year,
            )

            candidates.append(
                MusicCatalogMatch(
                    title=rel_title,
                    artist=rel_artist,
                    release_id=rel_id,
                    provider="musicbrainz",
                    confidence=confidence,
                    year=rel_year,
                    track_count=rel_track_count,
                    tracks=track_titles,
                )
            )

        candidates.sort(key=lambda m: m.confidence, reverse=True)
        return candidates
