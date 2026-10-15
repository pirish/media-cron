import logging
import os
import re
import shutil
from pathlib import Path

from media_cron.models import (
    OperationPlan,
    OperationResult,
    OperationStatus,
    OperationType,
    TransferMode,
)
from media_cron.plugins.base import OutputPlugin
from media_cron.plugins.registry import default_registry
from media_cron.recovery.verifier import TransferVerifier

logger = logging.getLogger(__name__)

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

    def __init__(self, verifier: TransferVerifier | None = None) -> None:
        self.verifier = verifier if verifier is not None else TransferVerifier()

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

        # 1. Collision detection and recovery check
        target_to_compare: Path | None = None
        if dest.exists():
            target_to_compare = dest
        elif dest.parent.exists() and dest.suffix.lower() in (
            ".mkv",
            ".mp4",
            ".avi",
            ".mov",
            ".wmv",
            ".m4v",
        ):
            # Check if an alternative quality variant already exists in the destination directory
            video_siblings = [
                p
                for p in dest.parent.iterdir()
                if p.is_file()
                and p != dest
                and p.suffix.lower() in (".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v")
            ]
            tv_match = re.search(r"S\d{2}E\d{2}", dest.name, re.IGNORECASE)
            if tv_match:
                ep_code = tv_match.group(0).lower()
                matched = [p for p in video_siblings if ep_code in p.name.lower()]
                if matched:
                    target_to_compare = matched[0]
            elif video_siblings:
                target_to_compare = video_siblings[0]

        if target_to_compare is not None:
            # Check identical (same inode or size & hash)
            if target_to_compare.stat().st_size == src.stat().st_size:
                try:
                    if target_to_compare.stat().st_ino == src.stat().st_ino:
                        return OperationResult(
                            plan=plan,
                            status=OperationStatus.SKIPPED,
                            message="Identical file already hardlinked at destination",
                        )
                except AttributeError:
                    pass

                # Verify content hash (FR-006, FR-007)
                verify_res = self.verifier.verify_item(src, target_to_compare)
                if verify_res.can_resume:
                    logger.info(
                        "Destination file '%s' verified matching; bypassing transfer and completing post-transfer lifecycle (%d bytes saved)",
                        target_to_compare,
                        verify_res.bytes_saved,
                    )
                    self.verifier.summary.transfers_bypassed += 1
                    self.verifier.summary.bytes_saved += verify_res.bytes_saved
                    if (
                        plan.transfer_mode == TransferMode.MOVE
                        and not plan.dry_run
                        and src.exists()
                    ):
                        if src.resolve() != target_to_compare.resolve():
                            try:
                                if src.is_dir():
                                    shutil.rmtree(src)
                                elif src.is_file():
                                    src.unlink()
                            except Exception as e:
                                logger.warning(
                                    "Failed to clean up source '%s' after transfer bypass: %s",
                                    src,
                                    e,
                                )
                    return OperationResult(
                        plan=plan,
                        status=OperationStatus.SKIPPED,
                        message=f"Destination file already matches source content hash; transfer bypassed ({verify_res.bytes_saved} bytes saved)",
                    )
                else:
                    # Same size, but hash mismatch! Corrupted destination file! (FR-008, US4)
                    logger.warning(
                        "Corrupted destination file '%s' detected (hash_mismatch); purging before fresh transfer",
                        target_to_compare,
                    )
                    try:
                        self.verifier.purge_item(
                            target_to_compare,
                            allowed_parent_roots=[target_to_compare.parent],
                            dry_run=plan.dry_run,
                        )
                        self.verifier.summary.items_purged += 1
                        target_to_compare = None
                    except (PermissionError, OSError) as e:
                        logger.error(
                            "Permission or I/O error purging corrupted destination file '%s': %s. Halting write to prevent dirty state.",
                            target_to_compare,
                            e,
                        )
                        return OperationResult(
                            plan=plan,
                            status=OperationStatus.FAILED,
                            error=f"Permission or I/O error purging corrupted destination file '{target_to_compare}': {e}",
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to purge corrupted destination file '%s': %s",
                            target_to_compare,
                            e,
                        )
                        return OperationResult(
                            plan=plan,
                            status=OperationStatus.FAILED,
                            error=f"Failed to purge corrupted destination file '{target_to_compare}': {e}",
                        )

            # Check quality comparison if candidate was not already purged
            if target_to_compare is not None:
                src_rank = max(
                    self._get_quality_rank(src.name), self._get_quality_rank(plan.reason)
                )
                dest_rank = self._get_quality_rank(target_to_compare.name)

                should_upgrade = False
                if dest_rank > 0 and src_rank > 0:
                    if src_rank > dest_rank:
                        should_upgrade = True
                    elif (
                        src_rank == dest_rank
                        and src.stat().st_size > target_to_compare.stat().st_size
                    ):
                        should_upgrade = True
                else:
                    # If destination has no resolution tag, compare file size
                    if src.stat().st_size > target_to_compare.stat().st_size:
                        should_upgrade = True

                if should_upgrade:
                    plan.op_type = OperationType.UPGRADE_REPLACE
                    if not plan.dry_run:
                        try:
                            self.verifier.purge_item(
                                target_to_compare,
                                allowed_parent_roots=[target_to_compare.parent],
                                dry_run=False,
                            )
                            self.verifier.summary.items_purged += 1
                        except (PermissionError, OSError) as e:
                            logger.error(
                                "Permission or I/O error purging destination file '%s': %s. Halting write to prevent dirty state.",
                                target_to_compare,
                                e,
                            )
                            return OperationResult(
                                plan=plan,
                                status=OperationStatus.FAILED,
                                error=f"Permission or I/O error purging destination file '{target_to_compare}': {e}",
                            )
                        except Exception as e:
                            logger.error(
                                "Failed to purge destination file '%s': %s", target_to_compare, e
                            )
                            return OperationResult(
                                plan=plan,
                                status=OperationStatus.FAILED,
                                error=f"Failed to purge destination file '{target_to_compare}': {e}",
                            )
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
