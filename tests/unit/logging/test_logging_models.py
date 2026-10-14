import logging
from pathlib import Path

import pytest

from media_cron.logging.models import (
    LogDestination,
    LogFormat,
    LoggingConfig,
    LogLevel,
)


def test_log_level_parsing_and_mapping():
    assert LogLevel.from_str("debug") == LogLevel.DEBUG
    assert LogLevel.from_str("INFO") == LogLevel.INFO
    assert LogLevel.from_str("Warning ") == LogLevel.WARNING
    assert LogLevel.from_str("ERROR") == LogLevel.ERROR

    assert LogLevel.DEBUG.python_level == logging.DEBUG
    assert LogLevel.INFO.python_level == logging.INFO
    assert LogLevel.WARNING.python_level == logging.WARNING
    assert LogLevel.ERROR.python_level == logging.ERROR

    with pytest.raises(ValueError, match="Invalid log level 'verbose'"):
        LogLevel.from_str("verbose")


def test_log_destination_parsing():
    assert LogDestination.from_str("console") == LogDestination.CONSOLE
    assert LogDestination.from_str("FILE") == LogDestination.FILE
    assert LogDestination.from_str("Both") == LogDestination.BOTH

    with pytest.raises(ValueError, match="Invalid log destination 'syslog'"):
        LogDestination.from_str("syslog")


def test_log_format_parsing():
    assert LogFormat.from_str("text") == LogFormat.TEXT
    assert LogFormat.from_str("JSON") == LogFormat.JSON

    with pytest.raises(ValueError, match="Invalid log format 'xml'"):
        LogFormat.from_str("xml")


def test_logging_config_defaults():
    cfg = LoggingConfig()
    assert cfg.level == LogLevel.INFO
    assert cfg.destination == LogDestination.CONSOLE
    assert cfg.file_path is None
    assert cfg.format == LogFormat.TEXT
    assert cfg.max_size_mb == 10
    assert cfg.backup_count == 5
    cfg.validate()


def test_logging_config_validation_file_requires_path():
    cfg = LoggingConfig(destination=LogDestination.FILE, file_path=None)
    with pytest.raises(ValueError, match="requires 'file_path'"):
        cfg.validate()

    cfg_both = LoggingConfig(destination=LogDestination.BOTH, file_path=None)
    with pytest.raises(ValueError, match="requires 'file_path'"):
        cfg_both.validate()


def test_logging_config_validation_directory_path(tmp_path: Path):
    cfg = LoggingConfig(destination=LogDestination.FILE, file_path=tmp_path)
    with pytest.raises(ValueError, match="is an existing directory"):
        cfg.validate()


def test_logging_config_validation_numeric_bounds(tmp_path: Path):
    file_path = tmp_path / "app.log"
    with pytest.raises(ValueError, match="max_size_mb must be greater than 0"):
        LoggingConfig(
            destination=LogDestination.FILE,
            file_path=file_path,
            max_size_mb=0,
        ).validate()

    with pytest.raises(ValueError, match="backup_count cannot be negative"):
        LoggingConfig(
            destination=LogDestination.FILE,
            file_path=file_path,
            backup_count=-1,
        ).validate()


def test_resolve_effective_config_precedence(tmp_path: Path):
    # Base configuration from YAML/file
    base = LoggingConfig(
        level=LogLevel.INFO,
        destination=LogDestination.CONSOLE,
        format=LogFormat.TEXT,
        max_size_mb=5,
        backup_count=2,
    )

    # 1. Base config applies when no env or CLI
    resolved = LoggingConfig.resolve_effective_config(base_config=base, env_vars={})
    assert resolved.level == LogLevel.INFO
    assert resolved.max_size_mb == 5

    # 2. Environment variables override base config
    env = {
        "MEDIA_CRON_LOG_LEVEL": "warning",
        "MEDIA_CRON_LOG_MAX_SIZE_MB": "25",
        "MEDIA_CRON_LOG_BACKUP_COUNT": "7",
    }
    resolved = LoggingConfig.resolve_effective_config(base_config=base, env_vars=env)
    assert resolved.level == LogLevel.WARNING
    assert resolved.max_size_mb == 25
    assert resolved.backup_count == 7

    # 3. CLI options override environment variables and base config
    cli_file = tmp_path / "cli.log"
    resolved = LoggingConfig.resolve_effective_config(
        base_config=base,
        cli_level="debug",
        cli_file=cli_file,
        cli_console=True,
        cli_format="json",
        cli_max_size_mb=50,
        cli_backup_count=10,
        env_vars=env,
    )
    assert resolved.level == LogLevel.DEBUG
    assert resolved.destination == LogDestination.BOTH
    assert resolved.file_path == cli_file
    assert resolved.format == LogFormat.JSON
    assert resolved.max_size_mb == 50
    assert resolved.backup_count == 10
