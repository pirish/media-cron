from pathlib import Path

from media_cron.models import (
    OperationPlan,
    OperationStatus,
    OperationType,
    TransferMode,
)
from media_cron.plugins.base import OutputPlugin
from media_cron.plugins.output.organizer import LibraryOrganizerOutput
from media_cron.plugins.output.seed import SeedRelocatorOutput


def test_output_plugins_satisfy_protocol(tmp_path: Path):
    organizer = LibraryOrganizerOutput()
    seeder = SeedRelocatorOutput()

    assert isinstance(organizer, OutputPlugin)
    assert isinstance(seeder, OutputPlugin)
    assert organizer.plugin_name == "library_organizer"
    assert seeder.plugin_name == "seed_relocator"


def test_library_organizer_hardlink(tmp_path: Path):
    organizer = LibraryOrganizerOutput()
    src = tmp_path / "staging" / "movie.mkv"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"content" * 10)

    dest = tmp_path / "library" / "Movies" / "movie.mkv"

    plan = OperationPlan(
        op_type=OperationType.ORGANIZE,
        transfer_mode=TransferMode.HARDLINK,
        source_path=src,
        destination_path=dest,
        reason="Organizing",
        dry_run=False,
    )
    res = organizer.execute(plan)
    assert res.status == OperationStatus.SUCCESS
    assert dest.exists()
    assert dest.stat().st_ino == src.stat().st_ino  # Hardlinked
