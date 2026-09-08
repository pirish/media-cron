from pathlib import Path

from media_cron.models import (
    OperationPlan,
    OperationStatus,
    OperationType,
    TransferMode,
)
from media_cron.plugins.output.organizer import LibraryOrganizerOutput


def test_collision_upgrade_higher_quality(tmp_path: Path):
    organizer = LibraryOrganizerOutput()
    dest = tmp_path / "Movies" / "Inception (2010)" / "Inception (2010).mkv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Existing lower-quality file (720p, small)
    dest.write_bytes(b"old 720p version" * 50)

    # New 1080p incoming file
    src = tmp_path / "staging" / "Inception.2010.1080p.mkv"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"new 1080p high quality version" * 200)

    plan = OperationPlan(
        op_type=OperationType.ORGANIZE,
        transfer_mode=TransferMode.MOVE,
        source_path=src,
        destination_path=dest,
        reason="1080p",
        dry_run=False,
    )
    result = organizer.execute(plan)
    assert result.status == OperationStatus.SUCCESS
    assert plan.op_type == OperationType.UPGRADE_REPLACE
    assert dest.stat().st_size == len(b"new 1080p high quality version" * 200)


def test_collision_skip_lower_quality(tmp_path: Path):
    organizer = LibraryOrganizerOutput()
    dest = tmp_path / "Movies" / "Inception (2010)" / "Inception (2010).mkv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"existing high quality version" * 500)

    # New smaller/lower file
    src = tmp_path / "staging" / "Inception.2010.480p.mkv"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"low" * 10)

    plan = OperationPlan(
        op_type=OperationType.ORGANIZE,
        transfer_mode=TransferMode.MOVE,
        source_path=src,
        destination_path=dest,
        reason="480p",
        dry_run=False,
    )
    result = organizer.execute(plan)
    assert result.status == OperationStatus.SKIPPED
    assert plan.op_type == OperationType.SKIP_COLLISION
