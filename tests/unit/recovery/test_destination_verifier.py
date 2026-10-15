from pathlib import Path

from media_cron.models import OperationPlan, OperationStatus, OperationType, TransferMode
from media_cron.plugins.output.organizer import LibraryOrganizerOutput
from media_cron.recovery.verifier import TransferVerifier


def test_library_organizer_bypasses_transfer_when_destination_matches(tmp_path: Path):
    src = tmp_path / "staging" / "Movie (2020).mkv"
    src.parent.mkdir()
    src.write_bytes(b"Exact Movie Content" * 50)

    dest = tmp_path / "dest" / "Movie (2020)" / "Movie (2020).mkv"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"Exact Movie Content" * 50)

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

    assert res.status == OperationStatus.SKIPPED
    assert "transfer bypassed" in res.message.lower()
    assert verifier.summary.transfers_bypassed == 1
    assert verifier.summary.bytes_saved == len(b"Exact Movie Content" * 50)
