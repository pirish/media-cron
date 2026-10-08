from pathlib import Path

from media_cron.config import MediaCronConfig, PathsConfig
from media_cron.pipeline import Pipeline


def test_legacy_global_configuration_backward_compatibility(tmp_path: Path):
    """Verifies that setups with only global source_dir and destination_dir continue to work unmodified."""
    source_dir = tmp_path / "legacy_source"
    staging_dir = tmp_path / "legacy_staging"
    dest_dir = tmp_path / "legacy_destination"

    source_dir.mkdir()
    staging_dir.mkdir()
    dest_dir.mkdir()

    # Create dummy files for music and book
    music_file = source_dir / "Artist - Album - 01 - Song.flac"
    music_file.write_bytes(b"fLaC" + b"\x00" * 50)

    book_file = source_dir / "Author - Book Title.epub"
    book_file.write_bytes(b"PK\x03\x04" + b"\x00" * 50)

    # Pure legacy configuration: NO media-specific routes configured
    cfg = MediaCronConfig(
        paths=PathsConfig(
            source_dir=source_dir,
            staging_dir=staging_dir,
            destination_dir=dest_dir,
        )
    )
    cfg.general.mode = "copy"
    cfg.music.enabled = True
    cfg.books.enabled = True

    pipeline = Pipeline(cfg)
    summary = pipeline.run()

    assert summary.exit_code == 0
    assert summary.processed_count >= 2

    # Files arrive in global destination_dir under their respective category folders
    flac_dest = list(dest_dir.rglob("*.flac"))
    assert len(flac_dest) == 1
    assert flac_dest[0].is_relative_to(dest_dir)

    epub_dest = list(dest_dir.rglob("*.epub"))
    assert len(epub_dest) == 1
    assert epub_dest[0].is_relative_to(dest_dir)

    # Telemetry includes routing_summary
    assert hasattr(summary, "routing_summary")
    assert "music" in summary.routing_summary
    assert "books" in summary.routing_summary
