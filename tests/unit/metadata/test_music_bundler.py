from pathlib import Path

from media_cron.metadata.models import CompanionAssetType, MusicFormat
from media_cron.metadata.music_bundler import MusicReleaseBundleAggregator


def test_bundle_single_album_with_companions(tmp_path: Path):
    album_dir = tmp_path / "Pink Floyd - Animals (1977)"
    album_dir.mkdir()
    (album_dir / "01 - Pigs on the Wing 1.flac").write_bytes(b"dummy audio 1")
    (album_dir / "02 - Dogs.flac").write_bytes(b"dummy audio 2")
    (album_dir / "cover.jpg").write_bytes(b"dummy art")
    (album_dir / "album.cue").write_text("TITLE Animals\n")
    (album_dir / "rip.log").write_text("EAC extraction logfile\n")

    aggregator = MusicReleaseBundleAggregator()
    bundles = aggregator.aggregate(album_dir)

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.album_title == "Animals" or "Animals" in bundle.album_title
    assert len(bundle.tracks) == 2
    assert all(t.format == MusicFormat.FLAC for t in bundle.tracks)
    assert len(bundle.companion_assets) == 3
    asset_types = {c.asset_type for c in bundle.companion_assets}
    assert CompanionAssetType.COVER_ART in asset_types
    assert CompanionAssetType.CUE_SHEET in asset_types
    assert CompanionAssetType.RIP_LOG in asset_types


def test_bundle_multi_disc_album(tmp_path: Path):
    album_dir = tmp_path / "The Wall (1979)"
    cd1 = album_dir / "CD1"
    cd2 = album_dir / "CD2"
    cd1.mkdir(parents=True)
    cd2.mkdir(parents=True)

    (cd1 / "01 - In the Flesh.mp3").write_bytes(b"audio cd1")
    (cd2 / "01 - Hey You.mp3").write_bytes(b"audio cd2")
    (album_dir / "folder.png").write_bytes(b"art")

    aggregator = MusicReleaseBundleAggregator()
    bundles = aggregator.aggregate(album_dir)

    assert len(bundles) == 1
    bundle = bundles[0]
    assert len(bundle.tracks) == 2
    assert bundle.total_discs == 2
    assert len(bundle.companion_assets) == 1
    assert bundle.companion_assets[0].asset_type == CompanionAssetType.COVER_ART


def test_bundle_empty_or_non_audio_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    (empty_dir / "notes.txt").write_text("Just notes")

    aggregator = MusicReleaseBundleAggregator()
    bundles = aggregator.aggregate(empty_dir)
    assert bundles == []
