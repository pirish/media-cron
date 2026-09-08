from pathlib import Path

from media_cron.torrent.base import TorrentClientProtocol
from media_cron.torrent.models import TorrentClientConfig, TorrentItem, TorrentState


class MockContractClient:
    def __init__(self, config: TorrentClientConfig):
        self.config = config

    @property
    def client_type(self) -> str:
        return "mock"

    def test_connection(self) -> bool:
        return True

    def list_completed_torrents(
        self, categories=None, tags=None, exclude_tags=None, exclude_categories=None
    ):
        return [
            TorrentItem(
                info_hash="1234567890abcdef1234567890abcdef12345678",
                name="Contract.Test.2024",
                total_size=1024,
                progress=1.0,
                state=TorrentState.COMPLETED,
                save_path="/downloads",
                content_path="/downloads/Contract.Test.2024",
            )
        ]

    def get_torrent(self, identifier: str):
        if identifier in ("1234567890abcdef1234567890abcdef12345678", "Contract.Test.2024"):
            return self.list_completed_torrents()[0]
        return None

    def relocate_storage(self, info_hash: str, new_path: Path) -> bool:
        return True

    def apply_completion_state(
        self, info_hash: str, tag: str, category: str, pause: bool = False
    ) -> bool:
        return True


def test_torrent_client_protocol_satisfaction():
    client = MockContractClient(TorrentClientConfig())
    assert isinstance(client, TorrentClientProtocol)
    assert client.client_type == "mock"
    assert client.test_connection() is True
    torrents = client.list_completed_torrents()
    assert len(torrents) == 1
    assert torrents[0].is_completed() is True
    assert client.get_torrent("Contract.Test.2024") is not None
    assert client.relocate_storage("1234", Path("/tmp")) is True
    assert client.apply_completion_state("1234", "done", "archived") is True
