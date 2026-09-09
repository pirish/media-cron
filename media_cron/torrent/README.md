# Pluggable Torrent Client Architecture

This package provides an extensible abstraction layer for external BitTorrent clients in `media-cron`. Built on Python typing protocols and a dynamic client registry, developers can add support for new clients (such as Transmission or Deluge) without modifying core ingestion or organization pipeline code.

---

## 1. TorrentClientProtocol

All torrent client adapters must satisfy the `TorrentClientProtocol` defined in [`media_cron.torrent.base`](base.py):

```python
from pathlib import Path
from typing import Protocol, runtime_checkable
from media_cron.torrent.models import TorrentItem


@runtime_checkable
class TorrentClientProtocol(Protocol):
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
```

---

## 2. Registering a Custom Client

To register a new client adapter, call `TorrentClientRegistry.register()` during module initialization or application startup:

```python
from media_cron.torrent.base import TorrentClientRegistry
from media_cron.torrent.models import TorrentClientConfig


class TransmissionClient:
    def __init__(self, config: TorrentClientConfig):
        self.config = config

    @property
    def client_type(self) -> str:
        return "transmission"

    # ... implement protocol methods ...


# Register client adapter
TorrentClientRegistry.register("transmission", TransmissionClient)
```

---

## 3. Configuration

Users configure torrent clients in `~/.config/media-cron/config.yaml`:

```yaml
active_torrent_client: "transmission"

torrent_clients:
  transmission:
    client_type: "transmission"
    host: "localhost"
    port: 9091
    username: "transmission"
    password: "secretpassword"
    path_mappings:
      - remote_prefix: "/data/completed"
        local_prefix: "/mnt/storage/completed"
    seeding:
      mode: "client_relocate"
      target_location: "seed_dir"
      completion_tag: "media-cron-processed"
      completion_category: "media-cron-done"
```

---

## 4. Built-in Clients

- **`qbittorrent`**: Built-in HTTP Web API v2 client implemented via Python standard library `urllib.request`. Requires no third-party HTTP dependencies.
