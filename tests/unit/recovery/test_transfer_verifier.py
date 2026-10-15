import os
from pathlib import Path

from media_cron.recovery.models import VerificationStatus
from media_cron.recovery.verifier import TransferVerifier


def test_compute_sha256(tmp_path: Path):
    verifier = TransferVerifier()
    file_a = tmp_path / "file_a.txt"
    file_a.write_text("Hello Media Cron Recovery!")

    import hashlib

    expected_hash = hashlib.sha256(b"Hello Media Cron Recovery!").hexdigest()

    assert verifier.compute_sha256(file_a) == expected_hash


def test_verify_single_file_match(tmp_path: Path):
    verifier = TransferVerifier()
    src = tmp_path / "src" / "video.mkv"
    src.parent.mkdir()
    src.write_bytes(b"content" * 100)

    target = tmp_path / "staging" / "video.mkv"
    target.parent.mkdir()
    target.write_bytes(b"content" * 100)

    res = verifier.verify_item(src, target)
    assert res.overall_status == VerificationStatus.MATCH
    assert res.can_resume is True
    assert res.bytes_saved == len(b"content" * 100)
    assert len(res.file_records) == 1
    assert res.file_records[0].source_hash == res.file_records[0].target_hash


def test_verify_single_file_size_mismatch_fast_rejection(tmp_path: Path):
    verifier = TransferVerifier()
    src = tmp_path / "src" / "video.mkv"
    src.parent.mkdir()
    src.write_bytes(b"A" * 1000)

    target = tmp_path / "staging" / "video.mkv"
    target.parent.mkdir()
    target.write_bytes(b"A" * 500)  # Truncated

    res = verifier.verify_item(src, target)
    assert res.overall_status == VerificationStatus.SIZE_MISMATCH
    assert res.can_resume is False
    assert res.bytes_saved == 0
    # On size mismatch, target_hash should be None (no full file hashing wasted)
    assert res.file_records[0].target_hash is None


def test_verify_single_file_hash_mismatch(tmp_path: Path):
    verifier = TransferVerifier()
    src = tmp_path / "src" / "video.mkv"
    src.parent.mkdir()
    src.write_bytes(b"A" * 1000)

    target = tmp_path / "staging" / "video.mkv"
    target.parent.mkdir()
    target.write_bytes(b"B" * 1000)  # Same size, different content

    res = verifier.verify_item(src, target)
    assert res.overall_status == VerificationStatus.HASH_MISMATCH
    assert res.can_resume is False
    assert res.bytes_saved == 0
    assert res.file_records[0].source_hash != res.file_records[0].target_hash


def test_verify_single_file_missing_target(tmp_path: Path):
    verifier = TransferVerifier()
    src = tmp_path / "src" / "video.mkv"
    src.parent.mkdir()
    src.write_bytes(b"A" * 1000)

    target = tmp_path / "staging" / "video.mkv"
    res = verifier.verify_item(src, target)
    assert res.overall_status == VerificationStatus.MISSING
    assert res.can_resume is False


def test_verify_same_inode_hardlink(tmp_path: Path):
    verifier = TransferVerifier()
    src = tmp_path / "src" / "video.mkv"
    src.parent.mkdir()
    src.write_bytes(b"A" * 1000)

    target = tmp_path / "staging" / "video.mkv"
    target.parent.mkdir()
    os.link(src, target)

    res = verifier.verify_item(src, target)
    assert res.overall_status == VerificationStatus.MATCH
    assert res.can_resume is True
    assert res.file_records[0].is_same_inode is True
    # Inode match bypasses hashing
    assert res.file_records[0].source_hash is None
