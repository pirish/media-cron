import logging
from pathlib import Path

from media_cron.logging.engine import LoggingEngine
from media_cron.logging.models import LogDestination, LoggingConfig


def test_file_destination_auto_creates_directories(tmp_path: Path):
    engine = LoggingEngine()
    log_file = tmp_path / "deeply" / "nested" / "logs" / "test.log"
    assert not log_file.parent.exists()

    config = LoggingConfig(
        destination=LogDestination.FILE,
        file_path=log_file,
    )
    engine.setup(config)

    logger = logging.getLogger("media_cron.dir_test")
    logger.info("Nested directory test message")

    engine.reset()
    assert log_file.exists()
    content = log_file.read_text()
    assert "Nested directory test message" in content


def test_file_rotation(tmp_path: Path):
    engine = LoggingEngine()
    log_file = tmp_path / "rotate.log"

    # Use 1MB limit for testing rotation with repeated messages
    config = LoggingConfig(
        destination=LogDestination.FILE,
        file_path=log_file,
        max_size_mb=1,
        backup_count=3,
    )
    engine.setup(config)

    logger = logging.getLogger("media_cron.rotate_test")
    # Write enough lines to exceed 1MB
    payload = "A" * 1024  # 1 KB per line
    for _ in range(1200):
        logger.info(payload)

    engine.reset()

    assert log_file.exists()
    # Check that backup file .1 exists due to rotation
    backup_1 = Path(str(log_file) + ".1")
    assert backup_1.exists()
