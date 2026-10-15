from pathlib import Path

from media_cron.config import GeneralConfig, MediaCronConfig, PathsConfig, PluginsConfig
from media_cron.pipeline import Pipeline
from media_cron.recovery.verifier import TransferVerifier


def test_dry_run_recovery_reporting_non_destructive(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # 1. Matching file in staging (resumable)
    src_match = source_dir / "matched.txt"
    src_match.write_bytes(b"MATCH_CONTENT_12345")
    staged_match = staging_dir / "matched.txt"
    staged_match.write_bytes(b"MATCH_CONTENT_12345")

    # 2. Corrupt file in staging (mismatch)
    src_corrupt = source_dir / "corrupt.txt"
    src_corrupt.write_bytes(b"VALID_CORRUPT_SOURCE")
    staged_corrupt = staging_dir / "corrupt.txt"
    staged_corrupt.write_bytes(b"CORRUPT_STAGED_TRUNCATED")

    config = MediaCronConfig(
        general=GeneralConfig(mode="copy"),
        paths=PathsConfig(source_dir=source_dir, staging_dir=staging_dir, destination_dir=dest_dir),
        plugins=PluginsConfig(input="directory_scanner", outputs=["library_organizer"]),
    )

    verifier = TransferVerifier()
    pipeline = Pipeline(config, verifier=verifier)

    # Execute dry-run
    summary = pipeline.run(dry_run=True)

    # 1. Non-destructive: corrupt file was NOT deleted
    assert staged_corrupt.exists()
    assert staged_match.exists()

    # 2. Recovery telemetry populated in summary
    assert summary.recovery_summary is not None
    assert summary.recovery_summary.items_resumed >= 1
    assert summary.recovery_summary.items_purged >= 1
    assert summary.recovery_summary.bytes_saved >= len(b"MATCH_CONTENT_12345")

    # 3. JSON dictionary contains recovery block
    d = summary.to_dict()
    assert "recovery" in d
    assert d["recovery"]["items_resumed"] >= 1
    assert d["recovery"]["items_purged"] >= 1
