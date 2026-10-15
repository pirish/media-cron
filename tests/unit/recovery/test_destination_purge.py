from pathlib import Path
from unittest.mock import MagicMock

from media_cron.models import OperationPlan, OperationStatus, OperationType, TransferMode
from media_cron.plugins.output.organizer import LibraryOrganizerOutput
from media_cron.recovery.verifier import TransferVerifier


def test_corrupt_destination_size_mismatch_purged_and_retransferred(tmp_path: Path):
    src = tmp_path / "staging" / "movie.mkv"
    src.parent.mkdir()
    src.write_bytes(b"A" * 1024)

    dest = tmp_path / "dest" / "movie.mkv"
    dest.parent.mkdir()
    dest.write_bytes(b"A" * 512)  # Truncated

    plan = OperationPlan(
        op_type=OperationType.ORGANIZE,
        source_path=src,
        destination_path=dest,
        transfer_mode=TransferMode.COPY,
        reason="Organize Movie",
    )

    verifier = TransferVerifier()
    organizer = LibraryOrganizerOutput(verifier=verifier)
    res = organizer.execute(plan)

    assert res.status == OperationStatus.SUCCESS
    assert verifier.summary.items_purged == 1
    assert dest.read_bytes() == b"A" * 1024


def test_corrupt_destination_hash_mismatch_purged_and_retransferred(tmp_path: Path):
    src = tmp_path / "staging" / "movie.mkv"
    src.parent.mkdir()
    src.write_bytes(b"ValidContent1234")

    dest = tmp_path / "dest" / "movie.mkv"
    dest.parent.mkdir()
    dest.write_bytes(b"CorruptCont1234")  # Same length, wrong content

    plan = OperationPlan(
        op_type=OperationType.ORGANIZE,
        source_path=src,
        destination_path=dest,
        transfer_mode=TransferMode.COPY,
        reason="Organize Movie",
    )

    verifier = TransferVerifier()
    organizer = LibraryOrganizerOutput(verifier=verifier)
    res = organizer.execute(plan)

    assert res.status == OperationStatus.SUCCESS
    assert verifier.summary.items_purged == 1
    assert dest.read_bytes() == b"ValidContent1234"


def test_destination_purge_permission_error_halts_dirty_write(tmp_path: Path):
    src = tmp_path / "staging" / "movie.mkv"
    src.parent.mkdir()
    src.write_bytes(b"ValidContent1234")

    dest = tmp_path / "dest" / "movie.mkv"
    dest.parent.mkdir()
    dest.write_bytes(b"CorruptContent!!")

    plan = OperationPlan(
        op_type=OperationType.ORGANIZE,
        source_path=src,
        destination_path=dest,
        transfer_mode=TransferMode.COPY,
        reason="Organize Movie",
    )

    verifier = TransferVerifier()
    verifier.purge_item = MagicMock(side_effect=PermissionError("Permission denied: cannot delete"))
    organizer = LibraryOrganizerOutput(verifier=verifier)
    res = organizer.execute(plan)

    assert res.status == OperationStatus.FAILED
    assert "Permission" in res.error
    assert dest.read_bytes() == b"CorruptContent!!"  # Destination was not overwritten


def test_destination_purge_boundary_error_halts_write(tmp_path: Path):
    src = tmp_path / "staging" / "movie.mkv"
    src.parent.mkdir()
    src.write_bytes(b"ValidContent1234")

    dest = tmp_path / "dest" / "movie.mkv"
    dest.parent.mkdir()
    dest.write_bytes(b"CorruptContent!!")

    plan = OperationPlan(
        op_type=OperationType.ORGANIZE,
        source_path=src,
        destination_path=dest,
        transfer_mode=TransferMode.COPY,
        reason="Organize Movie",
    )

    verifier = TransferVerifier()
    verifier.purge_item = MagicMock(side_effect=ValueError("violates boundary containment"))
    organizer = LibraryOrganizerOutput(verifier=verifier)
    res = organizer.execute(plan)

    assert res.status == OperationStatus.FAILED
    assert "boundary" in res.error.lower()
