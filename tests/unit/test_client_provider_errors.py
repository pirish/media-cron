import pytest

from media_cron.torrent.base import TorrentClientRegistry
from media_cron.torrent.models import TorrentClientConfig


def test_unknown_client_provider_raises_informative_error():
    cfg = TorrentClientConfig(client_type="nonexistent_client")

    with pytest.raises(ValueError) as exc_info:
        TorrentClientRegistry.create_client(cfg)

    err_msg = str(exc_info.value)
    assert "Unknown torrent client provider 'nonexistent_client'" in err_msg
    assert "Available providers:" in err_msg
    assert "qbittorrent" in err_msg


def test_available_clients_lists_registered_providers():
    providers = TorrentClientRegistry.available_clients()
    assert "qbittorrent" in providers
    assert isinstance(providers, list)
