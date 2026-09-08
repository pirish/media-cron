import os
import re
import shutil

from media_cron.models import (
    OperationPlan,
    OperationResult,
    OperationStatus,
    OperationType,
    TransferMode,
)
from media_cron.plugins.base import OutputPlugin
from media_cron.plugins.registry import default_registry

RES_RANK = {
    "2160p": 4,
    "4k": 4,
    "uhd": 4,
    "1080p": 3,
    "720p": 2,
    "480p": 1,
}


class LibraryOrganizerOutput(OutputPlugin):
    """Transfers media assets to structured destination libraries with quality collision checks."""

    @property
    def plugin_name(self) -> str:
        return "library_organizer"

    def _get_quality_rank(self, path_or_reason: str) -> int:
        match = re.search(r"\b(2160p|4k|uhd|1080p|720p|480p)\b", path_or_reason, re.IGNORECASE)
        if match:
            return RES_RANK.get(match.group(1).lower(), 0)
        return 0

    def execute(self, plan: OperationPlan) -> OperationResult:
        if plan.op_type not in (OperationType.ORGANIZE, OperationType.UPGRADE_REPLACE):
            return OperationResult(
                plan=plan,
                status=OperationStatus.SKIPPED,
                message="Operation not handled by library organizer",
            )

        src = plan.source_path
        dest = plan.destination_path
        if not dest:
            return OperationResult(
                plan=plan, status=OperationStatus.FAILED, error="No destination path specified"
            )

        # 1. Collision detection
        if dest.exists():
            # Check identical (same inode or size)
            if dest.stat().st_size == src.stat().st_size:
                try:
                    if dest.stat().st_ino == src.stat().st_ino:
                        return OperationResult(
                            plan=plan,
                            status=OperationStatus.SKIPPED,
                            message="Identical file already hardlinked at destination",
                        )
                except AttributeError:
                    pass
                return OperationResult(
                    plan=plan,
                    status=OperationStatus.SKIPPED,
                    message="Identical file size already exists at destination",
                )

            # Check quality comparison
            src_rank = max(self._get_quality_rank(src.name), self._get_quality_rank(plan.reason))
            dest_rank = self._get_quality_rank(dest.name)

            should_upgrade = False
            if dest_rank > 0 and src_rank > 0:
                if src_rank > dest_rank:
                    should_upgrade = True
                elif src_rank == dest_rank and src.stat().st_size > dest.stat().st_size:
                    should_upgrade = True
            else:
                # If destination has no resolution tag, compare file size
                if src.stat().st_size > dest.stat().st_size:
                    should_upgrade = True

            if should_upgrade:
                plan.op_type = OperationType.UPGRADE_REPLACE
                if not plan.dry_run:
                    dest.unlink()
            else:
                plan.op_type = OperationType.SKIP_COLLISION
                return OperationResult(
                    plan=plan,
                    status=OperationStatus.SKIPPED,
                    message="Existing destination file is of equal or higher quality",
                )

        if plan.dry_run:
            return OperationResult(
                plan=plan,
                status=OperationStatus.SUCCESS,
                message=f"[DRY-RUN] Would {plan.transfer_mode.value} {src.name} to {dest}",
            )

        # 2. Execute transfer
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            if plan.transfer_mode == TransferMode.HARDLINK:
                try:
                    os.link(src, dest)
                except OSError as err:
                    # Fallback to copy if cross-device
                    if err.errno == 18:  # EXDEV
                        shutil.copy2(src, dest)
                    else:
                        raise
            elif plan.transfer_mode == TransferMode.MOVE:
                shutil.move(str(src), str(dest))
            elif plan.transfer_mode == TransferMode.COPY:
                shutil.copy2(src, dest)

            return OperationResult(
                plan=plan,
                status=OperationStatus.SUCCESS,
                message=f"Placed {src.name} at {dest} ({plan.transfer_mode.value})",
            )
        except Exception as e:
            return OperationResult(
                plan=plan,
                status=OperationStatus.FAILED,
                error=f"Failed to place {src} at {dest}: {e}",
            )


default_registry.register_output("library_organizer", LibraryOrganizerOutput)
