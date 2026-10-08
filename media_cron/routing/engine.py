from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from media_cron.config import DEFAULT_TEMPLATES
from media_cron.models import DiscoveredItem, MediaAsset, MediaCategory
from media_cron.routing.base import MediaRoutingEngineProtocol
from media_cron.routing.models import (
    CATEGORY_TO_MEDIA_TYPE,
    DestinationEndpointType,
    ResolvedMediaRoute,
    SourceEndpointType,
    SupportedMediaType,
)

if TYPE_CHECKING:
    from media_cron.config import MediaCronConfig


class MediaRoutingEngine(MediaRoutingEngineProtocol):
    """Coordinates intake, filtering, and target resolution across media routes."""

    def __init__(self, config: "MediaCronConfig | None" = None):
        self.config = config

    def discover_route_items(
        self,
        route: ResolvedMediaRoute,
        staging_dir: Path,
        dry_run: bool = False,
    ) -> Iterable[DiscoveredItem]:
        """Queries all source endpoints associated with the route."""
        import time

        from media_cron.plugins.input.directory import DirectoryScannerInput
        from media_cron.torrent.base import TorrentClientRegistry
        from media_cron.torrent.models import TorrentClientConfig

        seen_paths: set[Path] = set()

        for src in route.source_endpoints:
            endpoint_id = f"{src.type.value}:{src.path or src.category or src.client_profile}"

            if src.type == SourceEndpointType.DIRECTORY:
                if src.path and src.path.exists():
                    scanner = DirectoryScannerInput()
                    for item in scanner.discover(src.path, staging_dir, dry_run=dry_run):
                        resolved = item.source_path.resolve()
                        if resolved not in seen_paths:
                            seen_paths.add(resolved)
                            item.source_media_type = route.media_type
                            item.source_endpoint_id = endpoint_id
                            yield item

            elif src.type == SourceEndpointType.TORRENT:
                client_profile = src.client_profile or (
                    getattr(self.config, "active_torrent_client", None) if self.config else None
                )
                if (
                    self.config
                    and client_profile
                    and client_profile in getattr(self.config, "torrent_clients", {})
                ):
                    client_cfg = self.config.torrent_clients[client_profile]
                elif client_profile:
                    client_cfg = TorrentClientConfig(client_type=client_profile)
                else:
                    client_cfg = TorrentClientConfig()

                client = TorrentClientRegistry.create_client(client_cfg)
                if hasattr(client, "test_connection"):
                    try:
                        if not client.test_connection():
                            continue
                    except Exception:
                        continue

                categories = [src.category] if src.category else None
                tags = [src.tag] if src.tag else None
                exclude_categories = src.exclude_categories or None
                exclude_tags = src.exclude_tags or None

                torrents = []
                if hasattr(client, "list_completed_torrents"):
                    try:
                        res = client.list_completed_torrents(
                            categories=categories,
                            tags=tags,
                            exclude_tags=exclude_tags,
                            exclude_categories=exclude_categories,
                        )
                    except TypeError:
                        res = client.list_completed_torrents()
                    if isinstance(res, list):
                        torrents = res

                if not torrents and hasattr(client, "get_completed_torrents"):
                    res = client.get_completed_torrents()
                    if isinstance(res, list):
                        torrents = res

                for torrent in torrents:
                    if getattr(torrent, "progress", 1.0) < src.min_progress:
                        continue
                    if src.category and getattr(torrent, "category", None) != src.category:
                        continue
                    if src.tag and src.tag not in getattr(torrent, "tags", []):
                        continue
                    if src.exclude_tags and any(
                        t in getattr(torrent, "tags", []) for t in src.exclude_tags
                    ):
                        continue
                    if (
                        src.exclude_categories
                        and getattr(torrent, "category", None) in src.exclude_categories
                    ):
                        continue

                    content_path = getattr(torrent, "content_path", None)
                    if content_path:
                        local_path = client_cfg.translate_path(Path(content_path))
                    else:
                        local_path = (
                            client_cfg.translate_path(Path(torrent.save_path)) / torrent.name
                        )

                    if not local_path.exists():
                        fallback = Path(torrent.save_path) / torrent.name
                        if fallback.exists():
                            local_path = fallback
                        else:
                            continue

                    resolved = local_path.resolve()
                    if resolved in seen_paths:
                        continue
                    seen_paths.add(resolved)

                    is_dir = local_path.is_dir()
                    mtime = local_path.stat().st_mtime if local_path.exists() else time.time()
                    total_size = getattr(torrent, "total_size", 0)

                    item = DiscoveredItem(
                        source_path=local_path,
                        file_size=total_size,
                        modified_time=mtime,
                        is_directory=is_dir,
                        source_media_type=route.media_type,
                        source_endpoint_id=endpoint_id,
                    )
                    yield item

    def validate_source_type_match(
        self,
        asset: MediaAsset,
        source_media_type: SupportedMediaType | None,
    ) -> bool:
        """Verifies if identified MediaCategory matches source_media_type."""
        if source_media_type is None:
            return True

        expected_type = CATEGORY_TO_MEDIA_TYPE.get(asset.category)
        return expected_type == source_media_type

    def resolve_target_destination(
        self,
        asset: MediaAsset,
        route: ResolvedMediaRoute,
    ) -> Path:
        """Computes the target file path based on route.destination_endpoint."""
        dest_root = route.destination_endpoint.path or Path("/tmp/media")

        # 1. Spool mode
        if route.destination_endpoint.type == DestinationEndpointType.SPOOL:
            rel_folder = asset.path.parent.name
            return dest_root / rel_folder / asset.path.name

        # 2. Custom template override
        ext = asset.extension.lstrip(".")
        title = asset.clean_title
        year_str = str(asset.year) if asset.year else "Unknown"
        res_str = asset.resolution or ""
        artist_str = asset.artist or "Unknown Artist"
        album_str = asset.album or "Unknown Album"
        author_str = asset.author or "Unknown Author"
        show_str = asset.series_title or asset.clean_title

        # Check route template first, then config.templates
        custom_tmpl = route.destination_endpoint.template
        if not custom_tmpl and self.config and hasattr(self.config, "templates"):
            if (
                route.media_type == SupportedMediaType.MOVIES
                or asset.category == MediaCategory.VIDEO_MOVIE
            ):
                t = self.config.templates.get("movie")
                if t and t != DEFAULT_TEMPLATES.get("movie"):
                    custom_tmpl = t
            elif (
                route.media_type == SupportedMediaType.TV
                or asset.category == MediaCategory.VIDEO_SERIES
            ):
                t = self.config.templates.get("series")
                if t and t != DEFAULT_TEMPLATES.get("series"):
                    custom_tmpl = t
            elif (
                route.media_type == SupportedMediaType.MUSIC
                or asset.category == MediaCategory.AUDIO_MUSIC
            ):
                t = self.config.templates.get("music")
                if t and t != DEFAULT_TEMPLATES.get("music"):
                    custom_tmpl = t
            elif (
                route.media_type == SupportedMediaType.AUDIOBOOKS
                or asset.category == MediaCategory.AUDIO_BOOK
            ):
                t = self.config.templates.get("audiobook")
                if t and t != DEFAULT_TEMPLATES.get("audiobook"):
                    custom_tmpl = t
            elif (
                route.media_type == SupportedMediaType.BOOKS
                or asset.category == MediaCategory.BOOK_EBOOK
            ):
                t = self.config.templates.get("book")
                if t and t != DEFAULT_TEMPLATES.get("book"):
                    custom_tmpl = t

        if custom_tmpl:
            try:
                rel_path = custom_tmpl.format(
                    title=title,
                    artist=artist_str,
                    album=album_str,
                    track=asset.track_number or 1,
                    author=author_str,
                    year=year_str,
                    show=show_str,
                    season=asset.season_number or 1,
                    episode=asset.episode_number or 1,
                    resolution=res_str,
                    ext=ext,
                )
                return dest_root / rel_path
            except KeyError:
                pass

        # 3. Default category templates
        if (
            route.media_type == SupportedMediaType.MUSIC
            or asset.category == MediaCategory.AUDIO_MUSIC
        ):
            rel_path = (
                f"Music/{artist_str}/{album_str}/{asset.track_number or 1:02d} - {title}.{ext}"
            )
        elif (
            route.media_type == SupportedMediaType.AUDIOBOOKS
            or asset.category == MediaCategory.AUDIO_BOOK
        ):
            rel_path = (
                f"Audiobooks/{author_str}/{title}/{asset.track_number or 1:02d} - {title}.{ext}"
            )
        elif (
            route.media_type == SupportedMediaType.BOOKS
            or asset.category == MediaCategory.BOOK_EBOOK
        ):
            rel_path = f"Books/{author_str}/{title}.{ext}"
        elif (
            route.media_type == SupportedMediaType.MOVIES
            or asset.category == MediaCategory.VIDEO_MOVIE
        ):
            video_cfg = getattr(self.config, "video", None) if self.config else None
            is_video_enabled = bool(video_cfg and video_cfg.enabled)
            if is_video_enabled:
                movies_dir = video_cfg.library_movies_dir or "Movies"
                res_part = f" [{res_str}]" if res_str else ""
                year_part = f" ({year_str})" if asset.year else " (Unknown)"
                rel_path = f"{movies_dir}/{title}{year_part}/{title}{year_part}{res_part}.{ext}"
            else:
                tmpl = DEFAULT_TEMPLATES.get(
                    "movie", "Movies/{title} ({year})/{title} ({year}).{ext}"
                )
                rel_path = tmpl.format(
                    title=title,
                    year=year_str,
                    ext=ext,
                )
        elif (
            route.media_type == SupportedMediaType.TV
            or asset.category == MediaCategory.VIDEO_SERIES
        ):
            video_cfg = getattr(self.config, "video", None) if self.config else None
            is_video_enabled = bool(video_cfg and video_cfg.enabled)
            season = asset.season_number or 1
            episode = asset.episode_number or 1
            end_ep = getattr(asset, "episode_end_number", None)
            ep_tag = (
                f"S{season:02d}E{episode:02d}-E{end_ep:02d}"
                if end_ep
                else f"S{season:02d}E{episode:02d}"
            )
            res_part = f" [{res_str}]" if res_str else ""
            title_part = (
                f" - {title}" if title and not title.startswith("S") and title != show_str else ""
            )
            if is_video_enabled:
                tv_dir = video_cfg.library_tv_dir or "TV"
                rel_path = f"{tv_dir}/{show_str}/Season {season:02d}/{show_str} - {ep_tag}{title_part}{res_part}.{ext}"
            else:
                tmpl = DEFAULT_TEMPLATES.get(
                    "series",
                    "TV Shows/{show}/Season {season:02d}/{show} - S{season:02d}E{episode:02d}.{ext}",
                )
                rel_path = tmpl.format(
                    show=show_str,
                    season=season,
                    episode=episode,
                    ext=ext,
                )
        else:
            rel_path = f"Uncategorized/{title}.{ext}"

        return dest_root / rel_path
