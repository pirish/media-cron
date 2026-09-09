from pathlib import Path

from media_cron.config import (
    GeneralConfig,
    MediaCronConfig,
    MusicConfig,
    PathsConfig,
)
from media_cron.metadata.models import MusicWorkflowMode
from media_cron.pipeline import Pipeline


def test_music_spool_integration_deposits_bundle_and_companions(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    spool_dir = tmp_path / "music_drop"
    spool_dir.mkdir()

    album_dir = staging_dir / "Pink Floyd - Animals (1977)"
    album_dir.mkdir()
    track1 = album_dir / "01 - Dogs.flac"
    track1.write_bytes(b"flac audio data 1")
    track2 = album_dir / "02 - Pigs.flac"
    track2.write_bytes(b"flac audio data 2")
    cover = album_dir / "cover.jpg"
    cover.write_bytes(b"cover image data")
    cue = album_dir / "album.cue"
    cue.write_text("TITLE Animals\n")
    log = album_dir / "rip.log"
    log.write_text("EAC extraction logfile\n")

    cfg = MediaCronConfig(
        paths=PathsConfig(source_dir=staging_dir, staging_dir=staging_dir),
        general=GeneralConfig(mode="copy", dry_run=False),
        music=MusicConfig(
            enabled=True,
            workflow_mode=MusicWorkflowMode.SPOOL,
            spool_dir=spool_dir,
            preserve_companions=True,
        ),
    )

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    # Drop folder should contain the album folder with all tracks and companions
    target_album = spool_dir / "Pink Floyd - Animals (1977)"
    assert target_album.exists()
    assert (target_album / "01 - Dogs.flac").exists()
    assert (target_album / "02 - Pigs.flac").exists()
    assert (target_album / "cover.jpg").exists()
    assert (target_album / "album.cue").exists()
    assert (target_album / "rip.log").exists()

    # No hidden staging folders remain
    assert not any(p.name.startswith(".incoming_") for p in spool_dir.iterdir())

    # Verify source staging was untouched
    assert (album_dir / "01 - Dogs.flac").exists()

    # Summary telemetry check
    assert summary.music_summary is not None
    assert summary.music_summary.get("spooled_releases", 0) >= 1


def test_music_spool_dry_run_leaves_drop_empty(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    spool_dir = tmp_path / "music_drop"
    spool_dir.mkdir()

    album_dir = source_dir / "Artist - Album"
    album_dir.mkdir()
    (album_dir / "01 - Song.mp3").write_bytes(b"mp3 audio")
    (album_dir / "folder.jpg").write_bytes(b"art")

    cfg = MediaCronConfig(
        paths=PathsConfig(source_dir=source_dir, staging_dir=staging_dir),
        general=GeneralConfig(mode="copy", dry_run=True),
        music=MusicConfig(
            enabled=True,
            workflow_mode=MusicWorkflowMode.SPOOL,
            spool_dir=spool_dir,
        ),
    )

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    # Spool dir must remain completely empty during dry run
    assert list(spool_dir.iterdir()) == []
    assert summary.dry_run is True
