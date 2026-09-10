from pathlib import Path

import pytest

from media_cron.metadata.models import (
    VideoCompanionAsset,
    VideoCompanionType,
    VideoFormat,
    VideoReleaseBundle,
    VideoTrack,
)
from media_cron.metadata.video_spooler import VideoSpoolEngine


@pytest.fixture
def sample_video_bundle(tmp_path: Path) -> VideoReleaseBundle:
    src_dir = tmp_path / "source" / "Dune.Part.Two.2024.2160p"
    src_dir.mkdir(parents=True)
    mkv = src_dir / "Dune.Part.Two.2024.2160p.mkv"
    mkv.write_bytes(b"dummy video data " * 500)
    srt = src_dir / "Dune.Part.Two.2024.2160p.en.srt"
    srt.write_text("1\n00:00:01 --> 00:00:04\nSub")
    poster = src_dir / "poster.jpg"
    poster.write_bytes(b"poster bytes")

    tracks = [
        VideoTrack(
            path=mkv,
            title="Dune Part Two",
            file_size=mkv.stat().st_size,
            format=VideoFormat.MKV,
            year=2024,
            resolution="2160p",
        )
    ]
    companions = [
        VideoCompanionAsset(
            path=srt,
            asset_type=VideoCompanionType.SUBTITLE,
            file_size=srt.stat().st_size,
            language="en",
        ),
        VideoCompanionAsset(
            path=poster, asset_type=VideoCompanionType.ARTWORK, file_size=poster.stat().st_size
        ),
    ]
    return VideoReleaseBundle(
        bundle_id="video-bundle-001",
        root_path=src_dir,
        release_title="Dune Part Two 2024 2160p",
        primary_videos=tracks,
        companion_assets=companions,
    )


def test_stage_and_promote_video_bundle(tmp_path: Path, sample_video_bundle: VideoReleaseBundle):
    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()

    engine = VideoSpoolEngine()
    staging_path = engine.stage_bundle(sample_video_bundle, spool_dir)

    assert staging_path.parent == spool_dir
    assert staging_path.name.startswith(".incoming_")
    assert (staging_path / "Dune.Part.Two.2024.2160p.mkv").exists()
    assert (staging_path / "Dune.Part.Two.2024.2160p.en.srt").exists()
    assert (staging_path / "poster.jpg").exists()

    final_target = spool_dir / sample_video_bundle.root_path.name
    final_path = engine.promote_bundle(staging_path, final_target)

    assert final_path == final_target
    assert final_path.exists()
    assert not staging_path.exists()
    assert (final_path / "Dune.Part.Two.2024.2160p.mkv").exists()


def test_spool_release_collision_skipping(tmp_path: Path, sample_video_bundle: VideoReleaseBundle):
    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()

    # Pre-create the destination release directory in spool_dir to induce collision
    existing_dest = spool_dir / sample_video_bundle.root_path.name
    existing_dest.mkdir()
    (existing_dest / "existing.txt").write_text("prior import")

    engine = VideoSpoolEngine()
    result = engine.spool_release(
        bundle=sample_video_bundle,
        spool_dir=spool_dir,
    )

    assert result.skipped is True
    assert result.skip_reason is not None
    assert "already exists" in result.skip_reason
    # Ensure no lingering staging folders
    assert not any(p.name.startswith(".incoming_") for p in spool_dir.iterdir())
    # Ensure source was not touched or destroyed
    assert (sample_video_bundle.root_path / "Dune.Part.Two.2024.2160p.mkv").exists()


def test_spool_release_full_workflow_with_post_command(
    tmp_path: Path, sample_video_bundle: VideoReleaseBundle
):
    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()
    log_file = tmp_path / "hook.log"

    engine = VideoSpoolEngine()
    result = engine.spool_release(
        bundle=sample_video_bundle,
        spool_dir=spool_dir,
        post_command=f"echo 'Spool finished for {{release_path}}' > {log_file}",
        dry_run=False,
    )

    assert result.success is True
    assert result.skipped is False
    assert result.file_count == 3
    assert result.post_command_executed is True
    assert result.post_command_exit_code == 0
    assert log_file.exists()
    assert str(spool_dir / sample_video_bundle.root_path.name) in log_file.read_text()


def test_spool_release_dry_run(tmp_path: Path, sample_video_bundle: VideoReleaseBundle):
    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()

    engine = VideoSpoolEngine()
    result = engine.spool_release(
        bundle=sample_video_bundle,
        spool_dir=spool_dir,
        post_command="echo 'should not run'",
        dry_run=True,
    )

    assert result.success is True
    assert result.file_count == 3
    assert list(spool_dir.iterdir()) == []
