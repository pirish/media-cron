from pathlib import Path

from media_cron.config import (
    GeneralConfig,
    MediaCronConfig,
    PathsConfig,
    VideoConfig,
)
from media_cron.metadata.models import VideoWorkflowMode
from media_cron.pipeline import Pipeline


def test_video_spool_integration_deposits_bundle_and_companions(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    spool_dir = tmp_path / "video_drop"
    spool_dir.mkdir()

    rel_dir = staging_dir / "Dune.Part.Two.2024.2160p"
    rel_dir.mkdir()
    mkv = rel_dir / "Dune.Part.Two.2024.2160p.mkv"
    mkv.write_bytes(b"dummy video data " * 500)
    srt = rel_dir / "Dune.Part.Two.2024.2160p.en.srt"
    srt.write_text("1\n00:00:01 --> 00:00:04\nSub")
    poster = rel_dir / "poster.jpg"
    poster.write_bytes(b"poster image data")
    nfo = rel_dir / "movie.nfo"
    nfo.write_text("<movie><title>Dune 2</title></movie>")

    cfg = MediaCronConfig(
        paths=PathsConfig(source_dir=staging_dir, staging_dir=staging_dir),
        general=GeneralConfig(mode="copy", dry_run=False),
        video=VideoConfig(
            enabled=True,
            workflow_mode=VideoWorkflowMode.SPOOL,
            spool_dir=spool_dir,
            preserve_companions=True,
        ),
    )

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    target_rel = spool_dir / "Dune.Part.Two.2024.2160p"
    assert target_rel.exists()
    assert (target_rel / "Dune.Part.Two.2024.2160p.mkv").exists()
    assert (target_rel / "Dune.Part.Two.2024.2160p.en.srt").exists()
    assert (target_rel / "poster.jpg").exists()
    assert (target_rel / "movie.nfo").exists()

    # No hidden staging folders remain
    assert not any(p.name.startswith(".incoming_") for p in spool_dir.iterdir())

    # Summary telemetry check
    assert summary.video_summary is not None
    assert summary.video_summary.get("spooled_releases", 0) >= 1


def test_video_spool_collision_skips_and_records_warning(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    spool_dir = tmp_path / "video_drop"
    spool_dir.mkdir()

    rel_dir = staging_dir / "Dune.Part.Two.2024.2160p"
    rel_dir.mkdir()
    mkv = rel_dir / "Dune.Part.Two.2024.2160p.mkv"
    mkv.write_bytes(b"dummy video data")

    # Pre-create the target directory in spool_dir
    existing = spool_dir / "Dune.Part.Two.2024.2160p"
    existing.mkdir()
    (existing / "existing.mkv").write_bytes(b"prior file")

    cfg = MediaCronConfig(
        paths=PathsConfig(source_dir=staging_dir, staging_dir=staging_dir),
        general=GeneralConfig(mode="copy", dry_run=False),
        video=VideoConfig(
            enabled=True,
            workflow_mode=VideoWorkflowMode.SPOOL,
            spool_dir=spool_dir,
        ),
    )

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    # Original staging file still exists (not deleted or moved)
    assert mkv.exists()
    # Telemetry records warning or skipped
    assert summary.video_summary is not None
    assert (
        summary.video_summary.get("spool_skipped_count", 0) >= 1
        or summary.video_summary.get("skipped_releases", 0) >= 1
    )


def test_video_spool_dry_run_leaves_drop_empty(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    spool_dir = tmp_path / "video_drop"
    spool_dir.mkdir()

    rel_dir = staging_dir / "Movie.2024"
    rel_dir.mkdir()
    (rel_dir / "Movie.2024.mkv").write_bytes(b"video data")

    cfg = MediaCronConfig(
        paths=PathsConfig(source_dir=staging_dir, staging_dir=staging_dir),
        general=GeneralConfig(mode="copy", dry_run=True),
        video=VideoConfig(
            enabled=True,
            workflow_mode=VideoWorkflowMode.SPOOL,
            spool_dir=spool_dir,
        ),
    )

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    # Spool dir must remain completely empty during dry run
    assert list(spool_dir.iterdir()) == []
    assert summary.dry_run is True
