from pathlib import Path
from unittest.mock import MagicMock

from media_cron.plugins.input.torrent import TorrentInputPlugin
from media_cron.torrent.models import (
    TorrentClientConfig,
    TorrentFile,
    TorrentItem,
    TorrentState,
)


def test_targeted_single_torrent_ingestion(tmp_path: Path):
    source_root = tmp_path / "downloads"
    source_root.mkdir()
    torrent_folder = source_root / "Targeted.Show.S01E01"
    torrent_folder.mkdir()
    (torrent_folder / "episode.mkv").write_text("dummy episode")

    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()

    config = TorrentClientConfig(client_type="qbittorrent")

    mock_client = MagicMock()
    target_torrent = TorrentItem(
        info_hash="aabbccddeeff00112233445566778899aabbccdd",
        name="Targeted.Show.S01E01",
        total_size=1000,
        progress=1.0,
        state=TorrentState.SEEDING,
        save_path=str(source_root),
        content_path=str(torrent_folder),
        category="tv",
        files=[TorrentFile(name="Targeted.Show.S01E01/episode.mkv", size=1000)],
    )

    mock_client.get_torrent.side_effect = lambda ident: (
        target_torrent if ident in (target_torrent.info_hash, target_torrent.name) else None
    )

    # Ingestion by hash
    plugin_hash = TorrentInputPlugin(
        client=mock_client, config=config, target_identifier=target_torrent.info_hash
    )
    discovered_hash = list(
        plugin_hash.discover(source_path=source_root, staging_path=staging_dir, dry_run=False)
    )
    assert len(discovered_hash) == 1
    assert (discovered_hash[0].source_path / "episode.mkv").exists()

    # Ingestion by name
    plugin_name = TorrentInputPlugin(
        client=mock_client, config=config, target_identifier="Targeted.Show.S01E01"
    )
    discovered_name = list(
        plugin_name.discover(source_path=source_root, staging_path=staging_dir, dry_run=False)
    )
    assert len(discovered_name) == 1
