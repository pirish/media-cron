from pathlib import Path
from unittest.mock import MagicMock, patch

from media_cron.config import MediaCronConfig, TorrentClientConfig
from media_cron.models import TransferMode
from media_cron.routing.engine import MediaRoutingEngine
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    ResolvedMediaRoute,
    SourceEndpointConfig,
    SourceEndpointType,
    SupportedMediaType,
)


def test_aggregate_multiple_directories(tmp_path: Path):
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()

    file1 = dir1 / "book1.epub"
    file1.write_bytes(b"PK\x03\x04" + b"\x00" * 30)

    file2 = dir2 / "book2.epub"
    file2.write_bytes(b"PK\x03\x04" + b"\x00" * 30)

    route = ResolvedMediaRoute(
        media_type=SupportedMediaType.BOOKS,
        source_endpoints=[
            SourceEndpointConfig(type=SourceEndpointType.DIRECTORY, path=dir1),
            SourceEndpointConfig(type=SourceEndpointType.DIRECTORY, path=dir2),
        ],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=tmp_path / "dest",
        ),
        transfer_mode=TransferMode.COPY,
    )

    engine = MediaRoutingEngine()
    items = list(engine.discover_route_items(route, staging_dir=tmp_path / "staging", dry_run=True))

    assert len(items) == 2
    paths = {item.source_path.resolve() for item in items}
    assert file1.resolve() in paths
    assert file2.resolve() in paths
    for item in items:
        assert item.source_media_type == SupportedMediaType.BOOKS


def test_deduplication_of_overlapping_sources(tmp_path: Path):
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()

    file1 = shared_dir / "audiobook.m4b"
    file1.write_bytes(b"\x00" * 10 + b"ftyp" + b"\x00" * 30)

    # Configure two endpoints pointing to the same directory
    route = ResolvedMediaRoute(
        media_type=SupportedMediaType.AUDIOBOOKS,
        source_endpoints=[
            SourceEndpointConfig(type=SourceEndpointType.DIRECTORY, path=shared_dir),
            SourceEndpointConfig(type=SourceEndpointType.DIRECTORY, path=shared_dir),
        ],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=tmp_path / "dest",
        ),
        transfer_mode=TransferMode.COPY,
    )

    engine = MediaRoutingEngine()
    items = list(engine.discover_route_items(route, staging_dir=tmp_path / "staging", dry_run=True))

    assert len(items) == 1
    assert items[0].source_path.resolve() == file1.resolve()


def test_torrent_source_client_profile_selection(tmp_path: Path):
    route = ResolvedMediaRoute(
        media_type=SupportedMediaType.MOVIES,
        source_endpoints=[
            SourceEndpointConfig(
                type=SourceEndpointType.TORRENT,
                client_profile="deluge_secondary",
                category="movies",
                tag="hd",
            )
        ],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=tmp_path / "dest",
        ),
        transfer_mode=TransferMode.COPY,
    )

    config = MediaCronConfig()
    config.torrent_clients["deluge_secondary"] = TorrentClientConfig(
        client_type="deluge",
        host="localhost",
        port=58846,
    )

    engine = MediaRoutingEngine(config=config)

    mock_client = MagicMock()
    mock_torrent = MagicMock()
    mock_torrent.save_path = str(tmp_path / "torrent_download")
    mock_torrent.name = "Test.Movie.2024.1080p.mkv"
    mock_torrent.category = "movies"
    mock_torrent.tags = ["hd"]
    mock_torrent.progress = 1.0
    mock_torrent.is_finished = True

    movie_dir = tmp_path / "torrent_download" / "Test.Movie.2024.1080p.mkv"
    movie_dir.mkdir(parents=True)
    video_file = movie_dir / "movie.mkv"
    video_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"\x00" * 50)

    mock_client.list_completed_torrents.return_value = [mock_torrent]
    mock_client.get_completed_torrents.return_value = [mock_torrent]

    with patch(
        "media_cron.torrent.base.TorrentClientRegistry.create_client",
        return_value=mock_client,
    ) as mock_create:
        items = list(
            engine.discover_route_items(route, staging_dir=tmp_path / "staging", dry_run=True)
        )
        assert len(items) >= 1
        assert items[0].source_media_type == SupportedMediaType.MOVIES
        assert mock_create.called
        # Check that deluge_secondary was used
        call_cfg = mock_create.call_args[0][0]
        assert call_cfg.client_type == "deluge"
