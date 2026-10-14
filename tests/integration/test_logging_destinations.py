from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.logging.engine import engine

runner = CliRunner()


def test_cli_file_destination_exclusive(tmp_path: Path):
    engine.reset()
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    log_file = tmp_path / "logs" / "run.log"

    result = runner.invoke(
        app,
        [
            "run",
            "--dry-run",
            "--log-file",
            str(log_file),
            "--source",
            str(src),
            "--destination",
            str(dest),
        ],
    )

    assert result.exit_code == 0
    # Console stderr must be silenced
    assert "[INFO]" not in result.stderr
    # File must exist and contain logs
    assert log_file.exists()
    assert "[INFO]" in log_file.read_text()
    engine.reset()


def test_cli_dual_destination_mirroring(tmp_path: Path):
    engine.reset()
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    log_file = tmp_path / "dual.log"

    result = runner.invoke(
        app,
        [
            "run",
            "--dry-run",
            "--log-file",
            str(log_file),
            "--console",
            "--source",
            str(src),
            "--destination",
            str(dest),
        ],
    )

    assert result.exit_code == 0
    # Both stderr and file have logs
    assert "[INFO]" in result.stderr
    assert log_file.exists()
    assert "[INFO]" in log_file.read_text()
    engine.reset()


def test_cli_unwritable_log_path_exits_code_2(tmp_path: Path):
    engine.reset()
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()

    blocking_file = tmp_path / "block"
    blocking_file.write_text("block")
    invalid_log = blocking_file / "uncreatable" / "app.log"

    result = runner.invoke(
        app,
        [
            "run",
            "--dry-run",
            "--log-file",
            str(invalid_log),
            "--source",
            str(src),
            "--destination",
            str(dest),
        ],
    )

    assert result.exit_code == 2
    assert "Configuration Error" in result.stderr or "Configuration Error" in result.output
    engine.reset()
