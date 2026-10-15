from pathlib import Path
from unittest.mock import MagicMock

from media_cron.models import OperationPlan, OperationStatus, OperationType, TransferMode
from media_cron.plugins.output.organizer import LibraryOrganizerOutput
from media_cron.plugins.output.torrent_seed import TorrentClientSeedOutput
from media_cron.recovery.verifier import TransferVerifier
from media_cron.torrent.models import TorrentSeedingConfig


def test_destination_bypass_allows_post_transfer_seeding_relocation(tmp_path: Path):
    src = tmp_path / "staging" / "Movie.2026.mkv"
    src.parent.mkdir()
    src.write_bytes(b"Movie Bytes" * 100)

    dest = tmp_path / "dest" / "Movie (2026)" / "Movie (2026).mkv"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"Movie Bytes" * 100)

    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()

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

    # 1. Transfer is marked SKIPPED (bypassed)
    assert res.status == OperationStatus.SKIPPED
    assert "bypassed" in res.message
    assert verifier.summary.transfers_bypassed == 1

    # 2. Downstream post-transfer seeding relocation executes
    mock_client = MagicMock()
    mock_client.relocate_storage.return_value = True
    seeding_config = TorrentSeedingConfig(mode="client_relocate", target_location="seed_dir")
    seed_output = TorrentClientSeedOutput(client=mock_client, seeding_config=seeding_config)

    relocate_plan = OperationPlan(
        op_type=OperationType.TORRENT_RELOCATE,
        source_path=Path("mock_hash_1234"),
        destination_path=seed_dir,
        transfer_mode=TransferMode.MOVE,
        reason=f"Client storage relocated to {seed_dir}",
    )
    rel_res = seed_output.execute(relocate_plan)
    assert rel_res.status == OperationStatus.SUCCESS
    mock_client.relocate_storage.assert_called_once_with("mock_hash_1234", seed_dir)


def test_destination_bypass_move_cleans_up_source(tmp_path: Path):
    src = tmp_path / "staging" / "Track.mp3"
    src.parent.mkdir()
    src.write_bytes(b"Audio content data")

    dest = tmp_path / "dest" / "Music" / "Artist" / "Track.mp3"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"Audio content data")

    plan = OperationPlan(
        op_type=OperationType.ORGANIZE,
        source_path=src,
        destination_path=dest,
        transfer_mode=TransferMode.MOVE,
        reason="Organize Track",
    )

    verifier = TransferVerifier()
    organizer = LibraryOrganizerOutput(verifier=verifier)
    res = organizer.execute(plan)

    assert res.status == OperationStatus.SKIPPED
    assert verifier.summary.transfers_bypassed == 1
    # Since transfer was MOVE and dest is satisfied, src must be cleaned up
    assert not src.exists()
    assert dest.exists()
