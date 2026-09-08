from media_cron.torrent.base import TorrentClientProtocol, TorrentClientRegistry
from media_cron.torrent.clients.qbittorrent import QBittorrentClient
from media_cron.torrent.models import (
    PathMappingRule,
    TorrentClientConfig,
    TorrentFile,
    TorrentFilterConfig,
    TorrentItem,
    TorrentSeedingConfig,
    TorrentState,
)

# Register built-in client providers
TorrentClientRegistry.register("qbittorrent", QBittorrentClient)

__all__ = [
    "PathMappingRule",
    "QBittorrentClient",
    "TorrentClientConfig",
    "TorrentClientProtocol",
    "TorrentClientRegistry",
    "TorrentFile",
    "TorrentFilterConfig",
    "TorrentItem",
    "TorrentSeedingConfig",
    "TorrentState",
]
