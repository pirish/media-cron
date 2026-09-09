from pathlib import Path

import pytest

from media_cron.metadata.models import (
    CompanionAssetType,
    MusicCompanionAsset,
    MusicFormat,
    MusicReleaseBundle,
    MusicTrack,
)
from media_cron.metadata.music_spooler import MusicSpoolEngine


@pytest.fixture
def sample_bundle(tmp_path: Path) -> MusicReleaseBundle:
    src_dir = tmp_path / "source" / "Artist - Album"
    src_dir.mkdir(parents=True)
    t1 = src_dir / "01 - Track 1.flac"
    t1.write_bytes(b"track 1 flac content")
    t2 = src_dir / "02 - Track 2.flac"
    t2.write_bytes(b"track 2 flac content")
    art = src_dir / "cover.jpg"
    art.write_bytes(b"jpeg image bytes")

    tracks = [
        MusicTrack(
            path=t1,
            format=MusicFormat.FLAC,
            file_size=t1.stat().st_size,
            title="Track 1",
            artist="Artist",
            album="Album",
            track_number=1,
        ),
        MusicTrack(
            path=t2,
            format=MusicFormat.FLAC,
            file_size=t2.stat().st_size,
            title="Track 2",
            artist="Artist",
            album="Album",
            track_number=2,
        ),
    ]
    companions = [
        MusicCompanionAsset(
            path=art,
            asset_type=CompanionAssetType.COVER_ART,
            file_size=art.stat().st_size,
        )
    ]
    return MusicReleaseBundle(
        bundle_id="test-bundle-001",
        root_path=src_dir,
        album_title="Album",
        album_artist="Artist",
        tracks=tracks,
        companion_assets=companions,
    )


def test_stage_and_promote_bundle(tmp_path: Path, sample_bundle: MusicReleaseBundle):
    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()

    engine = MusicSpoolEngine()
    staging_path = engine.stage_bundle(sample_bundle, spool_dir)

    # Staging path should be hidden (.incoming_*) within spool_dir
    assert staging_path.parent == spool_dir
    assert staging_path.name.startswith(".incoming_")
    assert (staging_path / "01 - Track 1.flac").exists()
    assert (staging_path / "cover.jpg").exists()

    # Promote to final release dir
    final_target = spool_dir / sample_bundle.root_path.name
    final_path = engine.promote_bundle(staging_path, final_target)

    assert final_path == final_target
    assert final_path.exists()
    assert not staging_path.exists()
    assert (final_path / "01 - Track 1.flac").exists()
    assert (final_path / "cover.jpg").exists()


def test_spool_release_full_workflow(tmp_path: Path, sample_bundle: MusicReleaseBundle):
    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()

    engine = MusicSpoolEngine()
    result = engine.spool_release(
        bundle=sample_bundle,
        spool_dir=spool_dir,
        post_command=None,
        dry_run=False,
    )

    assert result.success is True
    assert result.file_count == 3
    assert result.target_dir.exists()
    assert not any(p.name.startswith(".incoming_") for p in spool_dir.iterdir())


def test_spool_release_dry_run(tmp_path: Path, sample_bundle: MusicReleaseBundle):
    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()

    engine = MusicSpoolEngine()
    result = engine.spool_release(
        bundle=sample_bundle,
        spool_dir=spool_dir,
        post_command="echo 'imported {release_path}'",
        dry_run=True,
    )

    assert result.success is True
    assert result.file_count == 3
    # Nothing actually written to spool directory in dry run
    assert list(spool_dir.iterdir()) == []


def test_execute_post_command(tmp_path: Path):
    engine = MusicSpoolEngine()
    rel_path = tmp_path / "test_album"
    rel_path.mkdir()

    exit_code, output = engine.execute_post_command(
        command_template="echo 'SUCCESS: {release_path}'",
        release_path=rel_path,
        timeout_seconds=5,
    )
    assert exit_code == 0
    assert f"SUCCESS: {rel_path}" in output
