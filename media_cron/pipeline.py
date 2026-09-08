import uuid
from datetime import UTC, datetime
from pathlib import Path

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
from media_cron.plugins.registry import PluginRegistry, default_registry


class Pipeline:
    """Core media-cron processing pipeline."""

    def __init__(
        self,
        config: MediaCronConfig,
        registry: PluginRegistry | None = None,
    ) -> None:
        self.config = config
        self.registry = registry or default_registry

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
        self, source_path: Path, staging_path: Path
    ) -> tuple[list[OperationPlan], list[DiscoveredItem]]:
        """Generates a list of planned operations without mutating files."""
        input_plugin = self.registry.get_input(self.config.plugins.input)
        discovered_items = list(input_plugin.discover(source_path, staging_path, dry_run=True))

        lookup_plugins = self.registry.get_lookups(self.config.plugins.lookups)
        plans: list[OperationPlan] = []
        mode = TransferMode(self.config.general.mode)

        for item in discovered_items:
            path = item.source_path
            ext = path.suffix.lower()

            # 1. Check junk extensions
            if ext in self.config.general.junk_extensions:
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
                            source_path=path,
                            destination_path=dest_path,
                            reason=f"Identified as {asset.category.value}: '{asset.clean_title}'",
                            dry_run=True,
                        )
                    )

                    # Plan associated subtitles
                    for sub in asset.subtitle_files:
                        sub_ext = sub.suffix.lower()
                        # destination with sub_ext
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
                # Default fallback organize
                dest_path = (
                    (self.config.paths.destination_dir or Path("/tmp/media")) / "Other" / path.name
                )
                plans.append(
                    OperationPlan(
                        op_type=OperationType.ORGANIZE,
                        transfer_mode=mode,
                        source_path=path,
                        destination_path=dest_path,
                        reason="Uncategorized file",
                        dry_run=True,
                    )
                )

        return plans, discovered_items

    def run(self) -> BatchSummary:
        """Executes the pipeline according to active configuration."""
        started_at = datetime.now(UTC)
        batch_id = uuid.uuid4()
        dry_run = self.config.general.dry_run

        source_dir = self.config.paths.source_dir
        staging_dir = self.config.paths.staging_dir
        dest_dir = self.config.paths.destination_dir

        if not source_dir or not dest_dir:
            return BatchSummary(
                batch_id=batch_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                exit_code=EXIT_CONFIG_ERROR,
                errors=["Source directory and Destination directory must be specified."],
            )

        if dry_run:
            plans, discovered = self.plan(source_dir, staging_dir)
            results = [
                OperationResult(
                    plan=p, status=OperationStatus.SUCCESS, message="Simulated in dry-run mode"
                )
                for p in plans
            ]
            completed_at = datetime.now(UTC)
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
            )

        # Live Execution: Acquire lockfile in staging_dir
        try:
            with StagingLock(staging_dir):
                # 1. Ingest into staging
                input_plugin = self.registry.get_input(self.config.plugins.input)
                staged_items = list(input_plugin.discover(source_dir, staging_dir, dry_run=False))

                # 2. Generate and execute plans
                plans, _ = self.plan(staging_dir, staging_dir)
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
