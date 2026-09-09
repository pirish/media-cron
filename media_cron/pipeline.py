import uuid
from datetime import UTC, datetime
from pathlib import Path

import media_cron.plugins  # noqa: F401
from media_cron.config import MediaCronConfig
from media_cron.lock import LockContentionError, StagingLock
from media_cron.models import (
    EXIT_CONFIG_ERROR,
    EXIT_FATAL_ERROR,
    EXIT_PARTIAL_OR_LOCKED,
    EXIT_SUCCESS,
    BatchSummary,
    DiscoveredItem,
    MediaAsset,
    MediaCategory,
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
        self._last_audiobook_summary: dict | None = None
        self._last_books_summary: dict | None = None

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
        dest_root = self.config.paths.destination_dir or Path("/tmp/media")

        # Determine category key
        if asset.category == MediaCategory.VIDEO_MOVIE:
            tmpl = self.config.templates.get(
                "movie", "Movies/{title} ({year})/{title} ({year}).{ext}"
            )
            rel_path = tmpl.format(
                title=asset.clean_title,
                year=asset.year or "Unknown",
                ext=asset.extension.lstrip("."),
            )
        elif asset.category == MediaCategory.VIDEO_SERIES:
            tmpl = self.config.templates.get(
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

    def plan(
        self, source_path: Path | None, staging_path: Path
    ) -> tuple[list[OperationPlan], list[DiscoveredItem], TorrentInputPlugin | None]:
        """Generates a list of planned operations without mutating files."""
        seen_paths: set[Path] = set()
        if source_path is not None and source_path.resolve() == staging_path.resolve():
            scanner = DirectoryScannerInput()
            raw_items = list(scanner.discover(staging_path, staging_path, dry_run=True))
            for item in raw_items:
                seen_paths.add(item.source_path.resolve())
            torrent_plugin = None
        else:
            input_plugins, torrent_plugin = self._get_input_plugins()
            raw_items = []

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
                            )
                        )
            else:
                discovered_items.append(item)

        lookup_plugins = self.registry.get_lookups(self.config.plugins.lookups)
        for lk in lookup_plugins:
            if hasattr(lk, "dry_run"):
                lk.dry_run = self.config.general.dry_run
            if hasattr(lk, "configure"):
                if getattr(lk, "plugin_name", "") == "book_meta" or (
                    hasattr(lk, "identifier") and hasattr(lk.identifier, "total_books")
                ):
                    lk.configure(self.config.books)
                else:
                    lk.configure(self.config.audiobook)
            elif hasattr(lk, "identifier") and hasattr(lk.identifier, "config"):
                if hasattr(lk.identifier, "total_books"):
                    lk.identifier.config = self.config.books
                else:
                    lk.identifier.config = self.config.audiobook
        plans: list[OperationPlan] = []
        mode = TransferMode(self.config.general.mode)

        for item in discovered_items:
            path = item.source_path
            ext = path.suffix.lower()

            # 1. Check junk extensions
            if ext in self.config.general.junk_extensions:
                is_book = False
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
                                is_book = True
                                break
                if not is_book:
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
                    dest_path = self._resolve_destination_path(asset)
                    plans.append(
                        OperationPlan(
                            op_type=OperationType.ORGANIZE,
                            transfer_mode=mode,
                            source_path=asset.path,
                            destination_path=dest_path,
                            reason=f"Identified as {asset.category.value}: '{asset.clean_title}'",
                            dry_run=True,
                        )
                    )

                    # Plan associated subtitles
                    for sub in asset.subtitle_files:
                        sub_resolved = sub.resolve()
                        if sub_resolved in seen_paths:
                            continue
                        sub_ext = sub.suffix.lower()
                        dest_sub = dest_path.with_suffix(sub_ext)
                        plans.append(
                            OperationPlan(
                                op_type=OperationType.ORGANIZE,
                                transfer_mode=mode,
                                source_path=sub,
                                destination_path=dest_sub,
                                reason=f"Preserved associated subtitle for '{asset.clean_title}'",
                                dry_run=True,
                            )
                        )

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
                # Non-media clutter or unsupported files purged from staging
                plans.append(
                    OperationPlan(
                        op_type=OperationType.PURGE_JUNK,
                        transfer_mode=mode,
                        source_path=path,
                        destination_path=None,
                        reason=f"Unrecognized non-media clutter: '{path.name}'",
                        dry_run=True,
                    )
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

        # Collect audiobook and book telemetry summary
        self._last_audiobook_summary = None
        self._last_books_summary = None
        for lk in lookup_plugins:
            if hasattr(lk, "identifier") and hasattr(lk.identifier, "get_summary"):
                summary_data = lk.identifier.get_summary()
                if summary_data.get("total_audiobooks", 0) > 0:
                    self._last_audiobook_summary = summary_data
                if summary_data.get("total_books", 0) > 0:
                    self._last_books_summary = summary_data

        return plans, discovered_items, torrent_plugin

    def run(self) -> BatchSummary:
        """Executes the pipeline according to active configuration."""
        started_at = datetime.now(UTC)
        batch_id = uuid.uuid4()
        dry_run = self.config.general.dry_run

        source_dir = self.config.paths.source_dir
        staging_dir = self.config.paths.staging_dir
        dest_dir = self.config.paths.destination_dir

        if not dest_dir:
            return BatchSummary(
                batch_id=batch_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                exit_code=EXIT_CONFIG_ERROR,
                errors=["Destination directory must be specified."],
            )

        if not self.config.active_torrent_client and not source_dir:
            return BatchSummary(
                batch_id=batch_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                exit_code=EXIT_CONFIG_ERROR,
                errors=[
                    "Source directory must be specified when torrent client is not configured."
                ],
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
                operations=results,
                dry_run=True,
                exit_code=EXIT_SUCCESS,
                torrent_summary=torrent_summary,
                audiobook_summary=self._last_audiobook_summary,
                books_summary=self._last_books_summary,
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

                for plan in plans:
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
                    errors=errors,
                    operations=results,
                    dry_run=False,
                    exit_code=exit_code,
                    torrent_summary=torrent_summary,
                    audiobook_summary=self._last_audiobook_summary,
                    books_summary=self._last_books_summary,
                )
        except LockContentionError as e:
            return BatchSummary(
                batch_id=batch_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                exit_code=EXIT_PARTIAL_OR_LOCKED,
                errors=[str(e)],
            )
        except Exception as e:
            return BatchSummary(
                batch_id=batch_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                exit_code=EXIT_FATAL_ERROR,
                errors=[f"Fatal error: {e}"],
            )
