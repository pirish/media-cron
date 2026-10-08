from datetime import UTC, datetime
from pathlib import Path

from media_cron.config import MediaCronConfig, PathsConfig
from media_cron.models import BatchSummary
from media_cron.pipeline import Pipeline
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    MediaRouteConfig,
    MediaRouteSummary,
)


def test_media_route_summary_model():
    summary = MediaRouteSummary(
        media_type="music",
        source_count=2,
        destination_path="/mnt/music",
        destination_type="library",
        transfer_mode="hardlink",
        scanned_count=10,
        processed_count=8,
        spooled_count=0,
        review_staged_count=2,
        skipped_count=0,
        error_count=0,
        errors=[],
    )

    data = summary.to_dict()
    assert data["media_type"] == "music"
    assert data["source_count"] == 2
    assert data["destination_path"] == "/mnt/music"
    assert data["destination_type"] == "library"
    assert data["transfer_mode"] == "hardlink"
    assert data["scanned_count"] == 10
    assert data["processed_count"] == 8
    assert data["review_staged_count"] == 2


def test_batch_summary_serializes_routing_summary():
    route_sum = MediaRouteSummary(
        media_type="movies",
        source_count=1,
        destination_path="/mnt/movies",
        destination_type="spool",
        transfer_mode="copy",
        processed_count=3,
    )

    batch = BatchSummary(
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        routing_summary={"movies": route_sum},
    )

    data = batch.to_dict()
    assert "routing_summary" in data
    assert "movies" in data["routing_summary"]
    assert data["routing_summary"]["movies"]["destination_type"] == "spool"
    assert data["routing_summary"]["movies"]["processed_count"] == 3


def test_pipeline_populates_routing_summary(tmp_path: Path):
    source_dir = tmp_path / "source"
    staging_dir = tmp_path / "staging"
    music_dest = tmp_path / "music"
    source_dir.mkdir()
    staging_dir.mkdir()
    music_dest.mkdir()

    music_file = source_dir / "Artist - Album - 01 - Song.flac"
    music_file.write_bytes(b"fLaC" + b"\x00" * 50)

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
            type=DestinationEndpointType.LIBRARY, path=music_dest
        ),
    )

    pipeline = Pipeline(cfg)
    summary = pipeline.run()

    assert summary.exit_code == 0
    assert "music" in summary.routing_summary
    music_summary = summary.routing_summary["music"]
    if isinstance(music_summary, dict):
        assert music_summary["processed_count"] >= 1
        assert music_summary["destination_path"] == str(music_dest)
    else:
        assert music_summary.processed_count >= 1
        assert music_summary.destination_path == str(music_dest)
