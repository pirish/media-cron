from pathlib import Path

import pytest

from media_cron.recovery.verifier import TransferVerifier


def test_purge_item_file(tmp_path: Path):
    verifier = TransferVerifier()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    corrupt_file = staging_dir / "corrupt.mkv"
    corrupt_file.write_text("corrupted")

    deleted = verifier.purge_item(corrupt_file, allowed_parent_roots=[staging_dir], dry_run=False)
    assert deleted is True
    assert not corrupt_file.exists()


def test_purge_item_directory(tmp_path: Path):
    verifier = TransferVerifier()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    corrupt_dir = staging_dir / "Album"
    corrupt_dir.mkdir()
    (corrupt_dir / "track1.flac").write_text("partial")

    deleted = verifier.purge_item(corrupt_dir, allowed_parent_roots=[staging_dir], dry_run=False)
    assert deleted is True
    assert not corrupt_dir.exists()


def test_purge_item_dry_run_non_destructive(tmp_path: Path):
    verifier = TransferVerifier()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    corrupt_file = staging_dir / "corrupt.mkv"
    corrupt_file.write_text("corrupted")

    deleted = verifier.purge_item(corrupt_file, allowed_parent_roots=[staging_dir], dry_run=True)
    assert deleted is True
    assert corrupt_file.exists()  # Not deleted in dry-run


def test_purge_item_disallows_path_outside_allowed_roots(tmp_path: Path):
    verifier = TransferVerifier()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    external_dir = tmp_path / "system"
    external_dir.mkdir()
    external_file = external_dir / "important.txt"
    external_file.write_text("critical")

    with pytest.raises(ValueError, match="violates boundary containment"):
        verifier.purge_item(external_file, allowed_parent_roots=[staging_dir], dry_run=False)

    assert external_file.exists()


def test_purge_item_disallows_root_or_parent_deletion(tmp_path: Path):
    verifier = TransferVerifier()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()

    with pytest.raises(ValueError, match="Cannot purge an allowed parent root itself"):
        verifier.purge_item(staging_dir, allowed_parent_roots=[staging_dir], dry_run=False)

    with pytest.raises(ValueError, match="Cannot purge root directory"):
        verifier.purge_item(Path("/"), allowed_parent_roots=[Path("/")], dry_run=False)
