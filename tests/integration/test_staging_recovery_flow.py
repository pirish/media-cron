from pathlib import Path
from unittest.mock import MagicMock

from media_cron.plugins.input.directory import DirectoryScannerInput
from media_cron.plugins.input.torrent import TorrentInputPlugin
from media_cron.torrent.models import (
    PathMappingRule,
    TorrentClientConfig,
    TorrentFile,
    TorrentItem,
    TorrentState,
)


def test_torrent_staging_resumes_matching_candidate(tmp_path: Path):
    source_root = tmp_path / "remote_downloads"
    source_root.mkdir()
    torrent_folder = source_root / "Big.Buck.Bunny.2008.1080p"
    torrent_folder.mkdir()
    media_file = torrent_folder / "movie.mkv"
    media_file.write_text("identical media payload")

    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    staged_folder = staging_dir / "Big.Buck.Bunny.2008.1080p"
    staged_folder.mkdir()
    staged_media = staged_folder / "movie.mkv"
    staged_media.write_text("identical media payload")

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
        total_size=len("identical media payload"),
        progress=1.0,
        state=TorrentState.SEEDING,
        save_path="/remote/downloads",
        content_path="/remote/downloads/Big.Buck.Bunny.2008.1080p",
        category="movies",
        files=[
            TorrentFile(
                name="Big.Buck.Bunny.2008.1080p/movie.mkv", size=len("identical media payload")
            )
        ],
    )
    mock_client.list_completed_torrents.return_value = [torrent_item]

    plugin = TorrentInputPlugin(client=mock_client, config=config)
    discovered = list(
        plugin.discover(source_path=source_root, staging_path=staging_dir, dry_run=False)
    )

    assert len(discovered) == 1
    assert discovered[0].source_path == staged_folder
    # Verifier recorded resume
    assert plugin.verifier.summary.items_resumed == 1
    assert plugin.verifier.summary.bytes_saved == len("identical media payload")


def test_directory_scanner_resumes_matching_staged_file(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    src_file = source_dir / "movie.mkv"
    src_file.write_text("identical media content")

    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    staged_file = staging_dir / "movie.mkv"
    staged_file.write_text("identical media content")

    scanner = DirectoryScannerInput()
    discovered = list(
        scanner.discover(source_path=source_dir, staging_path=staging_dir, dry_run=False)
    )

    assert len(discovered) == 1
    assert discovered[0].source_path == staged_file
    assert scanner.verifier.summary.items_resumed == 1
