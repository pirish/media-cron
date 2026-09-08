from pathlib import Path

# Plugins
import media_cron.plugins.input.directory  # noqa: F401
import media_cron.plugins.lookup.video  # noqa: F401
import media_cron.plugins.output.organizer  # noqa: F401
from media_cron.config import MediaCronConfig
from media_cron.pipeline import Pipeline


def test_corrupted_file_halts_organization(tmp_path: Path):
    source = tmp_path / "source"
    staging = tmp_path / "staging"
    destination = tmp_path / "destination"

    source.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)

    # Place a corrupt video file in source
    corrupt_movie = source / "Corrupt.Movie.2024.1080p.mkv"
    corrupt_movie.write_bytes(b"bad header truncated container data")

    cfg = MediaCronConfig()
    cfg.paths.source_dir = source
    cfg.paths.staging_dir = staging
    cfg.paths.destination_dir = destination
    cfg.general.dry_run = False

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    # Exit code should reflect partial / error due to corrupt item
    assert summary.exit_code != 0
    assert summary.error_count >= 1
    assert any("integrity" in err.lower() or "invalid" in err.lower() for err in summary.errors)

    # Ensure corrupt file was NOT transferred to destination library
    assert not any(destination.rglob("*.mkv"))
