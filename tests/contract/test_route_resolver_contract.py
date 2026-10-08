from pathlib import Path

from media_cron.config import MediaCronConfig, PathsConfig
from media_cron.models import TransferMode
from media_cron.routing.base import RouteResolverProtocol
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    MediaRouteConfig,
    SourceEndpointConfig,
    SourceEndpointType,
    SupportedMediaType,
)
from media_cron.routing.resolver import RouteResolver


def test_route_resolver_implements_protocol():
    resolver = RouteResolver()
    assert isinstance(resolver, RouteResolverProtocol)


def test_resolve_all_routes_hierarchical_fallbacks(tmp_path: Path):
    global_source = tmp_path / "global_src"
    global_dest = tmp_path / "global_dest"
    global_source.mkdir()
    global_dest.mkdir()

    cfg = MediaCronConfig(paths=PathsConfig(source_dir=global_source, destination_dir=global_dest))

    resolver = RouteResolver()
    routes = resolver.resolve_all_routes(cfg)

    # Must resolve all 5 media types
    assert set(routes.keys()) == {
        SupportedMediaType.MUSIC,
        SupportedMediaType.AUDIOBOOKS,
        SupportedMediaType.BOOKS,
        SupportedMediaType.MOVIES,
        SupportedMediaType.TV,
    }

    # All must fall back to global paths and default transfer mode (hardlink)
    for media_type, route in routes.items():
        assert route.media_type == media_type
        assert route.transfer_mode == TransferMode.HARDLINK
        assert route.destination_endpoint.type == DestinationEndpointType.LIBRARY
        assert route.destination_endpoint.path == global_dest
        assert len(route.source_endpoints) == 1
        assert route.source_endpoints[0].type == SourceEndpointType.DIRECTORY
        assert route.source_endpoints[0].path == global_source
        assert route.is_healthy is True


def test_resolve_route_with_custom_overrides(tmp_path: Path):
    global_dest = tmp_path / "global_dest"
    custom_dest = tmp_path / "custom_music"
    custom_src1 = tmp_path / "src1"
    custom_src2 = tmp_path / "src2"
    global_dest.mkdir()
    custom_dest.mkdir()
    custom_src1.mkdir()
    custom_src2.mkdir()

    cfg = MediaCronConfig(paths=PathsConfig(destination_dir=global_dest))
    cfg.music.route = MediaRouteConfig(
        transfer_mode="copy",
        sources=[
            SourceEndpointConfig(type=SourceEndpointType.DIRECTORY, path=custom_src1),
            SourceEndpointConfig(type=SourceEndpointType.DIRECTORY, path=custom_src2),
        ],
        destination=DestinationEndpointConfig(
            type=DestinationEndpointType.LIBRARY,
            path=custom_dest,
        ),
    )

    resolver = RouteResolver()
    routes = resolver.resolve_all_routes(cfg)

    music_route = routes[SupportedMediaType.MUSIC]
    assert music_route.transfer_mode == TransferMode.COPY
    assert music_route.destination_endpoint.path == custom_dest
    assert len(music_route.source_endpoints) == 2
    assert music_route.source_endpoints[0].path == custom_src1
    assert music_route.source_endpoints[1].path == custom_src2

    # Books must still fall back to global
    books_route = routes[SupportedMediaType.BOOKS]
    assert books_route.transfer_mode == TransferMode.HARDLINK
    assert books_route.destination_endpoint.path == global_dest


def test_mount_safety_validation(tmp_path: Path):
    existing_dest = tmp_path / "existing_mount"
    existing_dest.mkdir()
    missing_dest = tmp_path / "missing_unmounted_mount"

    cfg = MediaCronConfig()
    cfg.video.movies_route = MediaRouteConfig(
        destination=DestinationEndpointConfig(path=missing_dest)
    )
    cfg.music.route = MediaRouteConfig(destination=DestinationEndpointConfig(path=existing_dest))

    resolver = RouteResolver()
    routes = resolver.resolve_all_routes(cfg)

    movies_route = routes[SupportedMediaType.MOVIES]
    music_route = routes[SupportedMediaType.MUSIC]

    assert resolver.validate_mount_safety(music_route) is True
    assert music_route.is_healthy is True

    assert resolver.validate_mount_safety(movies_route) is False
    assert movies_route.is_healthy is False
    assert "does not exist" in (movies_route.validation_error or "")
