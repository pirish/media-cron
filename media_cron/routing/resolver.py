from typing import TYPE_CHECKING

from media_cron.models import TransferMode
from media_cron.routing.base import RouteResolverProtocol
from media_cron.routing.models import (
    DestinationEndpointConfig,
    DestinationEndpointType,
    MediaRouteConfig,
    ResolvedMediaRoute,
    SourceEndpointConfig,
    SourceEndpointType,
    SupportedMediaType,
)

if TYPE_CHECKING:
    from media_cron.config import MediaCronConfig


class RouteResolver(RouteResolverProtocol):
    """Resolves per-media-type routing configurations with hierarchical fallbacks."""

    def resolve_all_routes(
        self, config: "MediaCronConfig"
    ) -> dict[SupportedMediaType, ResolvedMediaRoute]:
        routes: dict[SupportedMediaType, ResolvedMediaRoute] = {}

        # 1. Music
        routes[SupportedMediaType.MUSIC] = self.resolve_media_route(
            SupportedMediaType.MUSIC, getattr(config.music, "route", None), config
        )

        # 2. Audiobooks
        routes[SupportedMediaType.AUDIOBOOKS] = self.resolve_media_route(
            SupportedMediaType.AUDIOBOOKS,
            getattr(config.audiobook, "route", None),
            config,
        )

        # 3. Books
        routes[SupportedMediaType.BOOKS] = self.resolve_media_route(
            SupportedMediaType.BOOKS, getattr(config.books, "route", None), config
        )

        # 4. Movies
        movies_route = getattr(config.video, "movies_route", None)
        routes[SupportedMediaType.MOVIES] = self.resolve_media_route(
            SupportedMediaType.MOVIES, movies_route, config
        )

        # 5. TV
        tv_route = getattr(config.video, "tv_route", None)
        routes[SupportedMediaType.TV] = self.resolve_media_route(
            SupportedMediaType.TV, tv_route, config
        )

        return routes

    def resolve_media_route(
        self,
        media_type: SupportedMediaType,
        route_cfg: MediaRouteConfig | None,
        config: "MediaCronConfig",
    ) -> ResolvedMediaRoute:
        # 1. Transfer mode resolution
        global_mode_str = (
            config.general.mode.lower()
            if hasattr(config, "general") and config.general.mode
            else "hardlink"
        )
        mode_str = (
            route_cfg.transfer_mode.lower()
            if route_cfg and route_cfg.transfer_mode
            else global_mode_str
        )
        try:
            transfer_mode = TransferMode(mode_str)
        except ValueError:
            transfer_mode = TransferMode.HARDLINK

        # 2. Destination resolution
        destination_endpoint: DestinationEndpointConfig
        if route_cfg and route_cfg.destination and route_cfg.destination.path is not None:
            destination_endpoint = DestinationEndpointConfig(
                type=route_cfg.destination.type,
                path=route_cfg.destination.path,
                template=route_cfg.destination.template,
            )
        else:
            # Domain-specific fallbacks
            dest_root = (
                config.paths.destination_dir
                if hasattr(config, "paths") and config.paths.destination_dir
                else None
            )
            dtype = DestinationEndpointType.LIBRARY

            if media_type == SupportedMediaType.MUSIC:
                if (
                    getattr(config, "music", None)
                    and str(getattr(config.music, "workflow_mode", "")).lower() == "spool"
                    and config.music.spool_dir
                ):
                    dest_root = config.music.spool_dir
                    dtype = DestinationEndpointType.SPOOL
            elif media_type in (SupportedMediaType.MOVIES, SupportedMediaType.TV):
                if (
                    getattr(config, "video", None)
                    and str(getattr(config.video, "workflow_mode", "")).lower() == "spool"
                    and config.video.spool_dir
                ):
                    dest_root = config.video.spool_dir
                    dtype = DestinationEndpointType.SPOOL

            destination_endpoint = DestinationEndpointConfig(
                type=dtype,
                path=dest_root,
                template=None,
            )

        # 3. Sources resolution
        source_endpoints: list[SourceEndpointConfig] = []
        if route_cfg and route_cfg.sources:
            source_endpoints = list(route_cfg.sources)
        else:
            # Fallback to global paths.source_dir
            if (
                hasattr(config, "paths")
                and config.paths.source_dir
                and config.paths.source_dir.exists()
            ):
                source_endpoints.append(
                    SourceEndpointConfig(
                        type=SourceEndpointType.DIRECTORY,
                        path=config.paths.source_dir,
                    )
                )
            elif hasattr(config, "paths") and config.paths.source_dir:
                source_endpoints.append(
                    SourceEndpointConfig(
                        type=SourceEndpointType.DIRECTORY,
                        path=config.paths.source_dir,
                    )
                )

        route = ResolvedMediaRoute(
            media_type=media_type,
            source_endpoints=source_endpoints,
            destination_endpoint=destination_endpoint,
            transfer_mode=transfer_mode,
            is_active=True,
            is_healthy=True,
        )

        return route

    def validate_mount_safety(self, route: ResolvedMediaRoute) -> bool:
        if not route.destination_endpoint or not route.destination_endpoint.path:
            route.is_healthy = False
            route.validation_error = "Destination path is not configured"
            return False

        dest_path = route.destination_endpoint.path
        if not dest_path.exists():
            route.is_healthy = False
            route.validation_error = (
                f"Destination root directory '{dest_path}' does not exist on disk"
            )
            return False

        route.is_healthy = True
        route.validation_error = None
        return True
