import logging

from media_cron.logging.engine import LoggingEngine, engine
from media_cron.logging.models import (
    LogDestination,
    LogFormat,
    LoggingConfig,
    LogLevel,
    LogRecordPayload,
)


def setup_logging(config: LoggingConfig | None = None) -> LoggingEngine:
    """Configures application-wide logging using LoggingConfig."""
    cfg = config or LoggingConfig()
    engine.setup(cfg)
    return engine


def get_logger(name: str | None = None) -> logging.Logger:
    """Returns a logger namespaced under media_cron."""
    if not name:
        return logging.getLogger("media_cron")
    if name.startswith("media_cron"):
        return logging.getLogger(name)
    return logging.getLogger(f"media_cron.{name}")


__all__ = [
    "LoggingEngine",
    "engine",
    "setup_logging",
    "get_logger",
    "LogLevel",
    "LogDestination",
    "LogFormat",
    "LoggingConfig",
    "LogRecordPayload",
]
