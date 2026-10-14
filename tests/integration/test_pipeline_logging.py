import io
import logging
import sys
from pathlib import Path

from media_cron.config import MediaCronConfig, PathsConfig
from media_cron.logging.engine import engine
from media_cron.logging.models import LogDestination, LoggingConfig, LogLevel
from media_cron.pipeline import Pipeline


def test_pipeline_lifecycle_logging_records(tmp_path: Path, monkeypatch):
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()

    # Create dummy music file
    test_file = src / "test_track.mp3"
    test_file.write_bytes(b"ID3\x03\x00\x00\x00" + b"\x00" * 100)

    cfg = MediaCronConfig(
        paths=PathsConfig(source_dir=src, destination_dir=dest),
        logging=LoggingConfig(level=LogLevel.INFO, destination=LogDestination.CONSOLE),
    )
    cfg.general.dry_run = True

    engine.setup(cfg.logging)
    pipeline = Pipeline(config=cfg)
    summary = pipeline.run()
    assert summary.exit_code == 0

    logs = fake_stderr.getvalue()
    # 1. Initialization logged
    assert "Initializing media organization pipeline" in logs
    # 2. Ingestion scan logged
    assert "Ingestion scan completed" in logs
    # 3. Dry-run operations logged
    assert "[DRY-RUN]" in logs or "Planned" in logs or "test_track.mp3" in logs

    engine.reset()


def test_error_diagnostic_clean_without_stacktrace_at_info(monkeypatch):
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    engine.setup(LoggingConfig(level=LogLevel.INFO, destination=LogDestination.CONSOLE))
    logger = logging.getLogger("media_cron.pipeline")

    try:
        raise RuntimeError("Sample internal failure")
    except RuntimeError as e:
        if engine.get_effective_config().level == LogLevel.DEBUG:
            logger.error("Processing failure: %s", e, exc_info=True)
        else:
            logger.error("Processing failure: %s", e)

    output = fake_stderr.getvalue()
    assert "[ERROR]" in output
    assert "Processing failure: Sample internal failure" in output
    # Stacktrace lines should be suppressed at INFO level
    assert "Traceback (most recent call last)" not in output
    engine.reset()


def test_error_stacktrace_present_at_debug(monkeypatch):
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    engine.setup(LoggingConfig(level=LogLevel.DEBUG, destination=LogDestination.CONSOLE))
    logger = logging.getLogger("media_cron.pipeline")

    try:
        raise RuntimeError("Sample internal failure")
    except RuntimeError as e:
        if engine.get_effective_config().level == LogLevel.DEBUG:
            logger.error("Processing failure: %s", e, exc_info=True)
        else:
            logger.error("Processing failure: %s", e)

    output = fake_stderr.getvalue()
    assert "[ERROR]" in output
    assert "Traceback (most recent call last)" in output
    assert "RuntimeError: Sample internal failure" in output
    engine.reset()
