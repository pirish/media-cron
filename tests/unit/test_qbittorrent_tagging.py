import urllib.error

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


def test_apply_completion_state_dual_update(client, mocker):
    client._authenticated = True
    mock_request = mocker.patch.object(client, "_request", return_value=b"")

    info_hash = "abcdef1234567890abcdef1234567890abcdef12"
    result = client.apply_completion_state(
        info_hash=info_hash,
        tag="media-cron-processed",
        category="media-cron-done",
        pause=False,
    )

    assert result is True
    assert mock_request.call_count == 2
    mock_request.assert_any_call(
        "/api/v2/torrents/addTags",
        method="POST",
        data={"hashes": info_hash, "tags": "media-cron-processed"},
    )
    mock_request.assert_any_call(
        "/api/v2/torrents/setCategory",
        method="POST",
        data={"hashes": info_hash, "category": "media-cron-done"},
    )


def test_apply_completion_state_with_pause(client, mocker):
    client._authenticated = True
    mock_request = mocker.patch.object(client, "_request", return_value=b"")

    info_hash = "abcdef1234567890abcdef1234567890abcdef12"
    result = client.apply_completion_state(
        info_hash=info_hash,
        tag="media-cron-processed",
        category="media-cron-done",
        pause=True,
    )

    assert result is True
    assert mock_request.call_count == 3
    mock_request.assert_any_call(
        "/api/v2/torrents/pause",
        method="POST",
        data={"hashes": info_hash},
    )


def test_apply_completion_state_unauthenticated_connection_error(client, mocker):
    client._authenticated = False
    mocker.patch.object(client, "test_connection", return_value=False)
    mock_request = mocker.patch.object(client, "_request")

    result = client.apply_completion_state(
        info_hash="hash123",
        tag="media-cron-processed",
        category="media-cron-done",
    )

    assert result is False
    mock_request.assert_not_called()


def test_apply_completion_state_tag_failure(client, mocker):
    client._authenticated = True

    def fake_request(endpoint, method="GET", data=None):
        if "addTags" in endpoint:
            raise urllib.error.HTTPError(
                url=endpoint, code=500, msg="Server Error", hdrs={}, fp=None
            )
        return b""

    mocker.patch.object(client, "_request", side_effect=fake_request)

    result = client.apply_completion_state(
        info_hash="hash123",
        tag="media-cron-processed",
        category="media-cron-done",
    )

    assert result is False


def test_direct_tagging_helpers(client, mocker):
    client._authenticated = True
    mock_request = mocker.patch.object(client, "_request", return_value=b"")

    info_hash = "hash123"
    assert client.add_tags(info_hash, "test-tag") is True
    mock_request.assert_called_with(
        "/api/v2/torrents/addTags",
        method="POST",
        data={"hashes": info_hash, "tags": "test-tag"},
    )

    assert client.set_category(info_hash, "test-cat") is True
    mock_request.assert_called_with(
        "/api/v2/torrents/setCategory",
        method="POST",
        data={"hashes": info_hash, "category": "test-cat"},
    )

    assert client.pause_torrent(info_hash) is True
    mock_request.assert_called_with(
        "/api/v2/torrents/pause",
        method="POST",
        data={"hashes": info_hash},
    )
