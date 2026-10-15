from pathlib import Path

from media_cron.models import OperationPlan, OperationStatus, OperationType, TransferMode
from media_cron.plugins.output.organizer import LibraryOrganizerOutput
from media_cron.recovery.verifier import TransferVerifier


def test_integration_destination_corruption_replacement(tmp_path: Path):
    # Setup source file in staging
    staging_file = tmp_path / "staging" / "Inception.2010.1080p.mkv"
    staging_file.parent.mkdir(parents=True)
    valid_data = b"INCEPTION_VALID_VIDEO_CONTENT" * 50
    staging_file.write_bytes(valid_data)

    # Setup corrupt file at destination library
    dest_file = tmp_path / "library" / "Movies" / "Inception (2010)" / "Inception (2010).mkv"
    dest_file.parent.mkdir(parents=True)
    corrupt_data = b"INCEPTION_CORRUPTED_TRUNCATED_CONTENT"
    dest_file.write_bytes(corrupt_data)

    plan = OperationPlan(
        op_type=OperationType.ORGANIZE,
        source_path=staging_file,
        destination_path=dest_file,
        transfer_mode=TransferMode.COPY,
        reason="Organize Inception",
    )

    verifier = TransferVerifier()
    organizer = LibraryOrganizerOutput(verifier=verifier)

    result = organizer.execute(plan)

    # Verification
    assert result.status == OperationStatus.SUCCESS
    assert verifier.summary.items_purged == 1
    assert dest_file.exists()
    assert dest_file.read_bytes() == valid_data


def test_integration_destination_corruption_with_move_mode(tmp_path: Path):
    # Setup source file in staging
    staging_file = tmp_path / "staging" / "Interstellar.2014.1080p.mkv"
    staging_file.parent.mkdir(parents=True)
    valid_data = b"INTERSTELLAR_VALID_DATA" * 50
    staging_file.write_bytes(valid_data)

    # Setup corrupt file at destination library (same size, wrong content)
    dest_file = tmp_path / "library" / "Movies" / "Interstellar (2014)" / "Interstellar (2014).mkv"
    dest_file.parent.mkdir(parents=True)
    dest_file.write_bytes(b"X" * len(valid_data))

    plan = OperationPlan(
        op_type=OperationType.ORGANIZE,
        source_path=staging_file,
        destination_path=dest_file,
        transfer_mode=TransferMode.MOVE,
        reason="Organize Interstellar",
    )

    verifier = TransferVerifier()
    organizer = LibraryOrganizerOutput(verifier=verifier)

    result = organizer.execute(plan)

    # Verification
    assert result.status == OperationStatus.SUCCESS
    assert verifier.summary.items_purged == 1
    assert dest_file.exists()
    assert dest_file.read_bytes() == valid_data
    assert not staging_file.exists()  # In MOVE mode, source is removed after successful transfer
