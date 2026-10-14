import json
import logging
import sys

from media_cron.logging.formatter import JsonLogFormatter


def test_json_formatter_schema_compliance():
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="media_cron.pipeline",
        level=logging.INFO,
        pathname="pipeline.py",
        lineno=100,
        msg="Organized %d tracks",
        args=(12,),
        exc_info=None,
    )
    # Add structured context
    record.context = {"media_type": "music", "artist": "ArtistName"}

    serialized = formatter.format(record)
    data = json.loads(serialized)

    assert "timestamp" in data
    assert data["level"] == "INFO"
    assert data["logger"] == "media_cron.pipeline"
    assert data["message"] == "Organized 12 tracks"
    assert data["context"] == {"media_type": "music", "artist": "ArtistName"}
    assert data["exception"] is None


def test_json_formatter_with_exception():
    formatter = JsonLogFormatter()
    try:
        raise RuntimeError("Failure in provider cascade")
    except RuntimeError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="media_cron.provider",
        level=logging.ERROR,
        pathname="provider.py",
        lineno=55,
        msg="Provider error",
        args=(),
        exc_info=exc_info,
    )

    serialized = formatter.format(record)
    data = json.loads(serialized)

    assert data["level"] == "ERROR"
    assert data["exception"] is not None
    assert "Traceback" in data["exception"]
    assert "RuntimeError: Failure in provider cascade" in data["exception"]
