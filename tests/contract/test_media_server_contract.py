import pytest

from media_cron.metadata.base import MediaServerClientProtocol
from media_cron.metadata.media_servers.emby import EmbyClient
from media_cron.metadata.media_servers.jellyfin import JellyfinClient
from media_cron.metadata.media_servers.plex import PlexClient


@pytest.mark.parametrize(
    "client_cls,expected_type",
    [
        (JellyfinClient, "jellyfin"),
        (EmbyClient, "emby"),
        (PlexClient, "plex"),
    ],
)
def test_media_server_clients_satisfy_protocol(client_cls, expected_type):
    client = client_cls()
    assert isinstance(client, MediaServerClientProtocol)
    assert client.server_type == expected_type
    assert hasattr(client, "trigger_rescan")
    assert callable(client.trigger_rescan)
