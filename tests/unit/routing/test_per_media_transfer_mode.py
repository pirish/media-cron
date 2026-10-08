from pathlib import Path

from media_cron.config import MediaCronConfig, PathsConfig
from media_cron.models import OperationType, TransferMode
from media_cron.pipeline import Pipeline
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    MediaRouteConfig,
)


def test_pipeline_applies_route_specific_transfer_modes(tmp_path: Path):
    source_dir = tmp_path / "source"
    staging_dir = tmp_path / "staging"
    music_dest = tmp_path / "music_lib"
    movies_dest = tmp_path / "movies_lib"

    source_dir.mkdir()
    staging_dir.mkdir()
    music_dest.mkdir()
    movies_dest.mkdir()

    # Create dummy files
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
    # Global default is copy
    cfg.general.mode = "copy"

    # Music overrides to hardlink
    cfg.music.enabled = True
    cfg.music.route = MediaRouteConfig(
        destination=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY, path=music_dest
        ),
        transfer_mode="hardlink",
    )

    # Movies has no override -> should fall back to global copy
    cfg.video.enabled = True
    cfg.video.movies_route = MediaRouteConfig(
        destination=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY, path=movies_dest
        ),
    )

    pipeline = Pipeline(cfg)
    plans, discovered, _ = pipeline.plan(source_dir, staging_dir)

    organize_plans = [p for p in plans if p.op_type == OperationType.ORGANIZE]
    assert len(organize_plans) == 2

    music_plan = next(p for p in organize_plans if p.source_path.suffix == ".flac")
    movie_plan = next(p for p in organize_plans if p.source_path.suffix == ".mkv")

    # Verify music used route transfer mode: hardlink
    assert music_plan.transfer_mode == TransferMode.HARDLINK

    # Verify movie used global fallback transfer mode: copy
    assert movie_plan.transfer_mode == TransferMode.COPY


def test_companion_files_inherit_route_transfer_mode(tmp_path: Path):
    source_dir = tmp_path / "source"
    staging_dir = tmp_path / "staging"
    movies_dest = tmp_path / "movies_lib"

    source_dir.mkdir()
    staging_dir.mkdir()
    movies_dest.mkdir()

    movie_file = source_dir / "Movie.2023.1080p.mkv"
    movie_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 50)
    sub_file = source_dir / "Movie.2023.1080p.en.srt"
    sub_file.write_text("1\n00:00:01 --> 00:00:02\nSubtitle")

    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=source_dir,
            staging_dir=staging_dir,
        )
    )
    cfg.general.mode = "copy"
    cfg.video.enabled = True
    # Movies route overrides transfer mode to move
    cfg.video.movies_route = MediaRouteConfig(
        destination=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY, path=movies_dest
        ),
        transfer_mode="move",
    )

    pipeline = Pipeline(cfg)
    plans, discovered, _ = pipeline.plan(source_dir, staging_dir)

    organize_plans = [p for p in plans if p.op_type == OperationType.ORGANIZE]
    assert len(organize_plans) == 2

    movie_plan = next(p for p in organize_plans if p.source_path.suffix == ".mkv")
    sub_plan = next(p for p in organize_plans if p.source_path.suffix == ".srt")

    assert movie_plan.transfer_mode == TransferMode.MOVE
    assert sub_plan.transfer_mode == TransferMode.MOVE
