from pathlib import Path

from media_cron.models import DiscoveredItem, MediaAsset, MediaCategory, TransferMode
from media_cron.routing.base import MediaRoutingEngineProtocol
from media_cron.routing.engine import MediaRoutingEngine
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    ResolvedMediaRoute,
    SourceEndpointConfig,
    SourceEndpointType,
    SupportedMediaType,
)


def test_media_routing_engine_satisfies_protocol():
    engine = MediaRoutingEngine()
    assert isinstance(engine, MediaRoutingEngineProtocol)


def test_discover_route_items_contract(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    file1 = src_dir / "sample.mp3"
    file1.write_bytes(b"ID3" + b"\x00" * 30)

    route = ResolvedMediaRoute(
        media_type=SupportedMediaType.MUSIC,
        source_endpoints=[SourceEndpointConfig(type=SourceEndpointType.DIRECTORY, path=src_dir)],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=tmp_path / "dest",
        ),
        transfer_mode=TransferMode.COPY,
    )

    engine = MediaRoutingEngine()
    items = list(engine.discover_route_items(route, staging_dir=tmp_path / "staging"))

    assert len(items) == 1
    assert isinstance(items[0], DiscoveredItem)
    assert items[0].source_media_type == SupportedMediaType.MUSIC


def test_validate_source_type_match_contract():
    engine = MediaRoutingEngine()
    music_asset = MediaAsset(
        path=Path("/tmp/song.flac"),
        category=MediaCategory.AUDIO_MUSIC,
        raw_title="Song",
        clean_title="Song",
        extension=".flac",
        file_size=1000,
    )

    assert engine.validate_source_type_match(music_asset, SupportedMediaType.MUSIC) is True
    assert engine.validate_source_type_match(music_asset, SupportedMediaType.MOVIES) is False
    assert engine.validate_source_type_match(music_asset, None) is True


def test_resolve_target_destination_contract(tmp_path: Path):
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    route = ResolvedMediaRoute(
        media_type=SupportedMediaType.MUSIC,
        source_endpoints=[],
        destination_endpoint=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=dest_dir,
        ),
        transfer_mode=TransferMode.COPY,
    )
    music_asset = MediaAsset(
        path=Path("/tmp/song.flac"),
        category=MediaCategory.AUDIO_MUSIC,
        raw_title="Song",
        clean_title="Song",
        extension=".flac",
        file_size=1000,
        artist="Artist",
        album="Album",
    )

    engine = MediaRoutingEngine()
    target = engine.resolve_target_destination(music_asset, route)
    assert isinstance(target, Path)
    assert str(target).startswith(str(dest_dir))
