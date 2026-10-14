import io
import logging
import sys
from pathlib import Path

import pytest

from media_cron.logging.engine import LoggingEngine
from media_cron.logging.models import LogDestination, LoggingConfig


def test_file_mode_silences_console(tmp_path: Path, monkeypatch):
    engine = LoggingEngine()
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    log_file = tmp_path / "silent_console.log"
    config = LoggingConfig(
        destination=LogDestination.FILE,
        file_path=log_file,
    )
    engine.setup(config)

    logger = logging.getLogger("media_cron.silence_test")
    logger.info("Message for file only")

    engine.reset()

    # Console stderr must be empty (silenced)
    assert fake_stderr.getvalue() == ""
    # File must contain the record
    assert "Message for file only" in log_file.read_text()


def test_both_mode_emits_to_both(tmp_path: Path, monkeypatch):
    engine = LoggingEngine()
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    log_file = tmp_path / "both.log"
    config = LoggingConfig(
        destination=LogDestination.BOTH,
        file_path=log_file,
    )
    engine.setup(config)

    logger = logging.getLogger("media_cron.both_test")
    logger.info("Dual emission message")

    engine.reset()

    # Both must contain the message
    assert "Dual emission message" in fake_stderr.getvalue()
    assert "Dual emission message" in log_file.read_text()


def test_unwritable_destination_fails_fast(tmp_path: Path):
    engine = LoggingEngine()
    # Directory that cannot be written or created (e.g. file acting as directory)
    blocking_file = tmp_path / "blocking_file"
    blocking_file.write_text("block")
    invalid_log = blocking_file / "uncreatable" / "app.log"

    config = LoggingConfig(
        destination=LogDestination.FILE,
        file_path=invalid_log,
    )
    with pytest.raises(ValueError, match="Failed to initialize log file destination"):
        engine.setup(config)
    engine.reset()
