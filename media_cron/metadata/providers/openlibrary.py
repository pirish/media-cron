import json
import socket
import urllib.error
import urllib.parse
import urllib.request

from media_cron.config import ExternalProviderConfig
from media_cron.metadata.base import (
    MetadataProviderProtocol,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from media_cron.metadata.models import MetadataMatch
from media_cron.metadata.scorer import ConfidenceScorer


class OpenLibraryProvider(MetadataProviderProtocol):
    """Open Library metadata provider using public REST API."""

    def __init__(self, scorer: ConfidenceScorer | None = None) -> None:
        self.scorer = scorer or ConfidenceScorer()

    @property
    def provider_name(self) -> str:
        return "openlibrary"

    def _build_url(self, title: str, author: str | None, base_url: str) -> str:
        clean_base = base_url.rstrip("/")
        params: dict[str, str] = {"title": title, "limit": "5"}
        if author:
            params["author"] = author
        query_str = urllib.parse.urlencode(params)
        return f"{clean_base}/search.json?{query_str}"

    def search(
        self,
        title: str,
        author: str | None = None,
        config: ExternalProviderConfig | None = None,
    ) -> list[MetadataMatch]:
        base_url = config.base_url if config and config.base_url else "https://openlibrary.org"
        timeout = config.timeout_seconds if config else 5.0

        url = self._build_url(title, author, base_url)
        headers = {
            "User-Agent": "media-cron/0.3.0 (+https://github.com/pirish/media-cron)",
            "Accept": "application/json",
        }

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise ProviderRateLimitError(f"Open Library rate limit exceeded: {e.reason}") from e
            elif e.code >= 500:
                raise ProviderUnavailableError(
                    f"Open Library server error ({e.code}): {e.reason}"
                ) from e
            else:
                return []
        except TimeoutError as e:
            raise ProviderTimeoutError(f"Open Library request timed out after {timeout}s") from e
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)):
                raise ProviderTimeoutError(
                    f"Open Library request timed out after {timeout}s"
                ) from e
            raise ProviderUnavailableError(f"Open Library connection failed: {e.reason}") from e
        except Exception as e:
            raise ProviderUnavailableError(f"Unexpected Open Library error: {e}") from e

        docs = data.get("docs", [])
        matches: list[MetadataMatch] = []

        for doc in docs:
            c_title = doc.get("title", "")
            authors = doc.get("author_name", [])
            c_author = authors[0] if authors else ""
            year = doc.get("first_publish_year")
            work_id = doc.get("key")

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
                    work_id=work_id,
                    provider=self.provider_name,
                    confidence=confidence,
                    raw_response=doc,
                )
            )

        # Sort matches by confidence descending
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
