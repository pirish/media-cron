from pathlib import Path

from media_cron.config import MediaCronConfig, PathsConfig
from media_cron.models import (
    MediaAsset,
    MediaCategory,
    OperationType,
)
from media_cron.pipeline import Pipeline
from media_cron.routing.engine import MediaRoutingEngine
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    MediaRouteConfig,
    SourceEndpointConfig,
    SourceEndpointType,
    SupportedMediaType,
)


def test_validate_source_type_match_all_combinations():
    engine = MediaRoutingEngine()

    def make_asset(cat: MediaCategory):
        return MediaAsset(
            path=Path("/tmp/file"),
            category=cat,
            raw_title="Test",
            clean_title="Test",
            extension=".ext",
            file_size=100,
        )

    # Valid matches
    assert (
        engine.validate_source_type_match(
            make_asset(MediaCategory.AUDIO_MUSIC), SupportedMediaType.MUSIC
        )
        is True
    )
    assert (
        engine.validate_source_type_match(
            make_asset(MediaCategory.AUDIO_BOOK), SupportedMediaType.AUDIOBOOKS
        )
        is True
    )
    assert (
        engine.validate_source_type_match(
            make_asset(MediaCategory.BOOK_EBOOK), SupportedMediaType.BOOKS
        )
        is True
    )
    assert (
        engine.validate_source_type_match(
            make_asset(MediaCategory.VIDEO_MOVIE), SupportedMediaType.MOVIES
        )
        is True
    )
    assert (
        engine.validate_source_type_match(
            make_asset(MediaCategory.VIDEO_SERIES), SupportedMediaType.TV
        )
        is True
    )

    # None matches everything (generic / legacy)
    assert engine.validate_source_type_match(make_asset(MediaCategory.AUDIO_MUSIC), None) is True
    assert engine.validate_source_type_match(make_asset(MediaCategory.VIDEO_MOVIE), None) is True

    # Mismatches
    assert (
        engine.validate_source_type_match(
            make_asset(MediaCategory.VIDEO_MOVIE), SupportedMediaType.MUSIC
        )
        is False
    )
    assert (
        engine.validate_source_type_match(
            make_asset(MediaCategory.AUDIO_MUSIC), SupportedMediaType.MOVIES
        )
        is False
    )
    assert (
        engine.validate_source_type_match(
            make_asset(MediaCategory.BOOK_EBOOK), SupportedMediaType.AUDIOBOOKS
        )
        is False
    )
    assert (
        engine.validate_source_type_match(
            make_asset(MediaCategory.AUDIO_BOOK), SupportedMediaType.BOOKS
        )
        is False
    )


def test_pipeline_quarantines_mismatched_media_to_review(tmp_path: Path):
    source_music = tmp_path / "music_src"
    staging_dir = tmp_path / "staging"
    dest_music = tmp_path / "music_lib"
    dest_movies = tmp_path / "movies_lib"

    source_music.mkdir()
    staging_dir.mkdir()
    dest_music.mkdir()
    dest_movies.mkdir()

    # Place a MOVIE file inside the MUSIC source directory!
    mismatched_movie = source_music / "Inception.2010.1080p.mkv"
    mismatched_movie.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=source_music,
            staging_dir=staging_dir,
        )
    )
    cfg.general.mode = "copy"
    cfg.music.enabled = True
    cfg.music.route = MediaRouteConfig(
        sources=[SourceEndpointConfig(type=SourceEndpointType.DIRECTORY, path=source_music)],
        destination=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY, path=dest_music
        ),
    )
    cfg.video.enabled = True
    cfg.video.movies_route = MediaRouteConfig(
        destination=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY, path=dest_movies
        ),
    )

    pipeline = Pipeline(cfg)
    plans, discovered, _ = pipeline.plan(source_music, staging_dir)

    # The movie file from the music source should NOT be planned to dest_movies or dest_music!
    # It must be planned for REVIEW_STAGE quarantine
    assert len(plans) == 1
    plan = plans[0]
    assert plan.op_type == OperationType.REVIEW_STAGE
    assert "Mismatched media type" in plan.reason
    assert "music" in plan.reason.lower()
