import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from media_cron.config import ExternalProviderConfig
from media_cron.metadata.base import (
    MetadataProviderProtocol,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from media_cron.metadata.models import MetadataMatch
from media_cron.metadata.scorer import ConfidenceScorer


class AudnexusProvider(MetadataProviderProtocol):
    """Audnexus metadata provider querying the public audiobook catalog API."""

    def __init__(self, scorer: ConfidenceScorer | None = None) -> None:
        self.scorer = scorer or ConfidenceScorer()

    @property
    def provider_name(self) -> str:
        return "audnexus"

    def _build_url(self, title: str, author: str | None, base_url: str) -> str:
        clean_base = base_url.rstrip("/")
        params: dict[str, str] = {"title": title}
        if author:
            params["author"] = author
        query_str = urllib.parse.urlencode(params)
        return f"{clean_base}/books?{query_str}"

    def search(
        self,
        title: str,
        author: str | None = None,
        config: ExternalProviderConfig | None = None,
    ) -> list[MetadataMatch]:
        base_url = config.base_url if config and config.base_url else "https://api.audnexus.com"
        timeout = config.timeout_seconds if config else 5.0

        url = self._build_url(title, author, base_url)
        headers = {
            "User-Agent": "media-cron/0.3.0 (+https://github.com/pirish/media-cron)",
            "Accept": "application/json",
        }

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_data = resp.read().decode("utf-8")
                data = json.loads(raw_data)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise ProviderRateLimitError(f"Audnexus rate limit exceeded: {e.reason}") from e
            elif e.code >= 500:
                raise ProviderUnavailableError(
                    f"Audnexus server error ({e.code}): {e.reason}"
                ) from e
            else:
                return []
        except TimeoutError as e:
            raise ProviderTimeoutError(f"Audnexus request timed out after {timeout}s") from e
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)):
                raise ProviderTimeoutError(f"Audnexus request timed out after {timeout}s") from e
            raise ProviderUnavailableError(f"Audnexus connection failed: {e.reason}") from e
        except Exception as e:
            raise ProviderUnavailableError(f"Unexpected Audnexus error: {e}") from e

        # API returns a list of book objects, or dict on some endpoints
        books: list[dict[str, Any]] = data if isinstance(data, list) else [data]
        matches: list[MetadataMatch] = []

        for book in books:
            if not isinstance(book, dict):
                continue
            c_title = book.get("title", "")
            authors = book.get("authors", [])
            c_author = (
                authors[0].get("name", "") if authors and isinstance(authors[0], dict) else ""
            )

            narrators = book.get("narrators", [])
            narrator_names = [
                n.get("name", "") for n in narrators if isinstance(n, dict) and n.get("name")
            ]
            c_narrator = ", ".join(narrator_names) if narrator_names else None

            series_list = book.get("series", [])
            c_series = None
            c_volume = None
            if series_list and isinstance(series_list[0], dict):
                c_series = series_list[0].get("name")
                pos = series_list[0].get("position")
                if pos is not None:
                    c_volume = str(pos)

            rel_date = book.get("releaseDate")
            year = None
            if rel_date and len(rel_date) >= 4 and rel_date[:4].isdigit():
                try:
                    year = int(rel_date[:4])
                except (ValueError, TypeError):
                    pass

            asin = book.get("asin")

            confidence = self.scorer.compute_confidence(
                query_title=title,
                query_author=author,
                candidate_title=c_title,
                candidate_author=c_author,
            )

            matches.append(
                MetadataMatch(
                    title=c_title,
                    author=c_author,
                    year=year,
                    narrator=c_narrator,
                    series=c_series,
                    volume=c_volume,
                    work_id=asin,
                    provider=self.provider_name,
                    confidence=confidence,
                    raw_response=book,
                )
            )

        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
