# Interface Contract: Route Resolver & Routing Engine

**Feature Branch**: `009-media-source-destination-routing`
**Date**: 2026-10-07
**Spec**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

---

## 1. `RouteResolverProtocol`

Responsible for parsing configuration, applying hierarchical fallbacks, executing mount safety validation, and producing `ResolvedMediaRoute` records.

```python
from typing import Protocol
from pathlib import Path
from media_cron.config import MediaCronConfig
from specs._009_models import SupportedMediaType, ResolvedMediaRoute, MediaRouteConfig


class RouteResolverProtocol(Protocol):
    """Protocol for resolving media-type routing configurations."""

    def resolve_all_routes(
        self, config: MediaCronConfig
    ) -> dict[SupportedMediaType, ResolvedMediaRoute]:
        """
        Resolves routes for all supported media types (music, audiobooks, books, movies, tv).
        Applies hierarchical fallback:
        - If media-type route has no sources: falls back to global paths.source_dir and active_torrent_client.
        - If media-type route has no destination: falls back to paths.destination_dir.
        - If media-type route has no transfer_mode: falls back to general.mode.
        """
        ...

    def resolve_media_route(
        self,
        media_type: SupportedMediaType,
        route_cfg: MediaRouteConfig | None,
        config: MediaCronConfig,
    ) -> ResolvedMediaRoute:
        """Resolves an individual media route with fallback resolution."""
        ...

    def validate_mount_safety(self, route: ResolvedMediaRoute) -> bool:
        """
        Validates that the route's destination root path exists on disk.
        Returns True if the destination root exists or is dry-run mode.
        Returns False and marks route.is_healthy = False if root directory is missing.
        """
        ...
```

---

## 2. `MediaRoutingEngineProtocol`

Responsible for coordinating intake across multi-source endpoints, enforcing strict type filtering, and directing assets to destination endpoints.

```python
from typing import Protocol, Iterable
from pathlib import Path
from media_cron.models import DiscoveredItem, MediaAsset, OperationPlan
from specs._009_models import SupportedMediaType, ResolvedMediaRoute


class MediaRoutingEngineProtocol(Protocol):
    """Coordinates intake, filtering, and target resolution across media routes."""

    def discover_route_items(
        self,
        route: ResolvedMediaRoute,
        staging_dir: Path,
        dry_run: bool = False,
    ) -> Iterable[DiscoveredItem]:
        """
        Queries all source endpoints associated with the route (directories and torrent clients).
        Aggregates discovered files and stamps each DiscoveredItem with:
        - source_media_type = route.media_type
        """
        ...

    def validate_source_type_match(
        self,
        asset: MediaAsset,
        source_media_type: SupportedMediaType | None,
    ) -> bool:
        """
        Verifies if identified MediaCategory matches source_media_type.
        Returns True if types match or source_media_type is generic/unspecified.
        Returns False if a mismatch is detected (e.g. video found in music source).
        """
        ...

    def resolve_target_destination(
        self,
        asset: MediaAsset,
        route: ResolvedMediaRoute,
    ) -> Path:
        """
        Computes the target file path based on route.destination_endpoint:
        - If type == SPOOL: returns spool_dir / release_folder / filename
        - If type == LIBRARY: evaluates category template against asset metadata
        """
        ...
```
