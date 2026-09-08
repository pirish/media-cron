from media_cron.models import (
    OperationPlan,
    OperationResult,
    OperationStatus,
    OperationType,
)
from media_cron.plugins.base import OutputPlugin
from media_cron.plugins.registry import default_registry
from media_cron.torrent.base import TorrentClientProtocol


class TorrentClientSeedOutput(OutputPlugin):
    """Commands external torrent clients to relocate storage and update completion state."""

    def __init__(
        self,
        client: TorrentClientProtocol | None = None,
        seeding_config: object | None = None,
    ) -> None:
        self.client = client
        self.seeding_config = seeding_config

    @property
    def plugin_name(self) -> str:
        return "torrent_seed"

    def execute(self, plan: OperationPlan) -> OperationResult:
        if plan.op_type == OperationType.TORRENT_RELOCATE:
            return self._execute_relocate(plan)
        elif plan.op_type == OperationType.TORRENT_TAG:
            return self._execute_tag(plan)
        else:
            return OperationResult(
                plan=plan,
                status=OperationStatus.SKIPPED,
                message="Operation not handled by torrent seed output",
            )

    def _execute_relocate(self, plan: OperationPlan) -> OperationResult:
        dest = plan.destination_path
        if not dest:
            return OperationResult(
                plan=plan,
                status=OperationStatus.FAILED,
                error="No destination path specified for torrent relocation",
            )

        info_hash = str(plan.source_path)
        if plan.dry_run:
            return OperationResult(
                plan=plan,
                status=OperationStatus.SUCCESS,
                message=f"[DRY-RUN] Would relocate torrent storage: {info_hash} -> {dest}",
            )

        if not self.client:
            return OperationResult(
                plan=plan,
                status=OperationStatus.FAILED,
                error="No torrent client available for storage relocation",
            )

        try:
            success = self.client.relocate_storage(info_hash, dest)
            if success:
                return OperationResult(
                    plan=plan,
                    status=OperationStatus.SUCCESS,
                    message=f"Relocated torrent storage for {info_hash} to {dest}",
                )
            else:
                return OperationResult(
                    plan=plan,
                    status=OperationStatus.FAILED,
                    error=f"Failed to relocate torrent storage for {info_hash} to {dest}",
                )
        except Exception as e:
            return OperationResult(
                plan=plan,
                status=OperationStatus.FAILED,
                error=f"Error relocating torrent storage for {info_hash} to {dest}: {e}",
            )

    def _execute_tag(self, plan: OperationPlan) -> OperationResult:
        info_hash = str(plan.source_path)
        if plan.dry_run:
            return OperationResult(
                plan=plan,
                status=OperationStatus.SUCCESS,
                message=f"[DRY-RUN] Would update torrent status: {info_hash}",
            )

        if not self.client:
            return OperationResult(
                plan=plan,
                status=OperationStatus.FAILED,
                error="No torrent client available for tagging",
            )

        tag = getattr(self.seeding_config, "completion_tag", "") or ""
        category = getattr(self.seeding_config, "completion_category", "") or ""
        pause = bool(getattr(self.seeding_config, "pause_after_process", False))

        try:
            success = self.client.apply_completion_state(
                info_hash=info_hash,
                tag=tag,
                category=category,
                pause=pause,
            )
            if success:
                return OperationResult(
                    plan=plan,
                    status=OperationStatus.SUCCESS,
                    message=f"Applied completion state for {info_hash}",
                )
            else:
                return OperationResult(
                    plan=plan,
                    status=OperationStatus.FAILED,
                    error=f"Failed to apply completion state for {info_hash}",
                )
        except Exception as e:
            return OperationResult(
                plan=plan,
                status=OperationStatus.FAILED,
                error=f"Error applying completion state for {info_hash}: {e}",
            )


default_registry.register_output("torrent_seed", TorrentClientSeedOutput)
