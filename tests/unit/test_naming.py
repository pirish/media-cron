from pathlib import Path

from media_cron.models import DiscoveredItem, MediaCategory
from media_cron.plugins.lookup.audio import AudioTagLookup
from media_cron.plugins.lookup.book import BookMetaLookup
from media_cron.plugins.lookup.video import SceneVideoLookup


def test_scene_video_naming_movie():
    lookup = SceneVideoLookup()
    item = DiscoveredItem(
        source_path=Path("/downloads/The.Matrix.1999.1080p.BluRay.x264-GROUP.mkv"),
        file_size=1000000,
        modified_time=0.0,
    )
    assert lookup.can_handle(item)
    asset = lookup.enrich(item)
    assert asset.category == MediaCategory.VIDEO_MOVIE
    assert asset.clean_title == "The Matrix"
    assert asset.year == 1999
    assert asset.resolution == "1080p"


def test_scene_video_naming_series():
    lookup = SceneVideoLookup()
    item = DiscoveredItem(
        source_path=Path("/downloads/Breaking.Bad.S05E14.720p.HDTV.x264-GRP.mp4"),
        file_size=1000000,
        modified_time=0.0,
    )
    assert lookup.can_handle(item)
    asset = lookup.enrich(item)
    assert asset.category == MediaCategory.VIDEO_SERIES
    assert asset.series_title == "Breaking Bad"
    assert asset.season_number == 5
    assert asset.episode_number == 14
    assert asset.resolution == "720p"


def test_audio_naming_fallback(tmp_path: Path):
    lookup = AudioTagLookup()
    audio_file = tmp_path / "01 - Pink Floyd - Time.mp3"
    audio_file.write_bytes(b"empty")
    item = DiscoveredItem(source_path=audio_file, file_size=100, modified_time=0.0)
    assert lookup.can_handle(item)
    asset = lookup.enrich(item)
    assert asset.category == MediaCategory.AUDIO_MUSIC
    assert asset.track_number == 1
    assert "Time" in asset.clean_title


def test_book_naming_fallback(tmp_path: Path):
    lookup = BookMetaLookup()
    book_file = tmp_path / "George Orwell - 1984 (1949).epub"
    book_file.write_bytes(b"empty")
    item = DiscoveredItem(source_path=book_file, file_size=100, modified_time=0.0)
    assert lookup.can_handle(item)
    asset = lookup.enrich(item)
    assert asset.category == MediaCategory.BOOK_EBOOK
    assert "1984" in asset.clean_title
