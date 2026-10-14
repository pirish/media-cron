from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.logging.engine import engine

runner = CliRunner()


def test_cli_verbose_flag(tmp_path: Path):
    engine.reset()
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()

    result = runner.invoke(
        app,
        ["run", "--dry-run", "-v", "--source", str(src), "--destination", str(dest)],
    )

    assert result.exit_code == 0
    # In verbose mode, debug level is set
    assert engine.get_effective_config().level.value == "debug"
    engine.reset()


def test_cli_explicit_log_level(tmp_path: Path):
    engine.reset()
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()

    result = runner.invoke(
        app,
        [
            "run",
            "--dry-run",
            "--log-level",
            "warning",
            "--source",
            str(src),
            "--destination",
            str(dest),
        ],
    )

    assert result.exit_code == 0
    assert engine.get_effective_config().level.value == "warning"
    # INFO logs like 'Ingestion scan completed' should be suppressed
    assert "[INFO]" not in result.stderr
    engine.reset()


def test_cli_quiet_flag(tmp_path: Path):
    engine.reset()
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()

    result = runner.invoke(
        app,
        ["run", "--dry-run", "-q", "--source", str(src), "--destination", str(dest)],
    )

    assert result.exit_code == 0
    assert engine.get_effective_config().level.value == "error"
    assert "[INFO]" not in result.stderr
    engine.reset()


def test_cli_invalid_log_level_exits_code_2(tmp_path: Path):
    engine.reset()
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()

    result = runner.invoke(
        app,
        [
            "run",
            "--dry-run",
            "--log-level",
            "invalid_level",
            "--source",
            str(src),
            "--destination",
            str(dest),
        ],
    )

    assert result.exit_code == 2
    assert "Invalid log level" in result.stderr or "Invalid log level" in result.output
    engine.reset()


def test_cli_precedence_over_environment(tmp_path: Path, monkeypatch):
    engine.reset()
    monkeypatch.setenv("MEDIA_CRON_LOG_LEVEL", "error")
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()

    # CLI flag --log-level debug should override env var error
    result = runner.invoke(
        app,
        [
            "run",
            "--dry-run",
            "--log-level",
            "debug",
            "--source",
            str(src),
            "--destination",
            str(dest),
        ],
    )

    assert result.exit_code == 0
    assert engine.get_effective_config().level.value == "debug"
    engine.reset()
