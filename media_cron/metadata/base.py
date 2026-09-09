from typing import Protocol, runtime_checkable

from media_cron.config import ExternalProviderConfig
from media_cron.metadata.models import MetadataMatch


class ProviderError(Exception):
    """Base error for metadata providers."""

    pass


class ProviderUnavailableError(ProviderError):
    """Raised when external provider endpoint is unreachable or DNS fails."""

    pass


class ProviderTimeoutError(ProviderError):
    """Raised when external provider request exceeds timeout."""

    pass


class ProviderRateLimitError(ProviderError):
    """Raised when external provider throttles requests (HTTP 429)."""

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
        """Query the external service for matching book/audiobook candidates."""
        ...


class MetadataProviderRegistry:
    """Registry mapping provider names to their adapter implementation classes."""

    def __init__(self) -> None:
        self._providers: dict[str, type[MetadataProviderProtocol]] = {}

    def register(self, name: str, provider_cls: type[MetadataProviderProtocol]) -> None:
        self._providers[name.lower()] = provider_cls

    def get(self, name: str) -> type[MetadataProviderProtocol]:
        key = name.lower()
        if key not in self._providers:
            raise KeyError(
                f"Unknown metadata provider '{name}'. Available: {sorted(self._providers.keys())}"
            )
        return self._providers[key]

    def available_providers(self) -> list[str]:
        return sorted(self._providers.keys())


default_provider_registry = MetadataProviderRegistry()
