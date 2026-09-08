from pathlib import Path

from media_cron.torrent.base import TorrentClientProtocol, TorrentClientRegistry
from media_cron.torrent.models import TorrentClientConfig, TorrentItem, TorrentState


class MockTransmissionClient:
    """Mock Transmission RPC client adapter."""

    def __init__(self, config: TorrentClientConfig) -> None:
        self.config = config

    @property
    def client_type(self) -> str:
        return "transmission"

    def test_connection(self) -> bool:
        return True

    def list_completed_torrents(
        self,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        exclude_categories: list[str] | None = None,
    ) -> list[TorrentItem]:
        return [
            TorrentItem(
                info_hash="transmission_hash_123",
                name="Transmission.Release.2024",
                total_size=2048,
                progress=1.0,
                state=TorrentState.SEEDING,
                save_path="/var/lib/transmission/downloads",
                content_path="/var/lib/transmission/downloads/Transmission.Release.2024",
            )
        ]

    def get_torrent(self, identifier: str) -> TorrentItem | None:
        if identifier in ("transmission_hash_123", "Transmission.Release.2024"):
            return self.list_completed_torrents()[0]
        return None

    def relocate_storage(self, info_hash: str, new_path: Path) -> bool:
        return True

    def apply_completion_state(
        self,
        info_hash: str,
        tag: str,
        category: str,
        pause: bool = False,
    ) -> bool:
        return True


class MockDelugeClient:
    """Mock Deluge JSON-RPC client adapter."""

    def __init__(self, config: TorrentClientConfig) -> None:
        self.config = config

    @property
    def client_type(self) -> str:
        return "deluge"

    def test_connection(self) -> bool:
        return True

    def list_completed_torrents(
        self,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        exclude_categories: list[str] | None = None,
    ) -> list[TorrentItem]:
        return [
            TorrentItem(
                info_hash="deluge_hash_456",
                name="Deluge.Release.2024",
                total_size=4096,
                progress=1.0,
                state=TorrentState.COMPLETED,
                save_path="/var/lib/deluge/downloads",
                content_path="/var/lib/deluge/downloads/Deluge.Release.2024",
            )
        ]

    def get_torrent(self, identifier: str) -> TorrentItem | None:
        if identifier in ("deluge_hash_456", "Deluge.Release.2024"):
            return self.list_completed_torrents()[0]
        return None

    def relocate_storage(self, info_hash: str, new_path: Path) -> bool:
        return True

    def apply_completion_state(
        self,
        info_hash: str,
        tag: str,
        category: str,
        pause: bool = False,
    ) -> bool:
        return True


def test_mock_clients_satisfy_protocol():
    trans_config = TorrentClientConfig(client_type="transmission")
    deluge_config = TorrentClientConfig(client_type="deluge")

    trans_client = MockTransmissionClient(trans_config)
    deluge_client = MockDelugeClient(deluge_config)

    assert isinstance(trans_client, TorrentClientProtocol)
    assert isinstance(deluge_client, TorrentClientProtocol)


def test_register_and_create_mock_clients():
    TorrentClientRegistry.register("transmission", MockTransmissionClient)
    TorrentClientRegistry.register("deluge", MockDelugeClient)

    assert "transmission" in TorrentClientRegistry.available_clients()
    assert "deluge" in TorrentClientRegistry.available_clients()

    trans_config = TorrentClientConfig(client_type="transmission")
    client1 = TorrentClientRegistry.create_client(trans_config)
    assert client1.client_type == "transmission"
    assert client1.test_connection() is True
    assert len(client1.list_completed_torrents()) == 1

    deluge_config = TorrentClientConfig(client_type="deluge")
    client2 = TorrentClientRegistry.create_client(deluge_config)
    assert client2.client_type == "deluge"
    assert client2.test_connection() is True
    assert len(client2.list_completed_torrents()) == 1
