import logging
import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def python_level(self) -> int:
        mapping = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
        }
        return mapping[self]

    @classmethod
    def from_str(cls, val: str) -> "LogLevel":
        normalized = val.strip().lower()
        try:
            return cls(normalized)
        except ValueError:
            raise ValueError(
                f"Invalid log level '{val}'. Allowed levels: {', '.join(cls.values())}"
            ) from None

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class LogDestination(StrEnum):
    CONSOLE = "console"  # Standard error stream (stderr)
    FILE = "file"  # Persistent file on disk (console silenced)
    BOTH = "both"  # Dual emission to both file and stderr

    @classmethod
    def from_str(cls, val: str) -> "LogDestination":
        normalized = val.strip().lower()
        try:
            return cls(normalized)
        except ValueError:
            raise ValueError(
                f"Invalid log destination '{val}'. Allowed: {', '.join(cls.values())}"
            ) from None

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


class LogFormat(StrEnum):
    TEXT = "text"  # Human-readable terminal output
    JSON = "json"  # Machine-readable single-line JSON

    @classmethod
    def from_str(cls, val: str) -> "LogFormat":
        normalized = val.strip().lower()
        try:
            return cls(normalized)
        except ValueError:
            raise ValueError(
                f"Invalid log format '{val}'. Allowed: {', '.join(cls.values())}"
            ) from None

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]


@dataclass
class LoggingConfig:
    level: LogLevel = LogLevel.INFO
    destination: LogDestination = LogDestination.CONSOLE
    file_path: Path | None = None
    format: LogFormat = LogFormat.TEXT
    max_size_mb: int = 10
    backup_count: int = 5

    def validate(self) -> None:
        """Validates configuration invariants, raising ValueError on invalid state."""
        if self.destination in (LogDestination.FILE, LogDestination.BOTH):
            if not self.file_path:
                raise ValueError(
                    f"Logging destination '{self.destination.value}' requires 'file_path' to be configured."
                )
            if self.file_path.exists() and self.file_path.is_dir():
                raise ValueError(
                    f"Configured log file path '{self.file_path}' is an existing directory; must specify a file path."
                )
        if self.max_size_mb <= 0:
            raise ValueError("Logging max_size_mb must be greater than 0.")
        if self.backup_count < 0:
            raise ValueError("Logging backup_count cannot be negative.")

    @classmethod
    def resolve_effective_config(
        cls,
        base_config: "LoggingConfig | None" = None,
        cli_level: str | None = None,
        cli_file: Path | None = None,
        cli_console: bool | None = None,
        cli_format: str | None = None,
        cli_max_size_mb: int | None = None,
        cli_backup_count: int | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> "LoggingConfig":
        """
        Enforces 4-tier precedence:
        1. CLI Options
        2. Environment Variables
        3. Config file (base_config)
        4. Built-in Defaults
        """
        env = env_vars if env_vars is not None else os.environ
        cfg = cls()

        # Tier 3: Base config if provided
        if base_config:
            cfg.level = base_config.level
            cfg.destination = base_config.destination
            cfg.file_path = base_config.file_path
            cfg.format = base_config.format
            cfg.max_size_mb = base_config.max_size_mb
            cfg.backup_count = base_config.backup_count

        # Tier 2: Environment Variables
        env_level = env.get("MEDIA_CRON_LOG_LEVEL")
        if env_level:
            cfg.level = LogLevel.from_str(env_level)

        env_dest = env.get("MEDIA_CRON_LOG_DESTINATION")
        if env_dest:
            cfg.destination = LogDestination.from_str(env_dest)

        env_file = env.get("MEDIA_CRON_LOG_FILE")
        if env_file:
            cfg.file_path = Path(env_file)
            if not env_dest and cfg.destination == LogDestination.CONSOLE:
                cfg.destination = LogDestination.FILE

        env_format = env.get("MEDIA_CRON_LOG_FORMAT")
        if env_format:
            cfg.format = LogFormat.from_str(env_format)

        env_size = env.get("MEDIA_CRON_LOG_MAX_SIZE_MB")
        if env_size:
            cfg.max_size_mb = int(env_size)

        env_backups = env.get("MEDIA_CRON_LOG_BACKUP_COUNT")
        if env_backups:
            cfg.backup_count = int(env_backups)

        # Tier 1: CLI Flags
        if cli_level:
            cfg.level = LogLevel.from_str(cli_level)

        if cli_file:
            cfg.file_path = Path(cli_file)
            if cfg.destination == LogDestination.CONSOLE:
                cfg.destination = LogDestination.FILE

        if cli_console is True:
            if cfg.file_path:
                cfg.destination = LogDestination.BOTH
            else:
                cfg.destination = LogDestination.CONSOLE
        elif cli_console is False:
            if cfg.file_path:
                cfg.destination = LogDestination.FILE

        if cli_format:
            cfg.format = LogFormat.from_str(cli_format)

        if cli_max_size_mb is not None:
            cfg.max_size_mb = int(cli_max_size_mb)

        if cli_backup_count is not None:
            cfg.backup_count = int(cli_backup_count)

        cfg.validate()
        return cfg


@dataclass
class LogRecordPayload:
    timestamp: str
    level: str
    logger: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    exception: str | None = None
