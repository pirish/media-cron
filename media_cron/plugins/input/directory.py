import logging
import shutil
from collections.abc import Iterable
from pathlib import Path

from media_cron.models import DiscoveredItem
from media_cron.plugins.base import InputPlugin
from media_cron.plugins.registry import default_registry
from media_cron.recovery.verifier import TransferVerifier

logger = logging.getLogger(__name__)


class DirectoryScannerInput(InputPlugin):
    """Discovers media files from a local source directory and stages them."""

    def __init__(self, verifier: TransferVerifier | None = None) -> None:
        self.verifier = verifier if verifier is not None else TransferVerifier()

    @property
    def plugin_name(self) -> str:
        return "directory_scanner"

    def discover(
        self, source_path: Path, staging_path: Path, dry_run: bool = False
    ) -> Iterable[DiscoveredItem]:
        source_path = Path(source_path)
        staging_path = Path(staging_path)

        if not source_path.exists():
            return

        # Gather files
        entries = []
        for p in source_path.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                entries.append(p)

        is_same_location = source_path.resolve() == staging_path.resolve()

        for src_file in entries:
            stat = src_file.stat()
            rel_path = src_file.relative_to(source_path)
            dest_file = staging_path / rel_path

            if is_same_location:
                yield DiscoveredItem(
                    source_path=src_file,
                    file_size=stat.st_size,
                    modified_time=stat.st_mtime,
                    is_archive=src_file.suffix.lower() in (".zip", ".rar", ".7z", ".tar"),
                    is_directory=False,
                )
                continue

            if dry_run:
                if dest_file.exists():
                    verify_res = self.verifier.verify_item(src_file, dest_file)
                    if verify_res.can_resume:
                        logger.info(
                            "[DRY-RUN] Staged item '%s' matches source (%d bytes saved)",
                            dest_file.name,
                            verify_res.bytes_saved,
                        )
                        self.verifier.summary.items_resumed += 1
                        self.verifier.summary.bytes_saved += verify_res.bytes_saved
                    else:
                        logger.warning(
                            "[DRY-RUN] Staged item '%s' corrupted (%s); would purge and restart",
                            dest_file.name,
                            verify_res.overall_status.value,
                        )
                        self.verifier.summary.items_purged += 1
                yield DiscoveredItem(
                    source_path=src_file,
                    file_size=stat.st_size,
                    modified_time=stat.st_mtime,
                    is_archive=src_file.suffix.lower() in (".zip", ".rar", ".7z", ".tar"),
                    is_directory=False,
                )
            else:
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                if dest_file.exists():
                    verify_res = self.verifier.verify_item(src_file, dest_file)
                    if verify_res.can_resume:
                        logger.info(
                            "Staged item '%s' verified matching; resuming without re-copying (%d bytes saved)",
                            dest_file.name,
                            verify_res.bytes_saved,
                        )
                        self.verifier.summary.items_resumed += 1
                        self.verifier.summary.bytes_saved += verify_res.bytes_saved
                        src_file.unlink()  # Move mode cleanup of source file
                        staged_stat = dest_file.stat()
                        yield DiscoveredItem(
                            source_path=dest_file,
                            file_size=staged_stat.st_size,
                            modified_time=staged_stat.st_mtime,
                            is_archive=dest_file.suffix.lower() in (".zip", ".rar", ".7z", ".tar"),
                            is_directory=False,
                        )
                        continue
                    else:
                        logger.warning(
                            "Corrupted staged candidate '%s' detected (%s); purging and restarting",
                            dest_file.name,
                            verify_res.overall_status.value,
                        )
                        self.verifier.purge_item(
                            dest_file, allowed_parent_roots=[staging_path], dry_run=False
                        )
                        self.verifier.summary.items_purged += 1

                # Atomically move to staging
                shutil.move(str(src_file), str(dest_file))
                staged_stat = dest_file.stat()
                yield DiscoveredItem(
                    source_path=dest_file,
                    file_size=staged_stat.st_size,
                    modified_time=staged_stat.st_mtime,
                    is_archive=dest_file.suffix.lower() in (".zip", ".rar", ".7z", ".tar"),
                    is_directory=False,
                )

        # In live mode, clean up empty folders in source
        if not dry_run:
            for d in sorted(source_path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                if d.is_dir() and not any(d.iterdir()):
                    try:
                        d.rmdir()
                    except OSError:
                        pass


# Register by default
default_registry.register_input("directory_scanner", DirectoryScannerInput)
