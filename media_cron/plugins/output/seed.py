import os
import shutil

from media_cron.models import (
    OperationPlan,
    OperationResult,
    OperationStatus,
    OperationType,
)
from media_cron.plugins.base import OutputPlugin
from media_cron.plugins.registry import default_registry


class SeedRelocatorOutput(OutputPlugin):
    """Relocates original source media to a dedicated seeding directory."""

    @property
    def plugin_name(self) -> str:
        return "seed_relocator"

    def execute(self, plan: OperationPlan) -> OperationResult:
        if plan.op_type != OperationType.SEED_RELOCATE:
            return OperationResult(
                plan=plan,
                status=OperationStatus.SKIPPED,
                message="Operation not handled by seed relocator",
            )

        src = plan.source_path
        dest = plan.destination_path
        if not dest:
            return OperationResult(
                plan=plan, status=OperationStatus.FAILED, error="No seed destination specified"
            )

        if plan.dry_run:
            return OperationResult(
                plan=plan,
                status=OperationStatus.SUCCESS,
                message=f"[DRY-RUN] Would relocate seed material: {src.name} -> {dest}",
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            if not dest.exists():
                try:
                    os.link(src, dest)
                except OSError as err:
                    if err.errno == 18:  # EXDEV
                        shutil.copy2(src, dest)
                    else:
                        raise

            return OperationResult(
                plan=plan,
                status=OperationStatus.SUCCESS,
                message=f"Seeded {src.name} at {dest}",
            )
        except Exception as e:
            return OperationResult(
                plan=plan,
                status=OperationStatus.FAILED,
                error=f"Failed to seed {src} at {dest}: {e}",
            )


default_registry.register_output("seed_relocator", SeedRelocatorOutput)
