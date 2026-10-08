import uuid
from datetime import UTC, datetime
from pathlib import Path

import media_cron.plugins  # noqa: F401
from media_cron.config import DEFAULT_TEMPLATES, MediaCronConfig
from media_cron.lock import LockContentionError, StagingLock
from media_cron.metadata.models import (
    MusicWorkflowMode,
    VideoCompanionType,
)
from media_cron.metadata.video_bundler import VideoReleaseBundleAggregator
from media_cron.metadata.video_spooler import VideoSpoolEngine
from media_cron.models import (
    EXIT_CONFIG_ERROR,
    EXIT_FATAL_ERROR,
    EXIT_PARTIAL_OR_LOCKED,
    EXIT_SUCCESS,
    BatchSummary,
    DiscoveredItem,
    MediaAsset,
    MediaCategory,
    MediaRouteSummary,
    OperationPlan,
    OperationResult,
    OperationStatus,
    OperationType,
    TransferMode,
)
from media_cron.plugins.base import InputPlugin
from media_cron.plugins.input.directory import DirectoryScannerInput
from media_cron.plugins.input.torrent import TorrentInputPlugin
from media_cron.plugins.output.torrent_seed import TorrentClientSeedOutput
from media_cron.plugins.registry import PluginRegistry, default_registry
from media_cron.routing.engine import MediaRoutingEngine
from media_cron.routing.models import (
    CATEGORY_TO_MEDIA_TYPE,
    DestinationEndpointType,
    SupportedMediaType,
)
from media_cron.routing.resolver import RouteResolver
from media_cron.torrent.base import TorrentClientRegistry
from media_cron.torrent.models import TorrentClientConfig


class Pipeline:
    """Core media-cron processing pipeline."""

    def __init__(
        self,
        config: MediaCronConfig,
        registry: PluginRegistry | None = None,
        target_torrent_identifier: str | None = None,
    ) -> None:
        self.config = config
        self.registry = registry or default_registry
        self.target_torrent_identifier = target_torrent_identifier
        self.route_resolver = RouteResolver()
        self.routing_engine = MediaRoutingEngine(self.config)
        self.resolved_routes = self.route_resolver.resolve_all_routes(self.config)

        # Wire route spool destinations to video / music configs if configured

        music_route = self.resolved_routes.get(SupportedMediaType.MUSIC)
        if (
            music_route
            and music_route.destination_endpoint.type == DestinationEndpointType.SPOOL
            and getattr(self.config, "music", None)
        ):
            self.config.music.spool_dir = music_route.destination_endpoint.path
            self.config.music.workflow_mode = MusicWorkflowMode.SPOOL
        self._last_audiobook_summary: dict | None = None
        self._last_books_summary: dict | None = None
        self._last_music_summary: dict | None = None
        self._last_video_summary: dict | None = None
        self._last_unrecognized_count: int = 0
        self._last_review_staged_count: int = 0

    def _get_video_summary(self) -> dict | None:
        if not getattr(self.config, "video", None) or not self.config.video.enabled:
            return None
        if self._last_video_summary is not None:
            return self._last_video_summary
        return {
            "total_videos": 0,
            "spooled_releases": 0,
            "spool_skipped_count": 0,
            "organized_movies": 0,
            "organized_episodes": 0,
            "rescan_notifications_sent": 0,
            "rescan_errors": 0,
        }

    def _get_input_plugins(self) -> tuple[list[InputPlugin], TorrentInputPlugin | None]:
        plugins: list[InputPlugin] = []
        torrent_plugin: TorrentInputPlugin | None = None

        if self.config.active_torrent_client:
            client_cfg = self.config.torrent_clients.get(
                self.config.active_torrent_client
            ) or TorrentClientConfig(client_type=self.config.active_torrent_client)
            client = TorrentClientRegistry.create_client(client_cfg)
            torrent_plugin = TorrentInputPlugin(
                client=client,
                config=client_cfg,
                target_identifier=self.target_torrent_identifier,
            )
            plugins.append(torrent_plugin)

        if self.config.hybrid_ingest or not self.config.active_torrent_client:
            dir_plugin = self.registry.get_input("directory_scanner")
            if self.config.hybrid_ingest:
                plugins.insert(0, dir_plugin)
            else:
                plugins.append(dir_plugin)

        return plugins, torrent_plugin

    def _resolve_destination_path(self, asset: MediaAsset) -> Path:
        """Resolves target library path using configured templates."""
        media_type = CATEGORY_TO_MEDIA_TYPE.get(asset.category)
        if media_type and media_type in self.resolved_routes:
            route = self.resolved_routes[media_type]
            if asset.destination_rel_path is not None:
                dest_root = route.destination_endpoint.path or (
                    self.config.paths.destination_dir or Path("/tmp/media")
                )
                return dest_root / asset.destination_rel_path
            return self.routing_engine.resolve_target_destination(asset, route)

        dest_root = self.config.paths.destination_dir or Path("/tmp/media")
        if asset.destination_rel_path is not None:
            return dest_root / asset.destination_rel_path

        # Determine category key
        if asset.category in (MediaCategory.VIDEO_MOVIE, MediaCategory.VIDEO_SERIES) and (
            getattr(self.config, "video", None)
            and self.config.video.enabled
            and str(self.config.video.workflow_mode).lower() == "spool"
            and self.config.video.spool_dir
        ):
            dest_root = self.config.video.spool_dir
            rel_folder = asset.path.parent.name
            rel_path = f"{rel_folder}/{asset.path.name}"
        elif asset.category == MediaCategory.VIDEO_MOVIE:
            custom_tmpl = self.config.templates.get("movie")
            video_cfg = getattr(self.config, "video", None)
            is_video_enabled = bool(video_cfg and video_cfg.enabled)
            if custom_tmpl and custom_tmpl != DEFAULT_TEMPLATES.get("movie"):
                rel_path = custom_tmpl.format(
                    title=asset.clean_title,
                    year=asset.year or "Unknown",
                    ext=asset.extension.lstrip("."),
                )
            elif is_video_enabled:
                movies_dir = video_cfg.library_movies_dir or "Movies"
                res_part = f" [{asset.resolution}]" if asset.resolution else ""
                year_part = f" ({asset.year})" if asset.year else " (Unknown)"
                title = asset.clean_title
                ext = asset.extension.lstrip(".")
                rel_path = f"{movies_dir}/{title}{year_part}/{title}{year_part}{res_part}.{ext}"
            else:
                tmpl = custom_tmpl or DEFAULT_TEMPLATES.get(
                    "movie", "Movies/{title} ({year})/{title} ({year}).{ext}"
                )
                rel_path = tmpl.format(
                    title=asset.clean_title,
                    year=asset.year or "Unknown",
                    ext=asset.extension.lstrip("."),
                )
        elif asset.category == MediaCategory.VIDEO_SERIES:
            custom_tmpl = self.config.templates.get("series")
            video_cfg = getattr(self.config, "video", None)
            is_video_enabled = bool(video_cfg and video_cfg.enabled)
            if custom_tmpl and custom_tmpl != DEFAULT_TEMPLATES.get("series"):
                rel_path = custom_tmpl.format(
                    show=asset.series_title or asset.clean_title,
                    season=asset.season_number or 1,
                    episode=asset.episode_number or 1,
                    ext=asset.extension.lstrip("."),
                )
            elif is_video_enabled:
                tv_dir = video_cfg.library_tv_dir or "TV"
                show = asset.series_title or asset.clean_title
                season = asset.season_number or 1
                episode = asset.episode_number or 1
                end_ep = getattr(asset, "episode_end_number", None)
                ep_tag = (
                    f"S{season:02d}E{episode:02d}-E{end_ep:02d}"
                    if end_ep
                    else f"S{season:02d}E{episode:02d}"
                )
                res_part = f" [{asset.resolution}]" if asset.resolution else ""
                ext = asset.extension.lstrip(".")
                title_part = ""
                if (
                    asset.clean_title
                    and not asset.clean_title.startswith("S")
                    and asset.clean_title != show
                ):
                    title_part = f" - {asset.clean_title}"
                rel_path = f"{tv_dir}/{show}/Season {season:02d}/{show} - {ep_tag}{title_part}{res_part}.{ext}"
            else:
                tmpl = custom_tmpl or DEFAULT_TEMPLATES.get(
                    "series",
                    "TV Shows/{show}/Season {season:02d}/{show} - S{season:02d}E{episode:02d}.{ext}",
                )
                rel_path = tmpl.format(
                    show=asset.series_title or asset.clean_title,
                    season=asset.season_number or 1,
                    episode=asset.episode_number or 1,
                    ext=asset.extension.lstrip("."),
                )
        elif asset.category == MediaCategory.AUDIO_MUSIC:
            if (
                getattr(self.config, "music", None)
                and self.config.music.enabled
                and self.config.music.workflow_mode == MusicWorkflowMode.SPOOL
                and self.config.music.spool_dir
            ):
                dest_root = self.config.music.spool_dir
                rel_folder = asset.path.parent.name
                rel_path = f"{rel_folder}/{asset.path.name}"
            else:
                tmpl = self.config.templates.get(
                    "music", "Music/{artist}/{album}/{track:02d} - {title}.{ext}"
                )
                rel_path = tmpl.format(
                    artist=asset.artist or "Unknown Artist",
                    album=asset.album or "Unknown Album",
                    track=asset.track_number or 1,
                    title=asset.clean_title,
                    ext=asset.extension.lstrip("."),
                )
        elif asset.category == MediaCategory.AUDIO_BOOK:
            tmpl = self.config.templates.get(
                "audiobook", "Audiobooks/{author}/{title}/{track:02d} - {title}.{ext}"
            )
            rel_path = tmpl.format(
                author=asset.author or "Unknown Author",
                title=asset.clean_title,
                track=asset.track_number or 1,
                ext=asset.extension.lstrip("."),
            )
        elif asset.category == MediaCategory.BOOK_EBOOK:
            tmpl = self.config.templates.get("book", "Books/{author}/{title}.{ext}")
            rel_path = tmpl.format(
                author=asset.author or "Unknown Author",
                title=asset.clean_title,
                ext=asset.extension.lstrip("."),
            )
        else:
            rel_path = f"Uncategorized/{asset.clean_title}{asset.extension}"

        return dest_root / rel_path

    def _get_route_config(self, media_type: SupportedMediaType):
        if media_type == SupportedMediaType.MUSIC:
            return getattr(getattr(self.config, "music", None), "route", None)
        elif media_type == SupportedMediaType.AUDIOBOOKS:
            return getattr(getattr(self.config, "audiobook", None), "route", None)
        elif media_type == SupportedMediaType.BOOKS:
            return getattr(getattr(self.config, "books", None), "route", None)
        elif media_type == SupportedMediaType.MOVIES:
            return getattr(getattr(self.config, "video", None), "movies_route", None)
        elif media_type == SupportedMediaType.TV:
            return getattr(getattr(self.config, "video", None), "tv_route", None)
        return None

    def plan(
        self, source_path: Path | None, staging_path: Path
    ) -> tuple[list[OperationPlan], list[DiscoveredItem], TorrentInputPlugin | None]:
        """Generates a list of planned operations without mutating files."""
        seen_paths: set[Path] = set()
        raw_items: list[DiscoveredItem] = []
        torrent_plugin = None

        # 1. Discover items from route-specific source endpoints
        for media_type, route in self.resolved_routes.items():
            cfg_media = getattr(self.config, media_type.value, None)
            if media_type in (SupportedMediaType.MOVIES, SupportedMediaType.TV):
                cfg_media = getattr(self.config, "video", None)
            elif media_type == SupportedMediaType.AUDIOBOOKS:
                cfg_media = getattr(self.config, "audiobook", None)
            if cfg_media is not None and hasattr(cfg_media, "enabled") and not cfg_media.enabled:
                continue

            route_cfg = self._get_route_config(media_type)
            if route_cfg and route_cfg.sources:
                for item in self.routing_engine.discover_route_items(
                    route, staging_path, dry_run=True
                ):
                    resolved = item.source_path.resolve()
                    if resolved not in seen_paths:
                        seen_paths.add(resolved)
                        raw_items.append(item)

        # 2. Discover items from global source or staging
        if source_path is not None and source_path.resolve() == staging_path.resolve():
            scanner = DirectoryScannerInput()
            for item in scanner.discover(staging_path, staging_path, dry_run=True):
                resolved = item.source_path.resolve()
                if resolved not in seen_paths:
                    seen_paths.add(resolved)
                    raw_items.append(item)
        else:
            input_plugins, torrent_plugin = self._get_input_plugins()
            for plugin in input_plugins:
                if plugin.plugin_name == "directory_scanner" and (
                    not source_path or not Path(source_path).exists()
                ):
                    continue
                for item in plugin.discover(
                    source_path or staging_path, staging_path, dry_run=True
                ):
                    resolved = item.source_path.resolve()
                    if resolved not in seen_paths:
                        seen_paths.add(resolved)
                        raw_items.append(item)

        discovered_items: list[DiscoveredItem] = []
        for item in raw_items:
            if item.is_directory and item.source_path.is_dir():
                for sub_file in item.source_path.rglob("*"):
                    if sub_file.is_file() and not sub_file.name.startswith("."):
                        stat = sub_file.stat()
                        discovered_items.append(
                            DiscoveredItem(
                                source_path=sub_file,
                                file_size=stat.st_size,
                                modified_time=stat.st_mtime,
                                is_archive=sub_file.suffix.lower()
                                in (".zip", ".rar", ".7z", ".tar"),
                                is_directory=False,
                                source_media_type=item.source_media_type,
                                source_endpoint_id=item.source_endpoint_id,
                            )
                        )
            else:
                discovered_items.append(item)

        # Ensure companion subtitle files are processed after primary media files
        subtitle_exts = {".srt", ".vtt", ".sub", ".idx", ".ass", ".ssa"}
        discovered_items.sort(
            key=lambda it: 1 if it.source_path.suffix.lower() in subtitle_exts else 0
        )

        lookup_plugins = self.registry.get_lookups(self.config.plugins.lookups)
        for lk in lookup_plugins:
            if hasattr(lk, "dry_run"):
                lk.dry_run = self.config.general.dry_run
            if hasattr(lk, "configure"):
                if getattr(lk, "plugin_name", "") == "book_meta" or (
                    hasattr(lk, "identifier") and hasattr(lk.identifier, "total_books")
                ):
                    lk.configure(self.config.books)
                elif getattr(lk, "plugin_name", "") == "music":
                    lk.configure(getattr(self.config, "music", None) or self.config)
                else:
                    lk.configure(self.config.audiobook)
            elif hasattr(lk, "identifier") and hasattr(lk.identifier, "config"):
                if hasattr(lk.identifier, "total_books"):
                    lk.identifier.config = self.config.books
                else:
                    lk.identifier.config = self.config.audiobook
        plans: list[OperationPlan] = []
        mode = TransferMode(self.config.general.mode)

        is_video_spool = bool(
            getattr(self.config, "video", None)
            and self.config.video.enabled
            and str(self.config.video.workflow_mode).lower() in ("spool", "hybrid")
            and self.config.video.spool_dir
        )

        video_spool_paths: set[Path] = set()
        video_spool_plans: list[OperationPlan] = []
        if is_video_spool:
            video_target = (
                staging_path
                if (staging_path and staging_path.exists() and any(staging_path.iterdir()))
                else source_path
            )
            if video_target and Path(video_target).exists():
                aggregator = VideoReleaseBundleAggregator(
                    sample_size_threshold_mb=self.config.general.sample_size_threshold_mb
                )
                bundles = aggregator.aggregate(Path(video_target))
                spool_dir = self.config.video.spool_dir
                total_videos = 0
                spooled_count = 0
                skipped_count = 0

                for bundle in bundles:
                    total_videos += len(bundle.primary_videos)
                    for v in bundle.primary_videos:
                        video_spool_paths.add(v.path.resolve())
                    for c in bundle.companion_assets:
                        video_spool_paths.add(c.path.resolve())

                    dest_dir_target = spool_dir / bundle.root_path.name
                    is_collision = dest_dir_target.exists()
                    if is_collision:
                        skipped_count += 1
                    else:
                        spooled_count += 1

                    plan = OperationPlan(
                        op_type=OperationType.SKIP_COLLISION
                        if is_collision
                        else OperationType.ORGANIZE,
                        transfer_mode=mode,
                        source_path=bundle.root_path,
                        destination_path=dest_dir_target,
                        reason=f"Target directory '{dest_dir_target.name}' already exists in drop folder"
                        if is_collision
                        else f"Video drop-folder spool for release '{bundle.release_title}'",
                        dry_run=True,
                    )
                    plan.is_video_spool = True
                    video_spool_plans.append(plan)

                self._last_video_summary = {
                    "total_videos": total_videos,
                    "spooled_releases": spooled_count,
                    "spool_skipped_count": skipped_count,
                    "organized_movies": 0,
                    "organized_episodes": 0,
                    "rescan_notifications_sent": 0,
                    "rescan_errors": 0,
                }

        planned_subtitle_paths: set[Path] = set()
        unhandled_items: list[DiscoveredItem] = []

        for item in discovered_items:
            path = item.source_path
            ext = path.suffix.lower()

            if is_video_spool and path.resolve() in video_spool_paths:
                continue
            if path.resolve() in planned_subtitle_paths:
                continue

            # 1. Check junk extensions
            if ext in self.config.general.junk_extensions:
                is_preserved = False
                if (
                    getattr(self.config, "books", None)
                    and self.config.books.enabled
                    and ext == ".txt"
                ):
                    for lk in lookup_plugins:
                        if getattr(lk, "plugin_name", "") == "book_meta" and lk.can_handle(item):
                            if path.stem.lower() not in (
                                "readme",
                                "instructions",
                                "install",
                                "read me",
                                "info",
                            ):
                                is_preserved = True
                                break
                if (
                    not is_preserved
                    and getattr(self.config, "music", None)
                    and self.config.music.enabled
                ):
                    for lk in lookup_plugins:
                        if getattr(lk, "plugin_name", "") == "music" and lk.can_handle(item):
                            is_preserved = True
                            break
                if (
                    not is_preserved
                    and getattr(self.config, "video", None)
                    and self.config.video.enabled
                    and self.config.video.preserve_companions
                ):
                    if VideoCompanionType.from_path(path) != VideoCompanionType.UNKNOWN:
                        is_preserved = True

                if not is_preserved:
                    plans.append(
                        OperationPlan(
                            op_type=OperationType.PURGE_JUNK,
                            transfer_mode=mode,
                            source_path=path,
                            destination_path=None,
                            reason=f"File extension '{ext}' in configured junk list",
                            dry_run=True,
                        )
                    )
                    continue

            # 2. Check sample threshold
            if "sample" in path.name.lower() and ext in (".mkv", ".mp4", ".avi"):
                limit_bytes = self.config.general.sample_size_threshold_mb * 1024 * 1024
                if item.file_size < limit_bytes:
                    plans.append(
                        OperationPlan(
                            op_type=OperationType.PURGE_SAMPLE,
                            transfer_mode=mode,
                            source_path=path,
                            destination_path=None,
                            reason=f"Sample video under threshold ({item.file_size} < {limit_bytes} bytes)",
                            dry_run=True,
                        )
                    )
                    continue

            # 3. Lookup & enrich
            handled = False
            for lookup in lookup_plugins:
                if lookup.can_handle(item):
                    from media_cron.integrity.validator import validate_container_integrity

                    is_valid, integrity_err = validate_container_integrity(path)
                    if not is_valid:
                        plans.append(
                            OperationPlan(
                                op_type=OperationType.QUARANTINE_CORRUPT,
                                transfer_mode=mode,
                                source_path=path,
                                destination_path=None,
                                reason=f"Integrity verification failed: {integrity_err}",
                                dry_run=True,
                            )
                        )
                        handled = True
                        break

                    asset = lookup.enrich(item)
                    asset.source_media_type = getattr(item, "source_media_type", None)
                    asset.source_endpoint_id = getattr(item, "source_endpoint_id", None)

                    if not self.routing_engine.validate_source_type_match(
                        asset, asset.source_media_type
                    ):
                        review_dir = (
                            self.config.paths.review_dir
                            if hasattr(self.config, "paths") and self.config.paths.review_dir
                            else (staging_path / "review")
                        )
                        plans.append(
                            OperationPlan(
                                op_type=OperationType.REVIEW_STAGE,
                                transfer_mode=mode,
                                source_path=asset.path,
                                destination_path=review_dir / asset.path.name,
                                reason=f"Mismatched media type: identified as '{asset.category.value}' but ingested from '{asset.source_media_type.value}' source",
                                dry_run=True,
                            )
                        )
                        handled = True
                        break

                    if (
                        asset.category == MediaCategory.AUDIO_MUSIC
                        and hasattr(self.config, "music")
                        and not self.config.music.enabled
                    ):
                        continue

                    media_type = CATEGORY_TO_MEDIA_TYPE.get(asset.category)
                    target_mode = mode
                    if media_type and media_type in self.resolved_routes:
                        route = self.resolved_routes[media_type]
                        if not self.route_resolver.validate_mount_safety(route):
                            continue
                        target_mode = route.transfer_mode

                    dest_path = self._resolve_destination_path(asset)
                    plans.append(
                        OperationPlan(
                            op_type=OperationType.ORGANIZE,
                            transfer_mode=target_mode,
                            source_path=asset.path,
                            destination_path=dest_path,
                            reason=f"Identified as {asset.category.value}: '{asset.clean_title}'",
                            dry_run=True,
                        )
                    )

                    # Plan associated subtitles
                    for sub in asset.subtitle_files:
                        sub_resolved = sub.resolve()
                        if sub_resolved in planned_subtitle_paths:
                            continue
                        sub_ext = sub.suffix.lower()
                        if hasattr(lookup, "format_subtitle_destination"):
                            dest_sub = lookup.format_subtitle_destination(dest_path, sub)
                        else:
                            dest_sub = dest_path.with_suffix(sub_ext)
                        plans.append(
                            OperationPlan(
                                op_type=OperationType.ORGANIZE,
                                transfer_mode=target_mode,
                                source_path=sub,
                                destination_path=dest_sub,
                                reason=f"Preserved associated subtitle for '{asset.clean_title}'",
                                dry_run=True,
                            )
                        )
                        planned_subtitle_paths.add(sub_resolved)

                    # Plan seed relocation if configured
                    if self.config.paths.seed_dir:
                        try:
                            rel_src = path.relative_to(staging_path)
                        except ValueError:
                            rel_src = Path(path.name)
                        seed_dest = self.config.paths.seed_dir / rel_src
                        plans.append(
                            OperationPlan(
                                op_type=OperationType.SEED_RELOCATE,
                                transfer_mode=TransferMode.HARDLINK,
                                source_path=path,
                                destination_path=seed_dest,
                                reason=f"Seeding relocation for '{asset.clean_title}'",
                                dry_run=True,
                            )
                        )

                    handled = True
                    break

            if not handled:
                unhandled_items.append(item)

        unrecognized_groups: dict[Path, list[DiscoveredItem]] = {}
        for unrec_item in unhandled_items:
            p = unrec_item.source_path
            try:
                rel = p.relative_to(staging_path)
                if len(rel.parts) > 1:
                    root = staging_path / rel.parts[0]
                else:
                    root = p
            except ValueError:
                root = p
            unrecognized_groups.setdefault(root, []).append(unrec_item)

        self._last_unrecognized_count = len(unrecognized_groups)
        self._last_review_staged_count = 0

        review_enabled = (
            getattr(self.config, "review", None)
            and self.config.review.enabled
            and self.config.paths.review_dir
        )

        for root, group_items in unrecognized_groups.items():
            if review_enabled:
                self._last_review_staged_count += 1
                plan = OperationPlan(
                    op_type=OperationType.REVIEW_STAGE,
                    transfer_mode=mode,
                    source_path=root,
                    destination_path=self.config.paths.review_dir,
                    reason=f"Unrecognized media '{root.name}' staged for manual review",
                    dry_run=True,
                )
                plan.unrecognized_files = [i.source_path for i in group_items]
                plans.append(plan)
            else:
                import logging

                logging.getLogger(__name__).warning(
                    "Unrecognized item '%s' cannot be automatically identified; review_dir not configured, leaving in staging",
                    root.name,
                )

        if torrent_plugin and torrent_plugin.processed_torrents:
            seeding_cfg = torrent_plugin.config.seeding
            for torrent in torrent_plugin.processed_torrents:
                if seeding_cfg.mode == "client_relocate":
                    relocate_dest = (
                        self.config.paths.seed_dir
                        if seeding_cfg.target_location == "seed_dir"
                        else self.config.paths.destination_dir
                    )
                    if relocate_dest:
                        plans.append(
                            OperationPlan(
                                op_type=OperationType.TORRENT_RELOCATE,
                                transfer_mode=TransferMode.MOVE,
                                source_path=Path(torrent.info_hash),
                                destination_path=relocate_dest,
                                reason=f"Client storage relocated to {relocate_dest}",
                                dry_run=True,
                            )
                        )
                plans.append(
                    OperationPlan(
                        op_type=OperationType.TORRENT_TAG,
                        transfer_mode=TransferMode.MOVE,
                        source_path=Path(torrent.info_hash),
                        reason=f"Applied tag '{seeding_cfg.completion_tag}' and category '{seeding_cfg.completion_category}'",
                        dry_run=True,
                    )
                )

        plans.extend(video_spool_plans)

        # Collect audiobook, book, and music telemetry summary
        self._last_audiobook_summary = None
        self._last_books_summary = None
        self._last_music_summary = None
        for lk in lookup_plugins:
            if getattr(lk, "plugin_name", "") == "music" and hasattr(lk, "get_summary"):
                self._last_music_summary = lk.get_summary()
            elif hasattr(lk, "identifier") and hasattr(lk.identifier, "get_summary"):
                summary_data = lk.identifier.get_summary()
                if summary_data.get("total_audiobooks", 0) > 0:
                    self._last_audiobook_summary = summary_data
                if summary_data.get("total_books", 0) > 0:
                    self._last_books_summary = summary_data

        if getattr(self.config, "video", None) and self.config.video.enabled and not is_video_spool:
            from media_cron.plugins.lookup.video import VIDEO_EXTENSIONS

            total_videos = 0
            organized_movies = 0
            organized_episodes = 0
            for p in plans:
                if p.op_type in (OperationType.ORGANIZE, OperationType.UPGRADE_REPLACE):
                    if p.source_path.suffix.lower() in VIDEO_EXTENSIONS:
                        total_videos += 1
                        dest_str = str(p.destination_path or "")
                        if "/Movies" in dest_str or "Movies/" in dest_str:
                            organized_movies += 1
                        elif "/TV" in dest_str or "TV/" in dest_str:
                            organized_episodes += 1
            self._last_video_summary = {
                "total_videos": total_videos,
                "spooled_releases": 0,
                "spool_skipped_count": 0,
                "organized_movies": organized_movies,
                "organized_episodes": organized_episodes,
                "rescan_notifications_sent": 0,
                "rescan_errors": 0,
            }

        return plans, discovered_items, torrent_plugin

    def _build_routing_summary(
        self,
        plans: list[OperationPlan],
        results: list[OperationResult] | None = None,
        discovered_count: int = 0,
    ) -> dict[str, MediaRouteSummary]:
        routing_summary: dict[str, MediaRouteSummary] = {}

        for media_type, route in self.resolved_routes.items():
            cfg_media = getattr(self.config, media_type.value, None)
            if media_type in (SupportedMediaType.MOVIES, SupportedMediaType.TV):
                cfg_media = getattr(self.config, "video", None)
            elif media_type == SupportedMediaType.AUDIOBOOKS:
                cfg_media = getattr(self.config, "audiobook", None)
            if cfg_media is not None and hasattr(cfg_media, "enabled") and not cfg_media.enabled:
                continue

            dest_path_str = (
                str(route.destination_endpoint.path)
                if route.destination_endpoint and route.destination_endpoint.path
                else ""
            )
            summary = MediaRouteSummary(
                media_type=media_type.value,
                source_count=len(route.source_endpoints),
                destination_path=dest_path_str,
                destination_type=route.destination_endpoint.type.value
                if route.destination_endpoint
                else "library",
                transfer_mode=route.transfer_mode.value
                if hasattr(route.transfer_mode, "value")
                else str(route.transfer_mode),
                scanned_count=0,
                processed_count=0,
                spooled_count=0,
                review_staged_count=0,
                skipped_count=0,
                error_count=0,
                errors=[],
            )
            routing_summary[media_type.value] = summary

        for plan in plans:
            plan_media_type = None
            dest_str = str(plan.destination_path or "")
            src_str = str(plan.source_path or "")
            reason_lower = plan.reason.lower()

            if (
                "music" in reason_lower
                or "/music" in dest_str.lower()
                or ".flac" in src_str.lower()
                or ".mp3" in src_str.lower()
            ):
                plan_media_type = SupportedMediaType.MUSIC.value
            elif (
                "audiobook" in reason_lower
                or "/audiobook" in dest_str.lower()
                or ".m4b" in src_str.lower()
            ):
                plan_media_type = SupportedMediaType.AUDIOBOOKS.value
            elif (
                "book" in reason_lower
                or "/book" in dest_str.lower()
                or ".epub" in src_str.lower()
                or ".pdf" in src_str.lower()
            ):
                plan_media_type = SupportedMediaType.BOOKS.value
            elif "movie" in reason_lower or "/movies" in dest_str.lower():
                plan_media_type = SupportedMediaType.MOVIES.value
            elif "series" in reason_lower or "tv" in reason_lower or "/tv" in dest_str.lower():
                plan_media_type = SupportedMediaType.TV.value

            if plan_media_type and plan_media_type in routing_summary:
                m_sum = routing_summary[plan_media_type]
                m_sum.scanned_count += 1
                if plan.op_type in (OperationType.ORGANIZE, OperationType.UPGRADE_REPLACE):
                    if getattr(plan, "is_video_spool", False) or m_sum.destination_type == "spool":
                        m_sum.spooled_count += 1
                    m_sum.processed_count += 1
                elif plan.op_type == OperationType.REVIEW_STAGE:
                    m_sum.review_staged_count += 1
                elif plan.op_type in (OperationType.SKIP_COLLISION,):
                    m_sum.skipped_count += 1

        if results:
            for r in results:
                if r.status == OperationStatus.FAILED:
                    plan_media_type = None
                    dest_str = str(r.plan.destination_path or "")
                    src_str = str(r.plan.source_path or "")
                    reason_lower = r.plan.reason.lower()
                    if (
                        "music" in reason_lower
                        or "/music" in dest_str.lower()
                        or ".flac" in src_str.lower()
                    ):
                        plan_media_type = SupportedMediaType.MUSIC.value
                    elif (
                        "audiobook" in reason_lower
                        or "/audiobook" in dest_str.lower()
                        or ".m4b" in src_str.lower()
                    ):
                        plan_media_type = SupportedMediaType.AUDIOBOOKS.value
                    elif (
                        "book" in reason_lower
                        or "/book" in dest_str.lower()
                        or ".epub" in src_str.lower()
                    ):
                        plan_media_type = SupportedMediaType.BOOKS.value
                    elif "movie" in reason_lower or "/movies" in dest_str.lower():
                        plan_media_type = SupportedMediaType.MOVIES.value
                    elif (
                        "series" in reason_lower
                        or "tv" in reason_lower
                        or "/tv" in dest_str.lower()
                    ):
                        plan_media_type = SupportedMediaType.TV.value
                    if plan_media_type and plan_media_type in routing_summary:
                        routing_summary[plan_media_type].error_count += 1
                        if r.error:
                            routing_summary[plan_media_type].errors.append(r.error)

        return routing_summary

    def run(self) -> BatchSummary:
        """Executes the pipeline according to active configuration."""
        started_at = datetime.now(UTC)
        batch_id = uuid.uuid4()
        dry_run = self.config.general.dry_run

        source_dir = self.config.paths.source_dir
        staging_dir = self.config.paths.staging_dir
        dest_dir = self.config.paths.destination_dir

        is_video_spool = bool(
            getattr(self.config, "video", None)
            and self.config.video.enabled
            and str(self.config.video.workflow_mode).lower() in ("spool", "hybrid")
            and self.config.video.spool_dir
        )

        has_route_dest = any(
            route.destination_endpoint and route.destination_endpoint.path
            for route in self.resolved_routes.values()
        )

        if (
            not dest_dir
            and not (
                getattr(self.config, "music", None)
                and self.config.music.enabled
                and self.config.music.workflow_mode == MusicWorkflowMode.SPOOL
                and self.config.music.spool_dir
            )
            and not is_video_spool
            and not has_route_dest
        ):
            return BatchSummary(
                batch_id=batch_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                exit_code=EXIT_CONFIG_ERROR,
                errors=["Destination directory must be specified."],
                routing_summary=self._build_routing_summary([]),
            )

        has_route_source = any(route.source_endpoints for route in self.resolved_routes.values())

        if not self.config.active_torrent_client and not source_dir and not has_route_source:
            return BatchSummary(
                batch_id=batch_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                exit_code=EXIT_CONFIG_ERROR,
                errors=[
                    "Source directory must be specified when torrent client is not configured."
                ],
                routing_summary=self._build_routing_summary([]),
            )

        if dry_run:
            plans, discovered, torrent_plugin = self.plan(source_dir, staging_dir)
            results = [
                OperationResult(
                    plan=p, status=OperationStatus.SUCCESS, message="Simulated in dry-run mode"
                )
                for p in plans
            ]
            completed_at = datetime.now(UTC)

            torrent_summary = None
            if torrent_plugin:
                torrent_summary = {
                    "client": self.config.active_torrent_client,
                    "discovered_torrents": len(torrent_plugin.processed_torrents),
                    "ingested_torrents": len(torrent_plugin.processed_torrents),
                    "relocated_torrents": 0,
                    "tagged_torrents": 0,
                }

            routing_summary = self._build_routing_summary(
                plans, results=results, discovered_count=len(discovered)
            )

            return BatchSummary(
                batch_id=batch_id,
                started_at=started_at,
                completed_at=completed_at,
                total_scanned=len(discovered),
                processed_count=len([p for p in plans if p.op_type == OperationType.ORGANIZE]),
                junk_purged_count=len(
                    [
                        p
                        for p in plans
                        if p.op_type in (OperationType.PURGE_JUNK, OperationType.PURGE_SAMPLE)
                    ]
                ),
                skipped_count=0,
                error_count=0,
                unrecognized_count=self._last_unrecognized_count,
                review_staged_count=self._last_review_staged_count,
                operations=results,
                dry_run=True,
                exit_code=EXIT_SUCCESS,
                torrent_summary=torrent_summary,
                audiobook_summary=self._last_audiobook_summary,
                books_summary=self._last_books_summary,
                music_summary=self._last_music_summary,
                video_summary=self._get_video_summary(),
                routing_summary=routing_summary,
            )

        # Live Execution: Acquire lockfile in staging_dir
        try:
            with StagingLock(staging_dir):
                # 1. Ingest into staging
                input_plugins, torrent_plugin = self._get_input_plugins()
                staged_items: list[DiscoveredItem] = []
                seen_staged: set[Path] = set()

                for plugin in input_plugins:
                    if plugin.plugin_name == "directory_scanner" and (
                        not source_dir or not Path(source_dir).exists()
                    ):
                        continue
                    for item in plugin.discover(
                        source_dir or staging_dir, staging_dir, dry_run=False
                    ):
                        resolved = item.source_path.resolve()
                        if resolved not in seen_staged:
                            seen_staged.add(resolved)
                            staged_items.append(item)

                # 2. Generate and execute plans
                plans, _, _ = self.plan(staging_dir, staging_dir)
                outputs = self.registry.get_outputs(self.config.plugins.outputs)

                results: list[OperationResult] = []
                errors: list[str] = []
                processed_count = 0
                upgraded_count = 0
                junk_count = 0
                skipped_count = 0
                error_count = 0
                review_staged_count = 0
                if is_video_spool:
                    spool_engine = VideoSpoolEngine()
                    aggregator = VideoReleaseBundleAggregator(
                        sample_size_threshold_mb=self.config.general.sample_size_threshold_mb
                    )
                    video_bundles = aggregator.aggregate(staging_dir)
                    total_videos = 0
                    spooled_releases = 0
                    spool_skipped = 0

                    for bundle in video_bundles:
                        total_videos += len(bundle.primary_videos)
                        spool_res = spool_engine.spool_release(
                            bundle=bundle,
                            spool_dir=self.config.video.spool_dir,
                            post_command=self.config.video.post_ingest_command,
                            dry_run=False,
                        )
                        if spool_res.skipped:
                            spool_skipped += 1
                        elif spool_res.success:
                            spooled_releases += 1
                            if self.config.general.mode == "move":
                                import shutil

                                shutil.rmtree(bundle.root_path, ignore_errors=True)
                        else:
                            error_count += 1
                            if spool_res.error:
                                errors.append(spool_res.error)

                    self._last_video_summary = {
                        "total_videos": total_videos,
                        "spooled_releases": spooled_releases,
                        "spool_skipped_count": spool_skipped,
                        "organized_movies": 0,
                        "organized_episodes": 0,
                        "rescan_notifications_sent": 0,
                        "rescan_errors": 0,
                    }

                for plan in plans:
                    if getattr(plan, "is_video_spool", False):
                        if plan.op_type == OperationType.SKIP_COLLISION:
                            skipped_count += 1
                            results.append(
                                OperationResult(
                                    plan=plan,
                                    status=OperationStatus.SKIPPED,
                                    message=plan.reason,
                                )
                            )
                        else:
                            processed_count += 1
                            results.append(
                                OperationResult(
                                    plan=plan,
                                    status=OperationStatus.SUCCESS,
                                    message=plan.reason,
                                )
                            )
                        continue

                    if plan.op_type == OperationType.QUARANTINE_CORRUPT:
                        error_count += 1
                        errors.append(plan.reason)
                        results.append(
                            OperationResult(
                                plan=plan,
                                status=OperationStatus.FAILED,
                                error=plan.reason,
                            )
                        )
                        continue

                    if plan.op_type == OperationType.REVIEW_STAGE:
                        if self.config.paths.review_dir:
                            from media_cron.review.manager import ReviewManager

                            review_mgr = ReviewManager(self.config.paths.review_dir)
                            source_paths = getattr(plan, "unrecognized_files", [plan.source_path])

                            seeding_paths = set()
                            if torrent_plugin and torrent_plugin.processed_torrents:
                                for t in torrent_plugin.processed_torrents:
                                    for tf in getattr(t, "files", []):
                                        seeding_paths.add(Path(tf).resolve())

                            try:
                                review_mgr.stage_unrecognized(
                                    source_paths=source_paths,
                                    config=self.config,
                                    failure_reasons=[
                                        "Unrecognized media or metadata lookup failure"
                                    ],
                                    seeding_paths=seeding_paths,
                                    dry_run=False,
                                )
                                review_staged_count += 1
                                results.append(
                                    OperationResult(
                                        plan=plan,
                                        status=OperationStatus.SUCCESS,
                                        message=plan.reason,
                                    )
                                )
                            except Exception as e:
                                error_count += 1
                                errors.append(f"Failed to stage to review: {e}")
                                results.append(
                                    OperationResult(
                                        plan=plan,
                                        status=OperationStatus.FAILED,
                                        error=str(e),
                                    )
                                )
                        continue

                    plan.dry_run = False
                    op_result = None
                    last_skipped = None
                    for out in outputs:
                        res = out.execute(plan)
                        if res.status != OperationStatus.SKIPPED:
                            op_result = res
                            break
                        last_skipped = res

                    if op_result is None:
                        op_result = last_skipped or OperationResult(
                            plan=plan,
                            status=OperationStatus.SKIPPED,
                            message="No output plugin handled operation",
                        )

                    results.append(op_result)
                    if op_result.status == OperationStatus.SUCCESS:
                        if plan.op_type == OperationType.ORGANIZE:
                            processed_count += 1
                        elif plan.op_type == OperationType.UPGRADE_REPLACE:
                            upgraded_count += 1
                        elif plan.op_type in (OperationType.PURGE_JUNK, OperationType.PURGE_SAMPLE):
                            junk_count += 1
                    elif op_result.status == OperationStatus.SKIPPED:
                        skipped_count += 1
                    elif op_result.status == OperationStatus.FAILED:
                        error_count += 1
                        if op_result.error:
                            errors.append(op_result.error)

                if (
                    getattr(self.config, "video", None)
                    and self.config.video.enabled
                    and not is_video_spool
                ):
                    from media_cron.plugins.lookup.video import VIDEO_EXTENSIONS

                    total_videos = 0
                    organized_movies = 0
                    organized_episodes = 0
                    for res in results:
                        if res.status == OperationStatus.SUCCESS and res.plan.op_type in (
                            OperationType.ORGANIZE,
                            OperationType.UPGRADE_REPLACE,
                        ):
                            if res.plan.source_path.suffix.lower() in VIDEO_EXTENSIONS:
                                total_videos += 1
                                dest_str = str(res.plan.destination_path or "")
                                if "/Movies" in dest_str or "Movies/" in dest_str:
                                    organized_movies += 1
                                elif "/TV" in dest_str or "TV/" in dest_str:
                                    organized_episodes += 1

                    # Media server notification hook (debounced single request per batch)
                    rescan_sent = 0
                    rescan_errors = 0
                    video_cfg = self.config.video
                    if (
                        video_cfg.media_server
                        and video_cfg.media_server.enabled
                        and (organized_movies > 0 or organized_episodes > 0)
                    ):
                        try:
                            from media_cron.metadata.media_servers import get_media_server_client

                            ms_client = get_media_server_client(video_cfg.media_server.provider)
                            rescan_result = ms_client.trigger_rescan(
                                config=video_cfg.media_server,
                                library_id=video_cfg.media_server.library_id,
                                dry_run=False,
                            )
                            if rescan_result.success:
                                rescan_sent = 1
                            else:
                                rescan_errors = 1
                        except Exception as e:
                            import logging

                            logging.getLogger(__name__).warning("Media server rescan error: %s", e)
                            rescan_errors = 1

                    self._last_video_summary = {
                        "total_videos": total_videos,
                        "spooled_releases": 0,
                        "spool_skipped_count": 0,
                        "organized_movies": organized_movies,
                        "organized_episodes": organized_episodes,
                        "rescan_notifications_sent": rescan_sent,
                        "rescan_errors": rescan_errors,
                    }

                # Seeding Relocation & Tagging for processed torrents
                relocated_count = 0
                tagged_count = 0
                if torrent_plugin and torrent_plugin.processed_torrents:
                    client = torrent_plugin.client
                    client_cfg = torrent_plugin.config
                    seeding_cfg = client_cfg.seeding
                    torrent_seed_out = TorrentClientSeedOutput(
                        client=client, seeding_config=seeding_cfg
                    )

                    for torrent in torrent_plugin.processed_torrents:
                        # 1. Relocation if client_relocate enabled
                        if seeding_cfg.mode == "client_relocate":
                            relocate_dest = (
                                self.config.paths.seed_dir
                                if seeding_cfg.target_location == "seed_dir"
                                else self.config.paths.destination_dir
                            )
                            if relocate_dest:
                                plan = OperationPlan(
                                    op_type=OperationType.TORRENT_RELOCATE,
                                    transfer_mode=TransferMode.MOVE,
                                    source_path=Path(torrent.info_hash),
                                    destination_path=relocate_dest,
                                    reason=f"Client storage relocated to {relocate_dest}",
                                )
                                rel_res = torrent_seed_out.execute(plan)
                                results.append(rel_res)
                                if rel_res.status == OperationStatus.SUCCESS:
                                    relocated_count += 1
                                else:
                                    error_count += 1
                                    if rel_res.error:
                                        errors.append(rel_res.error)

                        # 2. Dual status update (tag + category) and pause
                        plan = OperationPlan(
                            op_type=OperationType.TORRENT_TAG,
                            transfer_mode=TransferMode.MOVE,
                            source_path=Path(torrent.info_hash),
                            reason=f"Applied tag '{seeding_cfg.completion_tag}' and category '{seeding_cfg.completion_category}'",
                        )
                        tag_res = torrent_seed_out.execute(plan)
                        results.append(tag_res)
                        if tag_res.status == OperationStatus.SUCCESS:
                            tagged_count += 1
                        else:
                            error_count += 1
                            if tag_res.error:
                                errors.append(tag_res.error)

                torrent_summary = None
                if torrent_plugin:
                    torrent_summary = {
                        "client": self.config.active_torrent_client,
                        "discovered_torrents": len(torrent_plugin.processed_torrents),
                        "ingested_torrents": len(torrent_plugin.processed_torrents),
                        "relocated_torrents": relocated_count,
                        "tagged_torrents": tagged_count,
                    }

                exit_code = EXIT_SUCCESS if error_count == 0 else EXIT_PARTIAL_OR_LOCKED

                routing_summary = self._build_routing_summary(
                    plans, results=results, discovered_count=len(staged_items)
                )

                return BatchSummary(
                    batch_id=batch_id,
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                    total_scanned=len(staged_items),
                    processed_count=processed_count,
                    upgraded_count=upgraded_count,
                    junk_purged_count=junk_count,
                    skipped_count=skipped_count,
                    error_count=error_count,
                    unrecognized_count=self._last_unrecognized_count,
                    review_staged_count=review_staged_count,
                    errors=errors,
                    operations=results,
                    dry_run=False,
                    exit_code=exit_code,
                    torrent_summary=torrent_summary,
                    audiobook_summary=self._last_audiobook_summary,
                    books_summary=self._last_books_summary,
                    music_summary=self._last_music_summary,
                    video_summary=self._get_video_summary(),
                    routing_summary=routing_summary,
                )
        except LockContentionError as e:
            return BatchSummary(
                batch_id=batch_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                exit_code=EXIT_PARTIAL_OR_LOCKED,
                errors=[str(e)],
                routing_summary=self._build_routing_summary([]),
            )
        except Exception as e:
            return BatchSummary(
                batch_id=batch_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                exit_code=EXIT_FATAL_ERROR,
                errors=[f"Fatal error: {e}"],
                routing_summary=self._build_routing_summary([]),
            )
