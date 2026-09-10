from pathlib import Path

from media_cron.metadata.models import VideoCompanionType, VideoFormat
from media_cron.metadata.video_bundler import VideoReleaseBundleAggregator


def test_bundle_movie_release_with_companions(tmp_path: Path):
    rel_dir = tmp_path / "Dune.Part.Two.2024.2160p"
    rel_dir.mkdir()
    (rel_dir / "Dune.Part.Two.2024.2160p.mkv").write_bytes(b"dummy video data " * 1000)
    (rel_dir / "Dune.Part.Two.2024.2160p.en.srt").write_text("1\n00:00:01 --> 00:00:04\nSub")
    (rel_dir / "poster.jpg").write_bytes(b"dummy poster")
    (rel_dir / "movie.nfo").write_text("<movie><title>Dune: Part Two</title></movie>")
    # Sample file under 50MB should be filtered
    (rel_dir / "sample.mkv").write_bytes(b"sample video data")

    aggregator = VideoReleaseBundleAggregator()
    bundles = aggregator.aggregate(rel_dir)

    assert len(bundles) == 1
    bundle = bundles[0]
    assert "Dune" in bundle.release_title
    assert len(bundle.primary_videos) == 1
    assert bundle.primary_videos[0].format == VideoFormat.MKV
    assert not bundle.primary_videos[0].is_sample
    assert len(bundle.companion_assets) == 3

    types = {c.asset_type for c in bundle.companion_assets}
    assert VideoCompanionType.SUBTITLE in types
    assert VideoCompanionType.ARTWORK in types
    assert VideoCompanionType.METADATA_NFO in types

    sub_asset = next(
        c for c in bundle.companion_assets if c.asset_type == VideoCompanionType.SUBTITLE
    )
    assert sub_asset.language == "en"


def test_bundle_tv_series_season(tmp_path: Path):
    series_dir = tmp_path / "Breaking.Bad.S01"
    series_dir.mkdir()
    (series_dir / "Breaking.Bad.S01E01.1080p.mkv").write_bytes(b"ep1 data " * 500)
    (series_dir / "Breaking.Bad.S01E02.1080p.mkv").write_bytes(b"ep2 data " * 500)
    subs_dir = series_dir / "Subs"
    subs_dir.mkdir()
    (subs_dir / "Breaking.Bad.S01E01.eng.forced.srt").write_text("sub ep1")
    (subs_dir / "Breaking.Bad.S01E02.eng.srt").write_text("sub ep2")

    aggregator = VideoReleaseBundleAggregator()
    bundles = aggregator.aggregate(series_dir)

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.is_series is True
    assert len(bundle.primary_videos) == 2
    assert len(bundle.companion_assets) == 2


def test_bundle_single_file(tmp_path: Path):
    single_file = tmp_path / "Standalone.Movie.2023.mp4"
    single_file.write_bytes(b"video data " * 500)

    aggregator = VideoReleaseBundleAggregator()
    bundles = aggregator.aggregate(single_file)

    assert len(bundles) == 1
    bundle = bundles[0]
    assert len(bundle.primary_videos) == 1
    assert bundle.primary_videos[0].format == VideoFormat.MP4


def test_bundle_empty_or_non_video_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    (empty_dir / "notes.txt").write_text("Random notes")

    aggregator = VideoReleaseBundleAggregator()
    bundles = aggregator.aggregate(empty_dir)
    assert bundles == []
