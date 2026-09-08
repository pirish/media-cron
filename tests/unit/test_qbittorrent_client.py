import json
import urllib.error
from unittest.mock import MagicMock, patch

from media_cron.torrent.clients.qbittorrent import QBittorrentClient
from media_cron.torrent.models import TorrentClientConfig, TorrentState


def make_mock_response(body_bytes: bytes, status: int = 200, headers=None):
    mock_resp = MagicMock()
    mock_resp.read.return_value = body_bytes
    mock_resp.status = status
    mock_resp.getcode.return_value = status
    mock_resp.headers = headers or {}
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


def test_qbittorrent_login_success():
    config = TorrentClientConfig(host="localhost", port=8080, username="admin", password="password")
    client = QBittorrentClient(config)

    with patch.object(client._opener, "open") as mock_open:
        mock_open.return_value = make_mock_response(b"Ok.")
        assert client.test_connection() is True


def test_qbittorrent_login_failure_bad_credentials():
    config = TorrentClientConfig(
        host="localhost", port=8080, username="admin", password="wrongpassword"
    )
    client = QBittorrentClient(config)

    with patch.object(client._opener, "open") as mock_open:
        mock_open.return_value = make_mock_response(b"Fails.", status=200)
        assert client.test_connection() is False


def test_qbittorrent_connection_unreachable():
    config = TorrentClientConfig(host="unreachable.local", port=8080)
    client = QBittorrentClient(config)

    with patch.object(
        client._opener, "open", side_effect=urllib.error.URLError("Connection refused")
    ):
        assert client.test_connection() is False


def test_qbittorrent_list_completed_torrents():
    config = TorrentClientConfig(host="localhost", port=8080)
    client = QBittorrentClient(config)

    torrents_data = [
        {
            "hash": "abc1234567890123456789012345678901234567",
            "name": "Movie.Completed.2024",
            "size": 1024 * 1024 * 500,
            "progress": 1.0,
            "state": "uploading",
            "save_path": "/downloads",
            "content_path": "/downloads/Movie.Completed.2024",
            "category": "movies",
            "tags": "1080p, release",
        },
        {
            "hash": "def1234567890123456789012345678901234567",
            "name": "Movie.Downloading.2024",
            "size": 1024 * 1024 * 500,
            "progress": 0.45,
            "state": "downloading",
            "save_path": "/downloads",
            "content_path": "/downloads/Movie.Downloading.2024",
            "category": "movies",
            "tags": "",
        },
    ]

    files_data = [{"name": "Movie.Completed.2024.mkv", "size": 1024 * 1024 * 500, "progress": 1.0}]

    with patch.object(client, "test_connection", return_value=True):
        with patch.object(client._opener, "open") as mock_open:
            mock_open.side_effect = [
                make_mock_response(json.dumps(torrents_data).encode("utf-8")),
                make_mock_response(json.dumps(files_data).encode("utf-8")),
            ]

            completed = client.list_completed_torrents(categories=["movies"])
            assert len(completed) == 1
            t = completed[0]
            assert t.name == "Movie.Completed.2024"
            assert t.info_hash == "abc1234567890123456789012345678901234567"
            assert t.state == TorrentState.SEEDING
            assert t.category == "movies"
            assert "1080p" in t.tags
            assert len(t.files) == 1
            assert t.files[0].name == "Movie.Completed.2024.mkv"


def test_qbittorrent_get_torrent_by_hash_and_name():
    config = TorrentClientConfig(host="localhost", port=8080)
    client = QBittorrentClient(config)

    torrents_data = [
        {
            "hash": "abc1234567890123456789012345678901234567",
            "name": "Targeted.Movie.2024",
            "size": 1024,
            "progress": 1.0,
            "state": "pausedUP",
            "save_path": "/downloads",
            "content_path": "/downloads/Targeted.Movie.2024",
            "category": "",
            "tags": "",
        }
    ]

    with patch.object(client, "test_connection", return_value=True):
        with patch.object(client._opener, "open") as mock_open:
            mock_open.side_effect = [
                make_mock_response(json.dumps(torrents_data).encode("utf-8")),
                make_mock_response(b"[]"),
                make_mock_response(json.dumps(torrents_data).encode("utf-8")),
                make_mock_response(b"[]"),
            ]

            # Find by hash
            t1 = client.get_torrent("abc1234567890123456789012345678901234567")
            assert t1 is not None
            assert t1.name == "Targeted.Movie.2024"

            # Find by name
            t2 = client.get_torrent("Targeted.Movie.2024")
            assert t2 is not None
            assert t2.info_hash == "abc1234567890123456789012345678901234567"
