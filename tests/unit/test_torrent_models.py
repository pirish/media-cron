from media_cron.torrent.models import (
    TorrentFilterConfig,
    TorrentItem,
    TorrentState,
)


def test_torrent_item_completed_and_healthy():
    item = TorrentItem(
        info_hash="aabbcc112233",
        name="Movie.2024",
        total_size=1024 * 1024 * 100,
        progress=1.0,
        state=TorrentState.SEEDING,
        save_path="/downloads",
        content_path="/downloads/Movie.2024.mkv",
        category="movies",
        tags=["hd"],
    )
    assert item.is_completed() is True
    assert item.is_healthy() is True

    # Incomplete
    incomplete = TorrentItem(
        info_hash="aabbcc112234",
        name="Incomplete.2024",
        total_size=1024 * 1024 * 100,
        progress=0.85,
        state=TorrentState.DOWNLOADING,
        save_path="/downloads",
        content_path="/downloads/Incomplete.2024.mkv",
    )
    assert incomplete.is_completed() is False
    assert incomplete.is_healthy() is True

    # Error state
    errored = TorrentItem(
        info_hash="aabbcc112235",
        name="Error.2024",
        total_size=1024 * 1024 * 100,
        progress=1.0,
        state=TorrentState.ERROR,
        save_path="/downloads",
        content_path="/downloads/Error.2024.mkv",
    )
    assert errored.is_completed() is False
    assert errored.is_healthy() is False


def test_torrent_filter_config_matching():
    filter_cfg = TorrentFilterConfig(
        categories=["movies", "tv"],
        tags=["media"],
        exclude_tags=["media-cron-processed"],
        exclude_categories=["media-cron-done"],
    )

    eligible = TorrentItem(
        info_hash="1111",
        name="Eligible.Movie",
        total_size=1000,
        progress=1.0,
        state=TorrentState.SEEDING,
        save_path="/downloads",
        content_path="/downloads/Eligible.Movie",
        category="movies",
        tags=["media", "1080p"],
    )
    assert filter_cfg.matches(eligible) is True

    # Excluded by tag
    tagged = TorrentItem(
        info_hash="2222",
        name="Tagged.Movie",
        total_size=1000,
        progress=1.0,
        state=TorrentState.SEEDING,
        save_path="/downloads",
        content_path="/downloads/Tagged.Movie",
        category="movies",
        tags=["media", "media-cron-processed"],
    )
    assert filter_cfg.matches(tagged) is False

    # Excluded by category
    wrong_cat = TorrentItem(
        info_hash="3333",
        name="Wrong.Category",
        total_size=1000,
        progress=1.0,
        state=TorrentState.SEEDING,
        save_path="/downloads",
        content_path="/downloads/Wrong.Category",
        category="music",
        tags=["media"],
    )
    assert filter_cfg.matches(wrong_cat) is False
