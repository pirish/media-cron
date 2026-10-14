import logging

from media_cron.logging.base import LogFormatterProtocol
from media_cron.logging.formatter import StandardTextFormatter


def test_standard_text_formatter_implements_protocol():
    formatter = StandardTextFormatter()
    assert isinstance(formatter, LogFormatterProtocol)


def test_standard_text_formatter_output():
    formatter = StandardTextFormatter()
    record = logging.LogRecord(
        name="media_cron.pipeline",
        level=logging.INFO,
        pathname="pipeline.py",
        lineno=42,
        msg="Processing batch %d",
        args=(101,),
        exc_info=None,
    )
    output = formatter.format(record)
    assert "[INFO]" in output
    assert "media_cron.pipeline" in output
    assert "Processing batch 101" in output
