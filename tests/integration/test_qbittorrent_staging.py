from pathlib import Path
from unittest.mock import MagicMock

from media_cron.plugins.input.torrent import TorrentInputPlugin
from media_cron.torrent.models import (
    PathMappingRule,
    TorrentClientConfig,
    TorrentFile,
    TorrentItem,
    TorrentState,
)


def test_torrent_staging_copies_payload_and_preserves_source(tmp_path: Path):
    source_root = tmp_path / "remote_downloads"
    source_root.mkdir()
    torrent_folder = source_root / "Big.Buck.Bunny.2008.1080p"
    torrent_folder.mkdir()
    media_file = torrent_folder / "movie.mkv"
    media_file.write_text("dummy movie content")
    nfo_file = torrent_folder / "release.nfo"
    nfo_file.write_text("dummy release nfo")

    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()

    # Configure path mapping
    mapping = PathMappingRule(
        remote_prefix="/remote/downloads",
        local_prefix=str(source_root),
    )
    config = TorrentClientConfig(
        client_type="qbittorrent",
        path_mappings=[mapping],
    )

    mock_client = MagicMock()
    torrent_item = TorrentItem(
        info_hash="1111222233334444555566667777888899990000",
        name="Big.Buck.Bunny.2008.1080p",
        total_size=1000,
        progress=1.0,
        state=TorrentState.SEEDING,
        save_path="/remote/downloads",
        content_path="/remote/downloads/Big.Buck.Bunny.2008.1080p",
        category="movies",
        files=[
            TorrentFile(name="Big.Buck.Bunny.2008.1080p/movie.mkv", size=500),
            TorrentFile(name="Big.Buck.Bunny.2008.1080p/release.nfo", size=500),
        ],
    )
    mock_client.list_completed_torrents.return_value = [torrent_item]

    plugin = TorrentInputPlugin(client=mock_client, config=config)
    discovered = list(
        plugin.discover(source_path=source_root, staging_path=staging_dir, dry_run=False)
    )

    # Assert files copied to staging
    assert len(discovered) == 1
    staged_item = discovered[0]
    assert staged_item.is_directory is True
    assert staged_item.source_path.exists()
    assert (staged_item.source_path / "movie.mkv").exists()
    assert (staged_item.source_path / "release.nfo").exists()

    # Crucial: source file MUST still exist intact for active seeding!
    assert media_file.exists()
    assert nfo_file.exists()
