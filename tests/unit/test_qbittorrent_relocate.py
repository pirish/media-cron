import urllib.error
from pathlib import Path

import pytest

from media_cron.torrent.clients.qbittorrent import QBittorrentClient
from media_cron.torrent.models import TorrentClientConfig


@pytest.fixture
def client():
    config = TorrentClientConfig(
        client_type="qbittorrent",
        host="localhost",
        port=8080,
        username="admin",
        password="secretpassword",
    )
    return QBittorrentClient(config)


def test_relocate_storage_success(client, mocker):
    mock_request = mocker.patch.object(client, "_request", return_value=b"")
    client._authenticated = True

    dest = Path("/data/seeding/completed")
    result = client.relocate_storage("abcdef1234567890abcdef1234567890abcdef12", dest)

    assert result is True
    mock_request.assert_called_once_with(
        "/api/v2/torrents/setLocation",
        method="POST",
        data={
            "hashes": "abcdef1234567890abcdef1234567890abcdef12",
            "location": str(dest),
        },
    )


def test_relocate_storage_unauthenticated_connection_failure(client, mocker):
    client._authenticated = False
    mocker.patch.object(client, "test_connection", return_value=False)
    mock_request = mocker.patch.object(client, "_request")

    dest = Path("/data/seeding/completed")
    result = client.relocate_storage("hash123", dest)

    assert result is False
    mock_request.assert_not_called()


def test_relocate_storage_http_error(client, mocker):
    client._authenticated = True
    mocker.patch.object(
        client,
        "_request",
        side_effect=urllib.error.HTTPError(
            url="http://localhost:8080/api/v2/torrents/setLocation",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        ),
    )

    dest = Path("/data/seeding/completed")
    result = client.relocate_storage("hash123", dest)

    assert result is False


def test_relocate_storage_network_timeout(client, mocker):
    client._authenticated = True
    mocker.patch.object(
        client,
        "_request",
        side_effect=urllib.error.URLError("timed out"),
    )

    dest = Path("/data/seeding/completed")
    result = client.relocate_storage("hash123", dest)

    assert result is False
