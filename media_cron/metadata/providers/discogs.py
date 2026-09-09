from __future__ import annotations

import difflib
import json
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


class DiscogsProvider(MusicMetadataProviderProtocol):
    """Discogs metadata provider supporting personal access token authentication."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str = "https://api.discogs.com",
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "discogs"

    def _score_candidate(
        self,
        query_artist: str,
        query_album: str,
        query_year: int | None,
        cand_artist: str,
        cand_album: str,
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
            score += 0.10

        return min(round(score, 2), 1.0)

    def search_release(
        self,
        artist: str,
        album: str,
        track_count: int | None = None,
        year: int | None = None,
        timeout_seconds: int = 10,
    ) -> list[MusicCatalogMatch]:
        """Queries Discogs database search endpoint and returns candidate matches."""
        params: dict[str, str] = {
            "type": "release",
            "artist": artist,
            "release_title": album,
            "per_page": "5",
        }
        url = f"{self.base_url}/database/search?{urllib.parse.urlencode(params)}"

        headers = {
            "User-Agent": "media-cron/0.5.0",
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Discogs token={self.token}"

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            if err.code == 429:
                raise ProviderRateLimitError(f"Discogs rate limit exceeded: {err}") from err
            elif err.code >= 500:
                raise ProviderUnavailableError(f"Discogs service unavailable: {err}") from err
            else:
                raise ProviderUnavailableError(f"Discogs HTTP error {err.code}: {err}") from err
        except TimeoutError as err:
            raise ProviderTimeoutError(f"Discogs request timed out: {err}") from err
        except Exception as err:
            raise ProviderUnavailableError(f"Discogs query failed: {err}") from err

        results = data.get("results", [])
        candidates: list[MusicCatalogMatch] = []

        for item in results:
            rel_id = str(item.get("id", ""))
            title_raw = str(item.get("title", ""))

            if " - " in title_raw:
                parts = title_raw.split(" - ", 1)
                cand_artist = parts[0].strip()
                cand_title = parts[1].strip()
            else:
                cand_artist = artist
                cand_title = title_raw

            cand_year: int | None = None
            if "year" in item:
                try:
                    cand_year = int(str(item["year"])[:4])
                except (ValueError, TypeError):
                    pass

            confidence = self._score_candidate(
                query_artist=artist,
                query_album=album,
                query_year=year,
                cand_artist=cand_artist,
                cand_album=cand_title,
                cand_year=cand_year,
            )

            candidates.append(
                MusicCatalogMatch(
                    title=cand_title,
                    artist=cand_artist,
                    release_id=rel_id,
                    provider="discogs",
                    confidence=confidence,
                    year=cand_year,
                )
            )

        candidates.sort(key=lambda m: m.confidence, reverse=True)
        return candidates
