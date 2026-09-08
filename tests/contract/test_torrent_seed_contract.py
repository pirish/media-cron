from pathlib import Path
from unittest.mock import MagicMock

from media_cron.models import (
    OperationPlan,
    OperationStatus,
    OperationType,
    TransferMode,
)
from media_cron.plugins.base import OutputPlugin
from media_cron.plugins.output.torrent_seed import TorrentClientSeedOutput
from media_cron.torrent.base import TorrentClientProtocol


def test_torrent_seed_output_satisfies_protocol():
    plugin = TorrentClientSeedOutput()
    assert isinstance(plugin, OutputPlugin)
    assert plugin.plugin_name == "torrent_seed"


def test_torrent_seed_output_relocate_dry_run():
    mock_client = MagicMock(spec=TorrentClientProtocol)
    plugin = TorrentClientSeedOutput(client=mock_client)

    plan = OperationPlan(
        op_type=OperationType.TORRENT_RELOCATE,
        transfer_mode=TransferMode.MOVE,
        source_path=Path("abcdef1234567890abcdef1234567890abcdef12"),
        destination_path=Path("/data/seeding/completed"),
        reason="Relocating client storage",
        dry_run=True,
    )

    res = plugin.execute(plan)
    assert res.status == OperationStatus.SUCCESS
    assert "[DRY-RUN]" in res.message
    mock_client.relocate_storage.assert_not_called()


def test_torrent_seed_output_relocate_success():
    mock_client = MagicMock(spec=TorrentClientProtocol)
    mock_client.relocate_storage.return_value = True
    plugin = TorrentClientSeedOutput(client=mock_client)

    dest = Path("/data/seeding/completed")
    plan = OperationPlan(
        op_type=OperationType.TORRENT_RELOCATE,
        transfer_mode=TransferMode.MOVE,
        source_path=Path("abcdef1234567890abcdef1234567890abcdef12"),
        destination_path=dest,
        reason="Relocating client storage",
        dry_run=False,
    )

    res = plugin.execute(plan)
    assert res.status == OperationStatus.SUCCESS
    assert "Relocated" in res.message
    mock_client.relocate_storage.assert_called_once_with(
        "abcdef1234567890abcdef1234567890abcdef12", dest
    )


def test_torrent_seed_output_relocate_failure():
    mock_client = MagicMock(spec=TorrentClientProtocol)
    mock_client.relocate_storage.return_value = False
    plugin = TorrentClientSeedOutput(client=mock_client)

    dest = Path("/data/seeding/completed")
    plan = OperationPlan(
        op_type=OperationType.TORRENT_RELOCATE,
        transfer_mode=TransferMode.MOVE,
        source_path=Path("abcdef1234567890abcdef1234567890abcdef12"),
        destination_path=dest,
        reason="Relocating client storage",
        dry_run=False,
    )

    res = plugin.execute(plan)
    assert res.status == OperationStatus.FAILED
    assert "Failed to relocate" in res.error


def test_torrent_seed_output_skips_unhandled_op():
    mock_client = MagicMock(spec=TorrentClientProtocol)
    plugin = TorrentClientSeedOutput(client=mock_client)

    plan = OperationPlan(
        op_type=OperationType.ORGANIZE,
        transfer_mode=TransferMode.HARDLINK,
        source_path=Path("/tmp/media.mkv"),
        destination_path=Path("/tmp/dest/media.mkv"),
        reason="Organizing",
    )

    res = plugin.execute(plan)
    assert res.status == OperationStatus.SKIPPED
