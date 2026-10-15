from pathlib import Path

from media_cron.recovery.models import VerificationStatus
from media_cron.recovery.verifier import TransferVerifier


def test_corrupt_staging_size_mismatch_detected(tmp_path: Path):
    verifier = TransferVerifier()
    src = tmp_path / "src" / "movie.mkv"
    src.parent.mkdir()
    src.write_bytes(b"X" * 1000)

    target = tmp_path / "staging" / "movie.mkv"
    target.parent.mkdir()
    target.write_bytes(b"X" * 200)  # Truncated write

    res = verifier.verify_item(src, target)
    assert res.overall_status == VerificationStatus.SIZE_MISMATCH
    assert res.can_resume is False
    assert res.file_records[0].target_hash is None  # Fast rejection skipped hash


def test_corrupt_staging_hash_mismatch_detected(tmp_path: Path):
    verifier = TransferVerifier()
    src = tmp_path / "src" / "movie.mkv"
    src.parent.mkdir()
    src.write_bytes(b"X" * 1000)

    target = tmp_path / "staging" / "movie.mkv"
    target.parent.mkdir()
    target.write_bytes(b"Y" * 1000)  # Bitrot or different content

    res = verifier.verify_item(src, target)
    assert res.overall_status == VerificationStatus.HASH_MISMATCH
    assert res.can_resume is False
    assert res.file_records[0].source_hash != res.file_records[0].target_hash


def test_corrupt_staging_multi_file_partial_failure(tmp_path: Path):
    verifier = TransferVerifier()
    src_dir = tmp_path / "src" / "Release"
    src_dir.mkdir(parents=True)
    (src_dir / "file1.bin").write_bytes(b"valid1")
    (src_dir / "file2.bin").write_bytes(b"valid2")

    target_dir = tmp_path / "staging" / "Release"
    target_dir.mkdir(parents=True)
    (target_dir / "file1.bin").write_bytes(b"valid1")
    (target_dir / "file2.bin").write_bytes(b"corru2")  # Same size (6 bytes), different content

    res = verifier.verify_item(src_dir, target_dir)
    assert res.overall_status == VerificationStatus.HASH_MISMATCH
    assert res.can_resume is False
