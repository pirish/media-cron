from pathlib import Path

from media_cron.models import (
    OperationPlan,
    OperationStatus,
    OperationType,
    TransferMode,
)
from media_cron.plugins.output.cleaner import JunkCleanerOutput


def test_junk_cleaner_purges_junk_file(tmp_path: Path):
    cleaner = JunkCleanerOutput()
    junk_file = tmp_path / "movie.nfo"
    junk_file.write_text("info")

    plan = OperationPlan(
        op_type=OperationType.PURGE_JUNK,
        transfer_mode=TransferMode.MOVE,
        source_path=junk_file,
        reason="NFO junk",
        dry_run=False,
    )
    result = cleaner.execute(plan)
    assert result.status == OperationStatus.SUCCESS
    assert not junk_file.exists()


def test_junk_cleaner_purges_sample_video(tmp_path: Path):
    cleaner = JunkCleanerOutput()
    sample_file = tmp_path / "sample.mkv"
    sample_file.write_bytes(b"small video" * 100)

    plan = OperationPlan(
        op_type=OperationType.PURGE_SAMPLE,
        transfer_mode=TransferMode.MOVE,
        source_path=sample_file,
        reason="Sample under threshold",
        dry_run=False,
    )
    result = cleaner.execute(plan)
    assert result.status == OperationStatus.SUCCESS
    assert not sample_file.exists()


def test_junk_cleaner_dry_run_preserves_files(tmp_path: Path):
    cleaner = JunkCleanerOutput()
    junk_file = tmp_path / "movie.url"
    junk_file.write_text("url")

    plan = OperationPlan(
        op_type=OperationType.PURGE_JUNK,
        transfer_mode=TransferMode.MOVE,
        source_path=junk_file,
        reason="URL shortcut",
        dry_run=True,
    )
    result = cleaner.execute(plan)
    assert result.status == OperationStatus.SUCCESS
    assert junk_file.exists()
