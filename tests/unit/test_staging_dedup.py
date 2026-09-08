from pathlib import Path
from unittest.mock import MagicMock

from media_cron.config import MediaCronConfig, PathsConfig
from media_cron.models import DiscoveredItem, OperationType
from media_cron.pipeline import Pipeline


def test_staging_deduplication_same_physical_file(tmp_path: Path):
    source_file = tmp_path / "source" / "Movie.2024.1080p.mkv"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"data" * 100)

    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "library"
    dest_dir.mkdir()

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=source_file.parent,
            staging_dir=staging_dir,
            destination_dir=dest_dir,
        ),
        hybrid_ingest=True,
    )

    # Mock two input plugins that discover the exact same file
    mock_plugin1 = MagicMock()
    mock_plugin1.plugin_name = "plugin1"
    mock_plugin1.discover.return_value = [
        DiscoveredItem(
            source_path=source_file,
            file_size=source_file.stat().st_size,
            modified_time=source_file.stat().st_mtime,
            is_directory=False,
        )
    ]

    mock_plugin2 = MagicMock()
    mock_plugin2.plugin_name = "plugin2"
    mock_plugin2.discover.return_value = [
        DiscoveredItem(
            source_path=source_file,
            file_size=source_file.stat().st_size,
            modified_time=source_file.stat().st_mtime,
            is_directory=False,
        )
    ]

    pipeline = Pipeline(cfg)
    pipeline._get_input_plugins = MagicMock(return_value=([mock_plugin1, mock_plugin2], None))

    plans, discovered, _ = pipeline.plan(source_file.parent, staging_dir)

    # Verify only 1 discovered item and 1 organize plan created
    assert len(discovered) == 1
    organize_plans = [p for p in plans if p.op_type == OperationType.ORGANIZE]
    assert len(organize_plans) == 1
