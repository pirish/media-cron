from pathlib import Path

from media_cron.config import MediaCronConfig, PathsConfig
from media_cron.pipeline import Pipeline
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    MediaRouteConfig,
)


def test_per_media_destination_routing_integration(tmp_path: Path):
    source_dir = tmp_path / "incoming"
    staging_dir = tmp_path / "staging"
    fallback_dir = tmp_path / "fallback"
    music_dest = tmp_path / "dest_music"
    movies_dest = tmp_path / "dest_movies"

    source_dir.mkdir()
    staging_dir.mkdir()
    fallback_dir.mkdir()
    music_dest.mkdir()
    movies_dest.mkdir()

    # Create dummy files
    music_file = source_dir / "Daft Punk - Discovery - 01 - One More Time.flac"
    music_file.write_bytes(b"fLaC" + b"\x00" * 50)

    movie_file = source_dir / "Inception.2010.1080p.mkv"
    movie_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)

    # Configure pipeline with per-media destination routes
    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=source_dir,
            staging_dir=staging_dir,
            destination_dir=fallback_dir,
        )
    )
    cfg.general.mode = "copy"
    cfg.music.enabled = True
    cfg.music.route = MediaRouteConfig(
        destination=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=music_dest,
        )
    )
    cfg.video.enabled = True
    cfg.video.movies_route = MediaRouteConfig(
        destination=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=movies_dest,
        )
    )

    pipeline = Pipeline(cfg)
    summary = pipeline.run()

    assert summary.exit_code == 0
    assert summary.processed_count >= 2

    # Verify music is in music_dest
    music_results = list(music_dest.rglob("*.flac"))
    assert len(music_results) == 1

    # Verify movie is in movies_dest
    movie_results = list(movies_dest.rglob("*.mkv"))
    assert len(movie_results) == 1

    # Fallback directory must remain empty
    fallback_results = list(fallback_dir.rglob("*"))
    assert len(fallback_results) == 0


def test_missing_destination_mount_safety_skips_unhealthy_route(tmp_path: Path):
    source_dir = tmp_path / "incoming"
    staging_dir = tmp_path / "staging"
    music_dest = tmp_path / "dest_music"
    missing_movies_dest = tmp_path / "unmounted_drive" / "movies"

    source_dir.mkdir()
    staging_dir.mkdir()
    music_dest.mkdir()

    # Create files
    music_file = source_dir / "Artist - Album - 01 - Song.flac"
    music_file.write_bytes(b"fLaC" + b"\x00" * 50)
    movie_file = source_dir / "Movie.2023.1080p.mkv"
    movie_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=source_dir,
            staging_dir=staging_dir,
        )
    )
    cfg.general.mode = "copy"
    cfg.music.enabled = True
    cfg.music.route = MediaRouteConfig(
        destination=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=music_dest,
        )
    )
    cfg.video.enabled = True
    cfg.video.movies_route = MediaRouteConfig(
        destination=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=missing_movies_dest,
        )
    )

    pipeline = Pipeline(cfg)
    summary = pipeline.run()
    assert summary.exit_code == 0

    # Music succeeds
    assert len(list(music_dest.rglob("*.flac"))) == 1

    # Missing mount was NOT created and movie was not written to missing mount
    assert not missing_movies_dest.exists()
