import json
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.logging.engine import engine

runner = CliRunner()


def test_cli_default_logging_stream_isolation(tmp_path: Path):
    engine.reset()
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()

    result = runner.invoke(
        app,
        ["run", "--dry-run", "--source", str(src), "--destination", str(dest)],
    )

    assert result.exit_code == 0
    # stderr must have log output
    assert "[INFO]" in result.stderr
    assert "media_cron" in result.stderr

    # stdout must contain batch summary without log prefixes
    assert "=== Media-Cron Batch Summary ===" in result.stdout
    assert "[INFO]" not in result.stdout
    engine.reset()


def test_cli_json_output_with_logging(tmp_path: Path):
    engine.reset()
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()

    result = runner.invoke(
        app,
        ["run", "--dry-run", "--format", "json", "--source", str(src), "--destination", str(dest)],
    )

    assert result.exit_code == 0
    # stderr must receive the logs
    assert "[INFO]" in result.stderr

    # stdout must be strictly valid JSON
    data = json.loads(result.stdout)
    assert "batch_id" in data
    assert "exit_code" in data
    engine.reset()


def test_cli_log_format_json(tmp_path: Path):
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
            "--log-format",
            "json",
            "--source",
            str(src),
            "--destination",
            str(dest),
        ],
    )

    assert result.exit_code == 0
    # stderr must have JSON formatted log lines
    lines = [line.strip() for line in result.stderr.strip().splitlines() if line.strip()]
    assert len(lines) > 0
    for line in lines:
        entry = json.loads(line)
        assert "timestamp" in entry
        assert "level" in entry
        assert "logger" in entry
        assert "message" in entry
    engine.reset()
