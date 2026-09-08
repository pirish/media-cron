from pathlib import Path

from media_cron.config import MediaCronConfig
from media_cron.models import MediaAsset, MediaCategory
from media_cron.pipeline import Pipeline


def test_custom_movie_path_template(tmp_path: Path):
    cfg = MediaCronConfig()
    cfg.paths.destination_dir = tmp_path / "media"
    cfg.templates["movie"] = "Cinema/{year}/{title}.{ext}"

    pipeline = Pipeline(config=cfg)
    asset = MediaAsset(
        path=Path("sample.mkv"),
        category=MediaCategory.VIDEO_MOVIE,
        raw_title="sample.mkv",
        clean_title="Inception",
        year=2010,
        extension=".mkv",
        file_size=1000,
    )
    dest = pipeline._resolve_destination_path(asset)
    assert dest == tmp_path / "media" / "Cinema" / "2010" / "Inception.mkv"


def test_custom_series_path_template(tmp_path: Path):
    cfg = MediaCronConfig()
    cfg.paths.destination_dir = tmp_path / "media"
    cfg.templates["series"] = (
        "Shows/{show}/S{season:02d}/{show} - S{season:02d}E{episode:02d}.{ext}"
    )

    pipeline = Pipeline(config=cfg)
    asset = MediaAsset(
        path=Path("sample.mp4"),
        category=MediaCategory.VIDEO_SERIES,
        raw_title="sample.mp4",
        clean_title="Dark - S01E01",
        series_title="Dark",
        season_number=1,
        episode_number=1,
        extension=".mp4",
        file_size=1000,
    )
    dest = pipeline._resolve_destination_path(asset)
    assert dest == tmp_path / "media" / "Shows" / "Dark" / "S01" / "Dark - S01E01.mp4"
