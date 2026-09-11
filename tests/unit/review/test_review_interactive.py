from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from media_cron.cli import app
from tests.unit.review.test_review_cli import create_sample_review_item

runner = CliRunner()


def test_review_interactive_requires_tty(tmp_path: Path):
    review_dir = tmp_path / "review"
    create_sample_review_item(review_dir, "item_tty_1", "mystery.bin")

    # In CliRunner, isatty() is False by default
    result = runner.invoke(app, ["review", "--review-dir", str(review_dir)])
    assert result.exit_code != 0
    assert "interactive terminal" in result.output.lower() or "tty" in result.output.lower()


def test_review_interactive_skip_action(tmp_path: Path):
    review_dir = tmp_path / "review"
    create_sample_review_item(review_dir, "item_skip_1", "video.mkv", "movie")

    # Mock _is_interactive to return True
    # Inputs:
    # 1. Category prompt -> press enter to accept detected hint (movie)
    # 2. Title prompt -> "Test Movie"
    # 3. Year prompt -> "2022"
    # 4. Creator prompt -> ""
    # 5. Action prompt -> "s" (skip)
    user_inputs = "\nTest Movie\n2022\n\ns\n"

    with patch("media_cron.cli._is_interactive", return_value=True):
        result = runner.invoke(
            app,
            ["review", "--review-dir", str(review_dir)],
            input=user_inputs,
        )

    assert result.exit_code == 0
    assert "Skipped" in result.output or "skipped" in result.output.lower()
