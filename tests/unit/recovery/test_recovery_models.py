from pathlib import Path

from media_cron.recovery.models import (
    FileIntegrityRecord,
    RecoverySummary,
    VerificationResult,
    VerificationStatus,
)


def test_verification_status_values():
    assert VerificationStatus.MATCH == "match"
    assert VerificationStatus.SIZE_MISMATCH == "size_mismatch"
    assert VerificationStatus.HASH_MISMATCH == "hash_mismatch"
    assert VerificationStatus.MISSING == "missing"
    assert VerificationStatus.CORRUPTED == "corrupted"


def test_file_integrity_record_creation():
    rec = FileIntegrityRecord(
        relative_path=Path("sample.mkv"),
        source_path=Path("/data/src/sample.mkv"),
        target_path=Path("/data/staging/sample.mkv"),
        source_size=1024,
        target_size=1024,
        source_hash="abcd1234",
        target_hash="abcd1234",
        status=VerificationStatus.MATCH,
        is_same_inode=False,
    )
    assert rec.status == VerificationStatus.MATCH
    assert rec.source_size == 1024
    assert not rec.is_same_inode


def test_verification_result_post_init_logic():
    res_match = VerificationResult(
        item_name="TestRelease",
        source_root=Path("/data/src/TestRelease"),
        target_root=Path("/data/staging/TestRelease"),
        is_directory=True,
        overall_status=VerificationStatus.MATCH,
        total_source_bytes=5000,
    )
    assert res_match.can_resume is True
    assert res_match.bytes_saved == 5000

    res_mismatch = VerificationResult(
        item_name="BadRelease",
        source_root=Path("/data/src/BadRelease"),
        target_root=Path("/data/staging/BadRelease"),
        is_directory=False,
        overall_status=VerificationStatus.SIZE_MISMATCH,
        total_source_bytes=5000,
    )
    assert res_mismatch.can_resume is False
    assert res_mismatch.bytes_saved == 0


def test_recovery_summary_metrics():
    summary = RecoverySummary()
    summary.items_scanned += 5
    summary.items_resumed += 2
    summary.transfers_bypassed += 1
    summary.items_purged += 1
    summary.bytes_saved += 10485760
    summary.purge_errors += 0

    d = summary.to_dict()
    assert d["items_scanned"] == 5
    assert d["items_resumed"] == 2
    assert d["transfers_bypassed"] == 1
    assert d["items_purged"] == 1
    assert d["bytes_saved"] == 10485760
    assert d["purge_errors"] == 0
