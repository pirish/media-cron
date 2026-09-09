from pathlib import Path

from media_cron.metadata.converter import apply_retention_policy
from media_cron.metadata.models import RetentionPolicy


def test_retention_preserve(tmp_path: Path):
    src = tmp_path / "book.mobi"
    src.write_bytes(b"original mobi")
    target = tmp_path / "book.epub"
    target.write_bytes(b"converted epub")

    apply_retention_policy(src, target, RetentionPolicy.PRESERVE)
    assert src.exists()
    assert target.exists()


def test_retention_archive(tmp_path: Path):
    src = tmp_path / "book.mobi"
    src.write_bytes(b"original mobi")
    target = tmp_path / "book.epub"
    target.write_bytes(b"converted epub")
    archive_dir = tmp_path / "archive"

    apply_retention_policy(src, target, RetentionPolicy.ARCHIVE, archive_dir=archive_dir)
    assert not src.exists()
    assert (archive_dir / "book.mobi").exists()
    assert (archive_dir / "book.mobi").read_bytes() == b"original mobi"
    assert target.exists()


def test_retention_replace(tmp_path: Path):
    src = tmp_path / "book.mobi"
    src.write_bytes(b"original mobi")
    target = tmp_path / "book.epub"
    target.write_bytes(b"converted epub")

    apply_retention_policy(src, target, RetentionPolicy.REPLACE)
    assert not src.exists()
    assert target.exists()


def test_retention_failure_safety_missing_target(tmp_path: Path):
    src = tmp_path / "book.mobi"
    src.write_bytes(b"original mobi")
    missing_target = tmp_path / "missing.epub"

    # With replace policy, if target is missing, source must NEVER be deleted
    apply_retention_policy(src, missing_target, RetentionPolicy.REPLACE)
    assert src.exists()

    # With archive policy, if target is missing, source must NEVER be moved
    archive_dir = tmp_path / "archive"
    apply_retention_policy(src, missing_target, RetentionPolicy.ARCHIVE, archive_dir=archive_dir)
    assert src.exists()
    assert not (archive_dir / "book.mobi").exists()


def test_retention_failure_safety_empty_target(tmp_path: Path):
    src = tmp_path / "book.mobi"
    src.write_bytes(b"original mobi")
    empty_target = tmp_path / "empty.epub"
    empty_target.write_bytes(b"")

    apply_retention_policy(src, empty_target, RetentionPolicy.REPLACE)
    assert src.exists()
