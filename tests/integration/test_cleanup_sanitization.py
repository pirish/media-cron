from pathlib import Path

# Import plugins
import media_cron.plugins.input.directory  # noqa: F401
import media_cron.plugins.lookup.video  # noqa: F401
import media_cron.plugins.output.cleaner  # noqa: F401
from media_cron.config import MediaCronConfig
from media_cron.pipeline import Pipeline


def test_cleanup_and_subtitle_preservation(tmp_path: Path):
    source = tmp_path / "source"
    subfolder = source / "Movie.Release.2024"
    staging = tmp_path / "staging"
    destination = tmp_path / "destination"

    subfolder.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)

    # Populate source files
    video = subfolder / "Movie.Release.2024.1080p.mkv"
    video.write_bytes(b"\x1a\x45\xdf\xa3" + b"video data" * 1000)

    sub = subfolder / "Movie.Release.2024.1080p.en.srt"
    sub.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello")

    junk = subfolder / "release.nfo"
    junk.write_text("nfo file")

    sample = subfolder / "sample.mp4"
    sample.write_bytes(b"small sample" * 10)

    # Run pipeline in live mode
    cfg = MediaCronConfig()
    cfg.paths.source_dir = source
    cfg.paths.staging_dir = staging
    cfg.paths.destination_dir = destination
    cfg.general.dry_run = False

    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()

    assert summary.exit_code == 0
    assert summary.junk_purged_count >= 2

    # Junk files should NOT exist in staging or destination
    assert not (staging / "release.nfo").exists()
    assert not (staging / "sample.mp4").exists()
