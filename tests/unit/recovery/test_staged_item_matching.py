from pathlib import Path

from media_cron.recovery.models import VerificationStatus
from media_cron.recovery.verifier import TransferVerifier


def test_verify_directory_match(tmp_path: Path):
    verifier = TransferVerifier()
    src = tmp_path / "src" / "Album"
    src.mkdir(parents=True)
    (src / "track1.flac").write_bytes(b"Track 1 Content")
    (src / "track2.flac").write_bytes(b"Track 2 Content")

    target = tmp_path / "staging" / "Album"
    target.mkdir(parents=True)
    (target / "track1.flac").write_bytes(b"Track 1 Content")
    (target / "track2.flac").write_bytes(b"Track 2 Content")

    res = verifier.verify_item(src, target)
    assert res.overall_status == VerificationStatus.MATCH
    assert res.can_resume is True
    assert res.bytes_saved == len(b"Track 1 Content") + len(b"Track 2 Content")
    assert len(res.file_records) == 2


def test_verify_directory_missing_file_causes_mismatch(tmp_path: Path):
    verifier = TransferVerifier()
    src = tmp_path / "src" / "Album"
    src.mkdir(parents=True)
    (src / "track1.flac").write_bytes(b"Track 1 Content")
    (src / "track2.flac").write_bytes(b"Track 2 Content")

    target = tmp_path / "staging" / "Album"
    target.mkdir(parents=True)
    (target / "track1.flac").write_bytes(b"Track 1 Content")
    # track2 is missing in staging

    res = verifier.verify_item(src, target)
    assert res.overall_status in (VerificationStatus.SIZE_MISMATCH, VerificationStatus.MISSING)
    assert res.can_resume is False
    assert res.bytes_saved == 0


def test_verify_directory_extra_file_causes_mismatch(tmp_path: Path):
    verifier = TransferVerifier()
    src = tmp_path / "src" / "Album"
    src.mkdir(parents=True)
    (src / "track1.flac").write_bytes(b"Track 1 Content")

    target = tmp_path / "staging" / "Album"
    target.mkdir(parents=True)
    (target / "track1.flac").write_bytes(b"Track 1 Content")
    (target / "extra.flac").write_bytes(b"Leftover file")

    res = verifier.verify_item(src, target)
    assert res.can_resume is False
    assert res.bytes_saved == 0
