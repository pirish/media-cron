from media_cron.models import (
    OperationPlan,
    OperationResult,
    OperationStatus,
    OperationType,
)
from media_cron.plugins.base import OutputPlugin
from media_cron.plugins.registry import default_registry


class JunkCleanerOutput(OutputPlugin):
    """Purges junk files, sub-50MB samples, and prunes empty directories."""

    @property
    def plugin_name(self) -> str:
        return "junk_cleaner"

    def execute(self, plan: OperationPlan) -> OperationResult:
        if plan.op_type not in (OperationType.PURGE_JUNK, OperationType.PURGE_SAMPLE):
            return OperationResult(
                plan=plan,
                status=OperationStatus.SKIPPED,
                message="Operation not handled by junk cleaner",
            )

        src = plan.source_path
        if plan.dry_run:
            return OperationResult(
                plan=plan,
                status=OperationStatus.SUCCESS,
                message=f"[DRY-RUN] Would purge: {src.name} ({plan.reason})",
            )

        try:
            if src.exists():
                src.unlink()
                # Prune empty parent directory if empty
                parent = src.parent
                if parent.is_dir() and not any(parent.iterdir()):
                    try:
                        parent.rmdir()
                    except OSError:
                        pass
            return OperationResult(
                plan=plan,
                status=OperationStatus.SUCCESS,
                message=f"Purged {src.name}",
            )
        except Exception as e:
            return OperationResult(
                plan=plan,
                status=OperationStatus.FAILED,
                error=f"Failed to purge {src}: {e}",
            )


default_registry.register_output("junk_cleaner", JunkCleanerOutput)
