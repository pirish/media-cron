from pathlib import Path

import pytest

from media_cron.torrent.base import TorrentClientProtocol, TorrentClientRegistry
from media_cron.torrent.models import TorrentClientConfig


class DummyClient:
    def __init__(self, config: TorrentClientConfig):
        self.config = config

    @property
    def client_type(self) -> str:
        return "dummy"

    def test_connection(self) -> bool:
        return True

    def list_completed_torrents(
        self, categories=None, tags=None, exclude_tags=None, exclude_categories=None
    ):
        return []

    def get_torrent(self, identifier: str):
        return None

    def relocate_storage(self, info_hash: str, new_path: Path) -> bool:
        return True

    def apply_completion_state(
        self, info_hash: str, tag: str, category: str, pause: bool = False
    ) -> bool:
        return True


def test_torrent_registry_lifecycle():
    assert isinstance(DummyClient(TorrentClientConfig()), TorrentClientProtocol)

    TorrentClientRegistry.register("dummy", DummyClient)
    assert "dummy" in TorrentClientRegistry.available_clients()

    cls = TorrentClientRegistry.get_client_class("dummy")
    assert cls is DummyClient

    client = TorrentClientRegistry.create_client(TorrentClientConfig(client_type="dummy"))
    assert isinstance(client, DummyClient)
    assert client.test_connection() is True

    with pytest.raises(ValueError, match="Unknown torrent client provider 'nonexistent'"):
        TorrentClientRegistry.get_client_class("nonexistent")
