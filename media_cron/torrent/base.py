from pathlib import Path
from typing import Protocol, runtime_checkable

from media_cron.torrent.models import TorrentClientConfig, TorrentItem


@runtime_checkable
class TorrentClientProtocol(Protocol):
    """Abstract interface for external torrent clients."""

    @property
    def client_type(self) -> str:
        """Provider name identifying this client (e.g. 'qbittorrent', 'transmission', 'deluge')."""
        ...

    def test_connection(self) -> bool:
        """Validates connectivity and authentication to the client."""
        ...

    def list_completed_torrents(
        self,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        exclude_categories: list[str] | None = None,
    ) -> list[TorrentItem]:
        """Queries the client for completed downloads matching filter criteria."""
        ...

    def get_torrent(self, identifier: str) -> TorrentItem | None:
        """Retrieves a single torrent by info-hash or name."""
        ...

    def relocate_storage(self, info_hash: str, new_path: Path) -> bool:
        """Commands the client to move the torrent's storage and update its save path."""
        ...

    def apply_completion_state(
        self,
        info_hash: str,
        tag: str,
        category: str,
        pause: bool = False,
    ) -> bool:
        """Applies post-processing status updates to the torrent."""
        ...


class TorrentClientRegistry:
    """Registry for pluggable torrent client providers."""

    _registry: dict[str, type[TorrentClientProtocol]] = {}

    @classmethod
    def register(cls, client_type: str, client_cls: type[TorrentClientProtocol]) -> None:
        """Registers a torrent client adapter class."""
        cls._registry[client_type.lower()] = client_cls

    @classmethod
    def get_client_class(cls, client_type: str) -> type[TorrentClientProtocol]:
        """Retrieves a registered torrent client adapter class."""
        key = client_type.lower()
        if key not in cls._registry:
            available = ", ".join(sorted(cls._registry.keys())) or "none"
            raise ValueError(
                f"Unknown torrent client provider '{client_type}'. Available providers: {available}"
            )
        return cls._registry[key]

    @classmethod
    def create_client(cls, config: TorrentClientConfig) -> TorrentClientProtocol:
        """Instantiates a torrent client adapter from configuration."""
        client_cls = cls.get_client_class(config.client_type)
        return client_cls(config)  # type: ignore[call-arg]

    @classmethod
    def available_clients(cls) -> list[str]:
        """Returns a list of all registered client provider names."""
        return sorted(cls._registry.keys())

    @classmethod
    def clear(cls) -> None:
        """Clears the registry (useful for testing)."""
        cls._registry.clear()
