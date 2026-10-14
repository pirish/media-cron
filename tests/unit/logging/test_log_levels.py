import io
import logging
import sys

from media_cron.logging.engine import LoggingEngine
from media_cron.logging.models import LoggingConfig, LogLevel


def test_debug_log_level_emission(monkeypatch):
    engine = LoggingEngine()
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    engine.setup(LoggingConfig(level=LogLevel.DEBUG))
    logger = logging.getLogger("media_cron.debug_test")

    logger.debug("Granular debug diagnostic")
    logger.info("Routine info notification")

    output = fake_stderr.getvalue()
    assert "[DEBUG]" in output
    assert "Granular debug diagnostic" in output
    assert "[INFO]" in output
    assert "Routine info notification" in output
    engine.reset()


def test_warning_log_level_suppression(monkeypatch):
    engine = LoggingEngine()
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    engine.setup(LoggingConfig(level=LogLevel.WARNING))
    logger = logging.getLogger("media_cron.warn_test")

    logger.debug("Should be suppressed")
    logger.info("Should also be suppressed")
    logger.warning("Actual warning emitted")

    output = fake_stderr.getvalue()
    assert "Should be suppressed" not in output
    assert "Should also be suppressed" not in output
    assert "[WARNING]" in output
    assert "Actual warning emitted" in output
    engine.reset()


def test_error_log_level_suppression(monkeypatch):
    engine = LoggingEngine()
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    engine.setup(LoggingConfig(level=LogLevel.ERROR))
    logger = logging.getLogger("media_cron.err_test")

    logger.info("Suppressed info")
    logger.warning("Suppressed warning")
    logger.error("Critical error emitted")

    output = fake_stderr.getvalue()
    assert "Suppressed info" not in output
    assert "Suppressed warning" not in output
    assert "[ERROR]" in output
    assert "Critical error emitted" in output
    engine.reset()
