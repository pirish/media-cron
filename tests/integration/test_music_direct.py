from pathlib import Path
from unittest.mock import MagicMock, patch

from media_cron.config import (
    GeneralConfig,
    MediaCronConfig,
    MusicConfig,
    PathsConfig,
)
from media_cron.metadata.models import MusicWorkflowMode
from media_cron.pipeline import Pipeline


def test_music_direct_organization_pipeline(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "library"
    dest_dir.mkdir()

    album_dir = staging_dir / "Pink Floyd - Animals (1977)"
    album_dir.mkdir()
    t1 = album_dir / "01 - Dogs.flac"
    t1.write_bytes(b"fLaC" + b"\x00" * 50)
    t2 = album_dir / "02 - Pigs.flac"
    t2.write_bytes(b"fLaC" + b"\x00" * 50)
    art = album_dir / "cover.jpg"
    art.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)

    mock_tag1 = MagicMock(
        title="Dogs",
        artist="Pink Floyd",
        album="Animals",
        albumartist="Pink Floyd",
        track=1,
        disc=1,
        year=1977,
        genre="Rock",
    )
    mock_tag2 = MagicMock(
        title="Pigs",
        artist="Pink Floyd",
        album="Animals",
        albumartist="Pink Floyd",
        track=2,
        disc=1,
        year=1977,
        genre="Rock",
    )

    def mock_get(path_str):
        if "Dogs" in path_str:
            return mock_tag1
        return mock_tag2

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir,
            staging_dir=staging_dir,
            destination_dir=dest_dir,
        ),
        general=GeneralConfig(mode="copy", dry_run=False),
        music=MusicConfig(
            enabled=True,
            workflow_mode=MusicWorkflowMode.DIRECT,
            preserve_companions=True,
        ),
    )

    with patch("media_cron.metadata.music_reader.TinyTag.get", side_effect=mock_get):
        pipeline = Pipeline(config=cfg)
        summary = pipeline.run()

        assert summary.exit_code == 0
        assert summary.music_summary is not None
        assert summary.music_summary.get("organized_tracks", 0) >= 2

        # Verify destination library folder structure
        target_album_dir = dest_dir / "Music" / "Pink Floyd" / "Animals (1977)"
        assert target_album_dir.exists()
        assert (target_album_dir / "01 - Dogs.flac").exists()
        assert (target_album_dir / "02 - Pigs.flac").exists()
        assert (target_album_dir / "cover.jpg").exists()
