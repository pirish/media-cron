from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from media_cron.models import DiscoveredItem, MediaAsset
from media_cron.routing.models import (
    MediaRouteConfig,
    ResolvedMediaRoute,
    SupportedMediaType,
)

if TYPE_CHECKING:
    from media_cron.config import MediaCronConfig


@runtime_checkable
class RouteResolverProtocol(Protocol):
    """Protocol for resolving media-type routing configurations."""

    def resolve_all_routes(
        self, config: "MediaCronConfig"
    ) -> dict[SupportedMediaType, ResolvedMediaRoute]:
        """Resolves routes for all supported media types with hierarchical fallbacks."""
        ...

    def resolve_media_route(
        self,
        media_type: SupportedMediaType,
        route_cfg: MediaRouteConfig | None,
        config: "MediaCronConfig",
    ) -> ResolvedMediaRoute:
        """Resolves an individual media route with fallback resolution."""
        ...

    def validate_mount_safety(self, route: ResolvedMediaRoute) -> bool:
        """Validates that the route's destination root path exists on disk."""
        ...


@runtime_checkable
class MediaRoutingEngineProtocol(Protocol):
    """Coordinates intake, filtering, and target resolution across media routes."""

    def discover_route_items(
        self,
        route: ResolvedMediaRoute,
        staging_dir: Path,
        dry_run: bool = False,
    ) -> Iterable[DiscoveredItem]:
        """Queries all source endpoints associated with the route."""
        ...

    def validate_source_type_match(
        self,
        asset: MediaAsset,
        source_media_type: SupportedMediaType | None,
    ) -> bool:
        """Verifies if identified MediaCategory matches source_media_type."""
        ...

    def resolve_target_destination(
        self,
        asset: MediaAsset,
        route: ResolvedMediaRoute,
    ) -> Path:
        """Computes the target file path based on destination endpoint."""
        ...
