from pathlib import Path

import pytest

from media_cron.models import DiscoveredItem, MediaCategory
from media_cron.plugins.lookup.video import SceneVideoLookup


@pytest.fixture
def video_lookup() -> SceneVideoLookup:
    return SceneVideoLookup()


def test_parse_movie_standard_scene(video_lookup: SceneVideoLookup):
    item = DiscoveredItem(
        source_path=Path("/staging/Inception.2010.1080p.BluRay.x264.mkv"),
        file_size=1024 * 1024 * 500,
        modified_time=1000.0,
        is_archive=False,
        is_directory=False,
    )
    asset = video_lookup.enrich(item)
    assert asset.category == MediaCategory.VIDEO_MOVIE
    assert asset.clean_title == "Inception"
    assert asset.year == 2010
    assert asset.resolution == "1080p"


def test_parse_movie_with_brackets(video_lookup: SceneVideoLookup):
    item = DiscoveredItem(
        source_path=Path("/staging/Dune.Part.Two.(2024).[2160p].UHD.mkv"),
        file_size=1024 * 1024 * 500,
        modified_time=1000.0,
        is_archive=False,
        is_directory=False,
    )
    asset = video_lookup.enrich(item)
    assert asset.category == MediaCategory.VIDEO_MOVIE
    assert asset.clean_title == "Dune Part Two"
    assert asset.year == 2024
    assert asset.resolution == "2160p"


def test_parse_tv_standard_s01e01(video_lookup: SceneVideoLookup):
    item = DiscoveredItem(
        source_path=Path("/staging/Breaking.Bad.S05E16.Felina.1080p.BluRay.mkv"),
        file_size=1024 * 1024 * 500,
        modified_time=1000.0,
        is_archive=False,
        is_directory=False,
    )
    asset = video_lookup.enrich(item)
    assert asset.category == MediaCategory.VIDEO_SERIES
    assert asset.series_title == "Breaking Bad"
    assert asset.season_number == 5
    assert asset.episode_number == 16
    assert asset.clean_title == "Felina" or "S05E16" in asset.clean_title
    assert asset.resolution == "1080p"


def test_parse_tv_alt_format_and_multi_episode(video_lookup: SceneVideoLookup):
    # 1x09 format
    item1 = DiscoveredItem(
        source_path=Path("/staging/Game.of.Thrones.1x09.Baelor.720p.mkv"),
        file_size=1024 * 1024 * 500,
        modified_time=1000.0,
        is_archive=False,
        is_directory=False,
    )
    asset1 = video_lookup.enrich(item1)
    assert asset1.category == MediaCategory.VIDEO_SERIES
    assert asset1.series_title == "Game of Thrones"
    assert asset1.season_number == 1
    assert asset1.episode_number == 9
    assert asset1.resolution == "720p"

    # Multi-episode S01E01-E02
    item2 = DiscoveredItem(
        source_path=Path("/staging/House.of.the.Dragon.S01E01-E02.1080p.mkv"),
        file_size=1024 * 1024 * 500,
        modified_time=1000.0,
        is_archive=False,
        is_directory=False,
    )
    asset2 = video_lookup.enrich(item2)
    assert asset2.category == MediaCategory.VIDEO_SERIES
    assert asset2.series_title == "House of the Dragon"
    assert asset2.season_number == 1
    assert asset2.episode_number == 1
    assert getattr(asset2, "episode_end_number", None) == 2 or "E01-E02" in asset2.clean_title
