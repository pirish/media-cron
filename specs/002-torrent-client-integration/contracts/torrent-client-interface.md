# Contract: Pluggable Torrent Client Interface

**Branch**: `002-torrent-client-integration` | **Date**: 2026-09-07 | **Spec**: [spec.md](../spec.md)

## Purpose

Defines the Python `Protocol` and operational contract that all torrent client adapters must fulfill to support media-cron's ingestion and seeding pipelines.

---

## Protocol Definition

```python
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, runtime_checkable

from media_cron.torrent.models import TorrentItem


@runtime_checkable
class TorrentClientProtocol(Protocol):
    """Abstract interface for external torrent clients."""

    @property
    def client_type(self) -> str:
        """Provider name identifying this client (e.g. 'qbittorrent', 'transmission', 'deluge')."""
        ...

    def test_connection(self) -> bool:
        """
        Validates connectivity and authentication to the client.
        
        Returns:
            True if connection and credentials are valid, False otherwise.
        """
        ...

    def list_completed_torrents(
        self,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        exclude_categories: list[str] | None = None,
    ) -> list[TorrentItem]:
        """
        Queries the client for completed downloads matching filter criteria.

        Returns:
            A list of completed TorrentItem instances.
        """
        ...

    def get_torrent(self, identifier: str) -> TorrentItem | None:
        """
        Retrieves a single torrent by info-hash or name.

        Args:
            identifier: 40-character hex info-hash or exact torrent release name.

        Returns:
            TorrentItem if found, None otherwise.
        """
        ...

    def relocate_storage(self, info_hash: str, new_path: Path) -> bool:
        """
        Commands the client to move the torrent's storage and update its save path.

        Args:
            info_hash: Torrent info-hash.
            new_path: Target directory for relocated storage.

        Returns:
            True if relocation succeeded in the client, False otherwise.
        """
        ...

    def apply_completion_state(
        self,
        info_hash: str,
        tag: str,
        category: str,
        pause: bool = False,
    ) -> bool:
        """
        Applies post-processing status updates to the torrent.

        Args:
            info_hash: Torrent info-hash.
            tag: Completion tag to append (e.g. 'media-cron-processed').
            category: Post-processing category to set (e.g. 'media-cron-done').
            pause: Whether to pause the torrent after updating.

        Returns:
            True if status updates were successfully applied.
        """
        ...
```

---

## Client Registry Contract

`TorrentClientRegistry` discovers and instantiates client implementations based on `TorrentClientConfig.client_type`:

```python
class TorrentClientRegistry:
    @classmethod
    def register(cls, client_type: str, factory: type[TorrentClientProtocol]) -> None: ...

    @classmethod
    def get_client(cls, config: TorrentClientConfig) -> TorrentClientProtocol: ...
```

---

## Expected Client Implementations

| Provider | Transport Protocol | Primary Methods | Status |
|---|---|---|---|
| `qbittorrent` | HTTP Web API v2 | `/api/v2/auth/login`, `/api/v2/torrents/info`, `/api/v2/torrents/setLocation`, `/api/v2/torrents/addTags`, `/api/v2/torrents/setCategory` | Built-in |
| `transmission` | HTTP JSON-RPC 2.0 | `torrent-get`, `torrent-set-location`, `torrent-set` | Pluggable contract |
| `deluge` | HTTP JSON-RPC | `web.connected`, `core.get_torrents_status`, `core.move_storage`, `core.set_torrent_options` | Pluggable contract |
