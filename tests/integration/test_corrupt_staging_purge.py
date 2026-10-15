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


def test_torrent_staging_purges_corrupt_candidate_and_restarts(tmp_path: Path):
    source_root = tmp_path / "remote_downloads"
    source_root.mkdir()
    torrent_folder = source_root / "Corrupt.Release.2026"
    torrent_folder.mkdir()
    media_file = torrent_folder / "movie.mkv"
    media_file.write_bytes(b"Z" * 1000)

    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    staged_folder = staging_dir / "Corrupt.Release.2026"
    staged_folder.mkdir()
    staged_media = staged_folder / "movie.mkv"
    staged_media.write_bytes(b"Z" * 200)  # Truncated write from previous aborted run

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
        info_hash="2222333344445555666677778888999900001111",
        name="Corrupt.Release.2026",
        total_size=1000,
        progress=1.0,
        state=TorrentState.SEEDING,
        save_path="/remote/downloads",
        content_path="/remote/downloads/Corrupt.Release.2026",
        category="movies",
        files=[TorrentFile(name="Corrupt.Release.2026/movie.mkv", size=1000)],
    )
    mock_client.list_completed_torrents.return_value = [torrent_item]

    plugin = TorrentInputPlugin(client=mock_client, config=config)
    discovered = list(
        plugin.discover(source_path=source_root, staging_path=staging_dir, dry_run=False)
    )

    assert len(discovered) == 1
    assert discovered[0].source_path == staged_folder
    assert plugin.verifier.summary.items_purged == 1
    # Verify the file on disk was replaced with the full 1000-byte intact copy
    assert staged_media.stat().st_size == 1000


def test_directory_scanner_purges_corrupt_staged_file_and_restarts(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    src_file = source_dir / "doc.pdf"
    src_file.write_bytes(b"Document Content" * 10)

    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    staged_file = staging_dir / "doc.pdf"
    staged_file.write_bytes(b"Corrupt Partial")  # Size and content mismatch

    scanner = DirectoryScannerInput()
    discovered = list(
        scanner.discover(source_path=source_dir, staging_path=staging_dir, dry_run=False)
    )

    assert len(discovered) == 1
    assert discovered[0].source_path == staged_file
    assert scanner.verifier.summary.items_purged == 1
    assert staged_file.read_bytes() == b"Document Content" * 10
