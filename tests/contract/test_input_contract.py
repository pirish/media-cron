from pathlib import Path

from media_cron.models import DiscoveredItem
from media_cron.plugins.base import InputPlugin
from media_cron.plugins.input.directory import DirectoryScannerInput


def test_directory_scanner_input_satisfies_protocol(tmp_path: Path):
    scanner = DirectoryScannerInput()
    assert isinstance(scanner, InputPlugin)
    assert scanner.plugin_name == "directory_scanner"

    # Setup mock source files
    source = tmp_path / "source"
    staging = tmp_path / "staging"
    source.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)

    test_file = source / "test_movie.mkv"
    test_file.write_bytes(b"content")

    # In dry_run mode, discovers without moving
    items = list(scanner.discover(source_path=source, staging_path=staging, dry_run=True))
    assert len(items) == 1
    item = items[0]
    assert isinstance(item, DiscoveredItem)
    assert item.source_path == test_file
    assert test_file.exists()  # Not moved

    # In live mode, moves to staging
    live_items = list(scanner.discover(source_path=source, staging_path=staging, dry_run=False))
    assert len(live_items) == 1
    assert not test_file.exists()  # Moved out of source
    assert (staging / "test_movie.mkv").exists()  # Staged
