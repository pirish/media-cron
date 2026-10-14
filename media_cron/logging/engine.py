import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from media_cron.logging.models import (
    LogDestination,
    LogFormat,
    LoggingConfig,
)


class LoggingEngine:
    """Central engine for managing media-cron application logging."""

    LOGGER_NAME = "media_cron"

    def __init__(self) -> None:
        self._config = LoggingConfig()
        self._handlers: list[logging.Handler] = []

    def get_effective_config(self) -> LoggingConfig:
        """Returns the currently active LoggingConfig instance."""
        return self._config

    def setup(self, config: LoggingConfig) -> None:
        """
        Initializes handlers, formatters, and filters based on LoggingConfig.
        Ensures idempotency by removing previously registered handlers.
        Creates parent directories for file targets if required.
        """
        config.validate()
        self.reset()
        self._config = config

        target_logger = logging.getLogger(self.LOGGER_NAME)
        target_logger.setLevel(config.level.python_level)
        target_logger.propagate = False

        # Create Formatter (imported or fallback standard formatter)
        formatter = self._create_formatter(config.format)

        # 1. Console Stream Handler (stderr)
        if config.destination in (LogDestination.CONSOLE, LogDestination.BOTH):
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(config.level.python_level)
            console_handler.setFormatter(formatter)
            self._attach_filters(console_handler)
            target_logger.addHandler(console_handler)
            self._handlers.append(console_handler)

        # 2. Rotating File Handler
        if config.destination in (LogDestination.FILE, LogDestination.BOTH):
            if not config.file_path:
                raise ValueError("Logging file destination requires a valid file_path.")

            file_path = Path(config.file_path).resolve()
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = RotatingFileHandler(
                    file_path,
                    maxBytes=config.max_size_mb * 1024 * 1024,
                    backupCount=config.backup_count,
                    encoding="utf-8",
                )
            except (OSError, PermissionError) as e:
                raise ValueError(
                    f"Failed to initialize log file destination at '{file_path}': {e}"
                ) from e

            file_handler.setLevel(config.level.python_level)
            file_handler.setFormatter(formatter)
            self._attach_filters(file_handler)
            target_logger.addHandler(file_handler)
            self._handlers.append(file_handler)

    def _create_formatter(self, log_format: LogFormat) -> logging.Formatter:
        """Creates text or JSON formatter."""
        if log_format == LogFormat.JSON:
            try:
                from media_cron.logging.formatter import JsonLogFormatter

                return JsonLogFormatter()
            except ImportError:
                pass
        try:
            from media_cron.logging.formatter import StandardTextFormatter

            return StandardTextFormatter()
        except ImportError:
            return logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

    def _attach_filters(self, handler: logging.Handler) -> None:
        """Attaches sensitive data filter if available."""
        try:
            from media_cron.logging.sanitizer import SensitiveDataFilter

            handler.addFilter(SensitiveDataFilter())
        except ImportError:
            pass

    def reset(self) -> None:
        """Flushes and closes all handlers and restores default Python logging state."""
        target_logger = logging.getLogger(self.LOGGER_NAME)
        for handler in list(target_logger.handlers):
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
            target_logger.removeHandler(handler)
        self._handlers.clear()
        target_logger.setLevel(logging.INFO)
        target_logger.propagate = True
        self._config = LoggingConfig()


# Global engine singleton
engine = LoggingEngine()
