from pathlib import Path

import pytest

from media_cron.models import MediaAsset, MediaCategory


@pytest.fixture
def temp_dirs(tmp_path: Path):
    """Provides isolated temporary directories for source, staging, destination, and seed."""
    source_dir = tmp_path / "source"
    staging_dir = tmp_path / "staging"
    destination_dir = tmp_path / "destination"
    seed_dir = tmp_path / "seed"

    source_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)
    destination_dir.mkdir(parents=True, exist_ok=True)
    seed_dir.mkdir(parents=True, exist_ok=True)

    return {
        "source": source_dir,
        "staging": staging_dir,
        "destination": destination_dir,
        "seed": seed_dir,
    }


@pytest.fixture
def sample_video_asset(tmp_path: Path) -> MediaAsset:
    video_path = tmp_path / "staging" / "Movie.Sample.2024.1080p.mkv"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"mock video data" * 1000)
    return MediaAsset(
        path=video_path,
        category=MediaCategory.VIDEO_MOVIE,
        raw_title="Movie.Sample.2024.1080p.mkv",
        clean_title="Movie Sample",
        year=2024,
        extension=".mkv",
        file_size=video_path.stat().st_size,
        resolution="1080p",
    )
