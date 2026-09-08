from pathlib import Path

# Plugins
import media_cron.plugins.input.directory  # noqa: F401
import media_cron.plugins.lookup.video  # noqa: F401
import media_cron.plugins.output.organizer  # noqa: F401
import media_cron.plugins.output.seed  # noqa: F401
from media_cron.config import MediaCronConfig
from media_cron.pipeline import Pipeline


def test_staging_and_seeding_integration(tmp_path: Path):
    source = tmp_path / "source"
    staging = tmp_path / "staging"
    destination = tmp_path / "destination"
    seed = tmp_path / "seed"

    source.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    seed.mkdir(parents=True, exist_ok=True)

    movie = source / "The.Dark.Knight.2008.1080p.mkv"
    movie.write_bytes(b"\x1a\x45\xdf\xa3" + b"dark knight" * 100)

    cfg = MediaCronConfig()
    cfg.paths.source_dir = source
    cfg.paths.staging_dir = staging
    cfg.paths.destination_dir = destination
    cfg.paths.seed_dir = seed
    cfg.general.mode = "hardlink"
    cfg.general.dry_run = False

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    assert summary.exit_code == 0
    assert summary.processed_count == 1

    # Check organized file in destination
    expected_dest = destination / "Movies" / "The Dark Knight (2008)" / "The Dark Knight (2008).mkv"
    assert expected_dest.exists()

    # Check seed directory contains original filename
    expected_seed = seed / "The.Dark.Knight.2008.1080p.mkv"
    assert expected_seed.exists()

    # Inode matches between destination and seed (hardlink)
    assert expected_dest.stat().st_ino == expected_seed.stat().st_ino
