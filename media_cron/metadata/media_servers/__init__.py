from media_cron.metadata.base import MediaServerClientProtocol
from media_cron.metadata.media_servers.base import BaseMediaServerClient
from media_cron.metadata.media_servers.emby import EmbyClient
from media_cron.metadata.media_servers.jellyfin import JellyfinClient
from media_cron.metadata.media_servers.plex import PlexClient

_CLIENTS: dict[str, type[BaseMediaServerClient]] = {
    "jellyfin": JellyfinClient,
    "emby": EmbyClient,
    "plex": PlexClient,
}


def get_media_server_client(provider: str) -> BaseMediaServerClient:
    key = provider.strip().lower()
    client_cls = _CLIENTS.get(key)
    if not client_cls:
        raise ValueError(
            f"Unsupported media server provider: '{provider}'. Supported: {list(_CLIENTS.keys())}"
        )
    return client_cls()


__all__ = [
    "BaseMediaServerClient",
    "EmbyClient",
    "JellyfinClient",
    "MediaServerClientProtocol",
    "PlexClient",
    "get_media_server_client",
]
