from pathlib import Path

from media_cron.logging.base import LoggingEngineProtocol
from media_cron.logging.engine import LoggingEngine
from media_cron.logging.models import LogDestination, LogFormat, LoggingConfig, LogLevel


def test_logging_engine_implements_protocol():
    engine = LoggingEngine()
    assert isinstance(engine, LoggingEngineProtocol)


def test_logging_engine_lifecycle(tmp_path: Path):
    engine = LoggingEngine()
    log_file = tmp_path / "test.log"
    config = LoggingConfig(
        level=LogLevel.DEBUG,
        destination=LogDestination.FILE,
        file_path=log_file,
        format=LogFormat.TEXT,
    )

    engine.setup(config)
    effective = engine.get_effective_config()
    assert effective.level == LogLevel.DEBUG
    assert effective.destination == LogDestination.FILE
    assert effective.file_path == log_file

    engine.reset()
    default_cfg = engine.get_effective_config()
    assert default_cfg.level == LogLevel.INFO
    assert default_cfg.destination == LogDestination.CONSOLE
