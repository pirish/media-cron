from pathlib import Path

from media_cron.config import (
    GeneralConfig,
    MediaCronConfig,
    PathsConfig,
    VideoConfig,
)
from media_cron.metadata.models import VideoWorkflowMode
from media_cron.pipeline import Pipeline


def test_direct_movie_organization_with_subtitles(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "destination"
    dest_dir.mkdir()

    rel_dir = staging_dir / "Oppenheimer.2023.2160p.UHD.BluRay.x265"
    rel_dir.mkdir()
    mkv = rel_dir / "Oppenheimer.2023.2160p.UHD.BluRay.x265.mkv"
    mkv.write_bytes(b"\x1a\x45\xdf\xa3dummy video data " * 100)
    srt = rel_dir / "Oppenheimer.2023.2160p.UHD.BluRay.x265.en.forced.srt"
    srt.write_text("1\n00:00:01 --> 00:00:04\nSub")

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir, staging_dir=staging_dir, destination_dir=dest_dir
        ),
        general=GeneralConfig(mode="copy", dry_run=False),
        video=VideoConfig(
            enabled=True,
            workflow_mode=VideoWorkflowMode.DIRECT,
            preserve_companions=True,
        ),
    )

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    # Verify movie directory structure
    movie_folder = dest_dir / "Movies" / "Oppenheimer (2023)"
    assert movie_folder.exists()
    dest_mkv = movie_folder / "Oppenheimer (2023) [2160p].mkv"
    dest_srt = movie_folder / "Oppenheimer (2023) [2160p].en.forced.srt"
    assert dest_mkv.exists()
    assert dest_srt.exists()

    # Telemetry metrics check
    assert summary.video_summary is not None
    assert summary.video_summary.get("organized_movies", 0) >= 1
    assert summary.video_summary.get("total_videos", 0) >= 1


def test_direct_tv_organization_with_subtitles(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "destination"
    dest_dir.mkdir()

    rel_dir = staging_dir / "Severance.S01E01.Good.News.About.Hell.1080p.mkv"
    rel_dir.write_bytes(b"\x1a\x45\xdf\xa3dummy tv data " * 100)
    sub = staging_dir / "Severance.S01E01.Good.News.About.Hell.1080p.en.srt"
    sub.write_text("1\n00:00:01 --> 00:00:04\nSub")

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir, staging_dir=staging_dir, destination_dir=dest_dir
        ),
        general=GeneralConfig(mode="copy", dry_run=False),
        video=VideoConfig(
            enabled=True,
            workflow_mode=VideoWorkflowMode.DIRECT,
            preserve_companions=True,
        ),
    )

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    # Verify TV directory structure
    season_folder = dest_dir / "TV" / "Severance" / "Season 01"
    assert season_folder.exists()
    dest_video = season_folder / "Severance - S01E01 - Good News About Hell [1080p].mkv"
    dest_sub = season_folder / "Severance - S01E01 - Good News About Hell [1080p].en.srt"
    assert dest_video.exists()
    assert dest_sub.exists()

    assert summary.video_summary is not None
    assert summary.video_summary.get("organized_episodes", 0) >= 1


def test_direct_quality_collision_upgrade(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "destination"
    dest_dir.mkdir()

    # Pre-create 720p movie in destination
    movie_folder = dest_dir / "Movies" / "Inception (2010)"
    movie_folder.mkdir(parents=True)
    existing_dest = movie_folder / "Inception (2010) [720p].mkv"
    existing_dest.write_bytes(b"\x1a\x45\xdf\xa3lower quality 720p")

    # Incoming 2160p version in staging
    incoming = staging_dir / "Inception.2010.2160p.mkv"
    incoming.write_bytes(b"\x1a\x45\xdf\xa3higher quality 2160p")

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=staging_dir, staging_dir=staging_dir, destination_dir=dest_dir
        ),
        general=GeneralConfig(mode="copy", dry_run=False),
        video=VideoConfig(
            enabled=True,
            workflow_mode=VideoWorkflowMode.DIRECT,
        ),
    )

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    # Verify incoming 2160p upgraded/replaced or added to movie folder
    dest_2160 = movie_folder / "Inception (2010) [2160p].mkv"
    assert dest_2160.exists()
    assert summary.video_summary.get("organized_movies", 0) >= 1
