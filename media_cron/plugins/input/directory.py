import shutil
from collections.abc import Iterable
from pathlib import Path

from media_cron.models import DiscoveredItem
from media_cron.plugins.base import InputPlugin
from media_cron.plugins.registry import default_registry


class DirectoryScannerInput(InputPlugin):
    """Discovers media files from a local source directory and stages them."""

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

        for src_file in entries:
            stat = src_file.stat()
            rel_path = src_file.relative_to(source_path)

            if dry_run:
                yield DiscoveredItem(
                    source_path=src_file,
                    file_size=stat.st_size,
                    modified_time=stat.st_mtime,
                    is_archive=src_file.suffix.lower() in (".zip", ".rar", ".7z", ".tar"),
                    is_directory=False,
                )
            else:
                dest_file = staging_path / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
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
