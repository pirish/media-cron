import io
import logging
import sys

from media_cron.logging.engine import LoggingEngine
from media_cron.logging.formatter import StandardTextFormatter
from media_cron.logging.models import LogDestination, LoggingConfig, LogLevel


def test_standard_text_formatter_formatting():
    formatter = StandardTextFormatter()
    record = logging.LogRecord(
        name="media_cron.test",
        level=logging.WARNING,
        pathname="test.py",
        lineno=10,
        msg="Disk space low: %d%%",
        args=(95,),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "[WARNING]" in formatted
    assert "media_cron.test:" in formatted
    assert "Disk space low: 95%" in formatted


def test_standard_text_formatter_with_exception():
    formatter = StandardTextFormatter()
    try:
        raise ValueError("Simulated failure")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="media_cron.error",
        level=logging.ERROR,
        pathname="error.py",
        lineno=99,
        msg="Unhandled exception occurred",
        args=(),
        exc_info=exc_info,
    )
    formatted = formatter.format(record)
    assert "[ERROR]" in formatted
    assert "Unhandled exception occurred" in formatted
    assert "ValueError: Simulated failure" in formatted


def test_console_handler_targets_stderr(monkeypatch):
    engine = LoggingEngine()
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    config = LoggingConfig(
        level=LogLevel.INFO,
        destination=LogDestination.CONSOLE,
    )
    engine.setup(config)

    logger = logging.getLogger("media_cron.unit")
    logger.info("Test console message to stderr")

    output = fake_stderr.getvalue()
    assert "[INFO]" in output
    assert "media_cron.unit:" in output
    assert "Test console message to stderr" in output

    engine.reset()
