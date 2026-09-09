# Interface Contract: Metadata Provider Protocol & Registry

**Branch**: `003-audiobook-identification` | **Date**: 2026-09-08 | **Spec**: [spec.md](../spec.md)

## 1. `MetadataProviderProtocol` (Python `typing.Protocol`)

Every external book metadata adapter must implement this protocol.

```python
from typing import Protocol, runtime_checkable
from media_cron.metadata.models import MetadataMatch, ExternalProviderConfig


class ProviderError(Exception):
    """Base error for external metadata providers."""

    pass


class ProviderUnavailableError(ProviderError):
    """Raised when external provider endpoint is unreachable or DNS fails."""

    pass


class ProviderTimeoutError(ProviderError):
    """Raised when request exceeds configured timeout."""

    pass


class ProviderRateLimitError(ProviderError):
    """Raised when HTTP 429 Too Many Requests is received."""

    pass


@runtime_checkable
class MetadataProviderProtocol(Protocol):
    """Protocol implemented by all external book/audiobook metadata providers."""

    @property
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'openlibrary', 'audnexus')."""
        ...

    def search(
        self,
        title: str,
        author: str | None = None,
        config: ExternalProviderConfig | None = None,
    ) -> list[MetadataMatch]:
        """
        Query the external service for matching book/audiobook candidates.

        Args:
            title: Book or work title to search for.
            author: Optional author name to narrow the query.
            config: Provider configuration containing endpoints, timeouts, and credentials.

        Returns:
            A list of MetadataMatch candidates ordered by provider relevance.
            Returns empty list if no matches are found.

        Raises:
            ProviderUnavailableError: If network is unreachable or service returns 5xx.
            ProviderTimeoutError: If query exceeds config.timeout_seconds.
            ProviderRateLimitError: If service returns HTTP 429.
        """
        ...
```

---

## 2. `MetadataProviderRegistry`

Central registry pattern for discovering and instantiating providers.

```python
from typing import Type


class MetadataProviderRegistry:
    """Registry mapping provider names to their adapter implementation classes."""

    def __init__(self) -> None:
        self._providers: dict[str, Type[MetadataProviderProtocol]] = {}

    def register(self, name: str, provider_cls: Type[MetadataProviderProtocol]) -> None:
        """Register a provider implementation."""
        self._providers[name.lower()] = provider_cls

    def get(self, name: str) -> Type[MetadataProviderProtocol]:
        """Retrieve a registered provider class. Raises KeyError if unknown."""
        provider = self._providers.get(name.lower())
        if not provider:
            raise KeyError(
                f"Unknown metadata provider '{name}'. Registered: {list(self._providers.keys())}"
            )
        return provider

    def available_providers(self) -> list[str]:
        """Return names of all registered providers."""
        return sorted(list(self._providers.keys()))


default_provider_registry = MetadataProviderRegistry()
```

---

## 3. Built-in Provider Adapters

1. **`OpenLibraryProvider`** (`openlibrary`):
   - Queries `https://openlibrary.org/search.json`
   - Encodes URL parameters cleanly via `urllib.parse.urlencode`
   - Parses `docs` array into `MetadataMatch` objects with confidence scores.
2. **`AudnexusProvider`** (`audnexus`):
   - Queries `https://api.audnexus.com/books`
   - Parses response objects into `MetadataMatch` including `narrator` and `series`.
