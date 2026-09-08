import logging
import shutil
import time
from collections.abc import Iterable
from pathlib import Path

from media_cron.models import DiscoveredItem
from media_cron.plugins.base import InputPlugin
from media_cron.plugins.registry import default_registry
from media_cron.torrent.base import TorrentClientProtocol, TorrentClientRegistry
from media_cron.torrent.models import TorrentClientConfig, TorrentItem

logger = logging.getLogger(__name__)


class TorrentInputPlugin(InputPlugin):
    """Input plugin that discovers completed downloads from torrent clients and copies them to staging."""

    def __init__(
        self,
        client: TorrentClientProtocol | None = None,
        config: TorrentClientConfig | None = None,
        target_identifier: str | None = None,
    ):
        self.config = config or TorrentClientConfig()
        if client:
            self.client = client
        else:
            self.client = TorrentClientRegistry.create_client(self.config)
        self.target_identifier = target_identifier
        self.processed_torrents: list[TorrentItem] = []

    @property
    def plugin_name(self) -> str:
        return "torrent"

    def discover(
        self, source_path: Path, staging_path: Path, dry_run: bool = False
    ) -> Iterable[DiscoveredItem]:
        """Discovers eligible completed torrents and stages copies of their payloads."""
        if not self.client.test_connection():
            logger.error("Torrent client connection test failed. Skipping torrent ingestion.")
            return

        torrents: list[TorrentItem] = []
        if self.target_identifier:
            t = self.client.get_torrent(self.target_identifier)
            if t:
                torrents = [t]
            else:
                logger.warning(
                    "Targeted torrent identifier '%s' not found.", self.target_identifier
                )
        else:
            torrents = self.client.list_completed_torrents()

        logger.info("Found %d eligible completed torrent(s) in client.", len(torrents))

        for torrent in torrents:
            seeding_cfg = self.config.seeding
            if seeding_cfg.completion_tag and seeding_cfg.completion_tag in torrent.tags:
                logger.debug(
                    "Skipping torrent '%s' already tagged with '%s'",
                    torrent.name,
                    seeding_cfg.completion_tag,
                )
                continue
            if (
                seeding_cfg.completion_category
                and torrent.category == seeding_cfg.completion_category
            ):
                logger.debug(
                    "Skipping torrent '%s' with completion category '%s'",
                    torrent.name,
                    seeding_cfg.completion_category,
                )
                continue

            # Reconcile client path with local mount
            local_path = self.config.translate_path(torrent.content_path)
            if not local_path.exists():
                fallback = self.config.translate_path(torrent.save_path) / torrent.name
                if fallback.exists():
                    local_path = fallback
                else:
                    logger.warning(
                        "Torrent payload for '%s' could not be resolved at %s or %s.",
                        torrent.name,
                        local_path,
                        fallback,
                    )
                    continue

            self.processed_torrents.append(torrent)
            is_dir = local_path.is_dir()
            mtime = local_path.stat().st_mtime if local_path.exists() else time.time()

            if dry_run:
                logger.info("[DRY-RUN] Discovered torrent payload: %s", local_path)
                yield DiscoveredItem(
                    source_path=local_path,
                    file_size=torrent.total_size,
                    modified_time=mtime,
                    is_directory=is_dir,
                )
                continue

            # Live copy into staging
            staging_path.mkdir(parents=True, exist_ok=True)
            staging_dest = staging_path / torrent.name

            try:
                if is_dir:
                    shutil.copytree(local_path, staging_dest, dirs_exist_ok=True)
                else:
                    staging_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(local_path, staging_dest)

                logger.info(
                    "Copied torrent payload '%s' to staging: %s", torrent.name, staging_dest
                )
                yield DiscoveredItem(
                    source_path=staging_dest,
                    file_size=torrent.total_size,
                    modified_time=mtime,
                    is_directory=is_dir,
                )
            except Exception as e:
                logger.error("Failed to copy torrent '%s' to staging: %s", torrent.name, e)


default_registry.register_input("torrent", TorrentInputPlugin)
