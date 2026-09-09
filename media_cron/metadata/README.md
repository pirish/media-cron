# Audiobook Metadata Subsystem

The `media_cron.metadata` subsystem provides automated book and author identification, multi-file chapter bundle aggregation, persistent response caching, and external provider adapter integration for audiobooks.

---

## Subsystem Architecture

```
media_cron/metadata/
├── __init__.py
├── base.py                     # MetadataProviderProtocol, registry, custom exceptions
├── cache.py                    # Persistent file-based cache with atomic writes & TTL
├── scorer.py                   # Pure Python difflib + token set confidence scorer
├── aggregator.py               # Multi-file chapter bundle clustering & album consensus
├── identifier.py               # Identification coordinator, cascade logic, rate limiting
└── providers/
    ├── __init__.py             # Built-in provider registration
    ├── openlibrary.py          # Open Library REST adapter (default keyless provider)
    └── audnexus.py             # Audnexus REST adapter (specialized audiobook provider)
```

---

## Built-in Providers

### 1. `OpenLibraryProvider` (`openlibrary`)
- **Default**: Enabled by default as zero-configuration provider (Priority: 10).
- **Endpoint**: `https://openlibrary.org/search.json`
- **Authentication**: Keyless.

### 2. `AudnexusProvider` (`audnexus`)
- **Default**: Optional specialized provider (Priority: 20).
- **Endpoint**: `https://api.audnexus.com/books`
- **Features**: Deep audiobook metadata including narrators, series title, and volume/position.

---

## Authoring a Custom Metadata Provider

Any external book metadata provider can be plugged in by implementing `MetadataProviderProtocol`.

### 1. Implement `MetadataProviderProtocol`

```python
from typing import Any
import urllib.request
import urllib.parse
import json

from media_cron.config import ExternalProviderConfig
from media_cron.metadata.base import (
    MetadataProviderProtocol,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderRateLimitError,
)
from media_cron.metadata.models import MetadataMatch
from media_cron.metadata.scorer import ConfidenceScorer


class CustomBookProvider(MetadataProviderProtocol):
    """Custom provider adapter querying an internal or third-party catalog."""

    def __init__(self, scorer: ConfidenceScorer | None = None) -> None:
        self.scorer = scorer or ConfidenceScorer()

    @property
    def provider_name(self) -> str:
        return "my_catalog"

    def search(
        self,
        title: str,
        author: str | None = None,
        config: ExternalProviderConfig | None = None,
    ) -> list[MetadataMatch]:
        base_url = config.base_url if config and config.base_url else "https://api.mycatalog.org"
        timeout = config.timeout_seconds if config else 5.0

        query_params = {"q": title}
        if author:
            query_params["author"] = author
        url = f"{base_url}/search?{urllib.parse.urlencode(query_params)}"

        headers = {
            "User-Agent": "media-cron/0.3.0",
            "Accept": "application/json",
        }
        if config and config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise ProviderRateLimitError(f"Rate limit exceeded: {e.reason}") from e
            elif e.code >= 500:
                raise ProviderUnavailableError(f"Service unavailable: {e.reason}") from e
            return []
        except TimeoutError as e:
            raise ProviderTimeoutError(f"Request timed out after {timeout}s") from e
        except Exception as e:
            raise ProviderUnavailableError(f"Network error: {e}") from e

        matches: list[MetadataMatch] = []
        for item in data.get("items", []):
            cand_title = item.get("title", "")
            cand_author = item.get("author", "")
            confidence = self.scorer.compute_confidence(
                query_title=title,
                query_author=author,
                candidate_title=cand_title,
                candidate_author=cand_author,
            )
            matches.append(
                MetadataMatch(
                    title=cand_title,
                    author=cand_author,
                    year=item.get("year"),
                    work_id=item.get("id"),
                    provider=self.provider_name,
                    confidence=confidence,
                )
            )

        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
```

### 2. Register the Provider

Register your provider with the global provider registry:

```python
from media_cron.metadata.base import default_provider_registry

default_provider_registry.register("my_catalog", CustomBookProvider)
```

---

## Configuration & Precedence Rules

### Precedence Rule (≥85% Confidence)
1. **Full Override ($\ge 0.85$)**: External match title and author replace local tags and cues.
2. **Partial Enrichment ($[0.60, 0.85)$)**: Local title and author are preserved; non-conflicting attributes (narrator, series, volume, year) from the external match are adopted.
3. **Local Fallback ($< 0.60$)**: All external overrides are rejected; local embedded tags (0.75 confidence) or filename cues (0.50 confidence) are preserved.

### YAML Configuration Example

```yaml
audiobook:
  enable_external_lookup: true
  confidence_threshold: 0.85
  cache:
    enabled: true
    ttl_seconds: 2592000  # 30 days
    cache_file: ".media-cron-cache/audiobook_cache.json"
  providers:
    openlibrary:
      enabled: true
      priority: 10
      timeout_seconds: 5.0
      rate_limit_delay: 1.0
    audnexus:
      enabled: true
      priority: 20
      timeout_seconds: 5.0
      rate_limit_delay: 0.5
```
