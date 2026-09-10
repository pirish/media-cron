import urllib.error
from unittest.mock import patch

import pytest

from media_cron.metadata.media_servers import (
    EmbyClient,
    JellyfinClient,
    PlexClient,
    get_media_server_client,
)
from media_cron.metadata.models import MediaServerConfig


def test_factory_resolves_supported_clients():
    assert isinstance(get_media_server_client("jellyfin"), JellyfinClient)
    assert isinstance(get_media_server_client("emby"), EmbyClient)
    assert isinstance(get_media_server_client("plex"), PlexClient)
    assert isinstance(get_media_server_client("JELLYFIN"), JellyfinClient)

    with pytest.raises(ValueError, match="Unsupported media server"):
        get_media_server_client("kodi")


def test_jellyfin_client_global_refresh_request():
    client = JellyfinClient()
    cfg = MediaServerConfig(
        enabled=True,
        provider="jellyfin",
        url="http://jellyfin.local:8096",
        token="jelly-secret",
    )
    req = client._build_request(cfg)
    assert req.get_method() == "POST"
    assert req.full_url == "http://jellyfin.local:8096/Library/Refresh"
    assert req.headers.get("X-emby-token") == "jelly-secret"
    assert req.headers.get("Content-type") == "application/json"


def test_jellyfin_client_selective_refresh_request():
    client = JellyfinClient()
    cfg = MediaServerConfig(
        enabled=True,
        provider="jellyfin",
        url="http://jellyfin.local:8096/",
        token="jelly-secret",
        library_id="12345",
    )
    req = client._build_request(cfg, library_id=cfg.library_id)
    assert req.get_method() == "POST"
    assert req.full_url == "http://jellyfin.local:8096/Items/12345/Refresh"
    assert req.headers.get("X-emby-token") == "jelly-secret"


def test_emby_client_request():
    client = EmbyClient()
    cfg = MediaServerConfig(
        enabled=True,
        provider="emby",
        url="https://emby.media:8096",
        token="emby-token-xyz",
    )
    req = client._build_request(cfg)
    assert req.get_method() == "POST"
    assert req.full_url == "https://emby.media:8096/Library/Refresh"
    assert req.headers.get("X-emby-token") == "emby-token-xyz"

    req_selective = client._build_request(cfg, library_id="999")
    assert req_selective.full_url == "https://emby.media:8096/Items/999/Refresh"


def test_plex_client_global_refresh_request():
    client = PlexClient()
    cfg = MediaServerConfig(
        enabled=True,
        provider="plex",
        url="http://192.168.1.100:32400",
        token="plex-token-abc",
    )
    req = client._build_request(cfg)
    assert req.get_method() == "GET"
    assert req.full_url == "http://192.168.1.100:32400/library/sections/all/refresh"
    assert req.headers.get("X-plex-token") == "plex-token-abc"


def test_plex_client_selective_refresh_with_path():
    client = PlexClient()
    cfg = MediaServerConfig(
        enabled=True,
        provider="plex",
        url="http://192.168.1.100:32400",
        token="plex-token-abc",
        library_id="2",
    )
    req = client._build_request(cfg, library_id="2", path="/data/Movies/Avatar")
    assert req.get_method() == "GET"
    assert (
        req.full_url
        == "http://192.168.1.100:32400/library/sections/2/refresh?path=%2Fdata%2FMovies%2FAvatar"
    )
    assert req.headers.get("X-plex-token") == "plex-token-abc"


def test_dry_run_simulation_returns_success_without_network():
    client = JellyfinClient()
    cfg = MediaServerConfig(
        enabled=True,
        provider="jellyfin",
        url="http://offline:8096",
        token="tok",
    )
    with patch("urllib.request.urlopen") as mock_open:
        res = client.trigger_rescan(cfg, dry_run=True)
        assert res.success is True
        assert res.status_code == 204
        assert res.duration_seconds == 0.0
        mock_open.assert_not_called()


def test_offline_server_handled_gracefully_without_exception():
    client = PlexClient()
    cfg = MediaServerConfig(
        enabled=True,
        provider="plex",
        url="http://offline-host:32400",
        token="tok",
        max_retries=0,
    )
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        res = client.trigger_rescan(cfg, dry_run=False)
        assert res.success is False
        assert "Connection refused" in (res.error or "")
        assert res.server_type == "plex"


def test_retry_policy_exhaustion():
    client = JellyfinClient()
    cfg = MediaServerConfig(
        enabled=True,
        provider="jellyfin",
        url="http://failing-host:8096",
        token="tok",
        max_retries=2,
    )
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError("http://url", 503, "Unavailable", {}, None),
    ) as mock_open:
        with patch("time.sleep") as mock_sleep:
            res = client.trigger_rescan(cfg, dry_run=False)
            assert res.success is False
            assert res.status_code == 503
            assert mock_open.call_count == 3  # 1 initial + 2 retries
            assert mock_sleep.call_count == 2
