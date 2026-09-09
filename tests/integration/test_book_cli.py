import json
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app

runner = CliRunner()


def test_cli_dry_run_with_books(tmp_path: Path):
    source = tmp_path / "source"
    dest = tmp_path / "destination"
    staging = tmp_path / "staging"
    source.mkdir()
    dest.mkdir()
    staging.mkdir()

    txt_book = source / "Frank Herbert - Dune.txt"
    txt_book.write_text("Chapter 1\n...", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "run",
            "--source",
            str(source),
            "--destination",
            str(dest),
            "--staging",
            str(staging),
            "--dry-run",
            "--books",
            "--no-book-lookup",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["total_scanned"] == 1
    # Files in dest should not exist because dry-run
    assert not (dest / "Books").exists()
    # Source file remains intact
    assert txt_book.exists()


def test_cli_diagnostic_test_book_identify(tmp_path: Path):
    txt_book = tmp_path / "Arthur C. Clarke - Rendezvous with Rama.txt"
    txt_book.write_text("Chapter 1\nSpace probe...", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "test-book-identify",
            str(txt_book),
            "--no-udc",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["status"] == "success"
    assert data["identified"]["title"] == "Rendezvous with Rama"
    assert data["identified"]["author"] == "Arthur C. Clarke"


def test_cli_diagnostic_test_book_convert(tmp_path: Path):
    txt_book = tmp_path / "sample.txt"
    txt_book.write_text("Chapter 1\nTesting converter...", encoding="utf-8")
    out_dir = tmp_path / "output"

    result = runner.invoke(
        app,
        [
            "test-book-convert",
            str(txt_book),
            "--output-dir",
            str(out_dir),
            "--engine",
            "python",
        ],
    )

    assert result.exit_code == 0
    converted = out_dir / "sample.epub"
    assert converted.exists()
    assert converted.stat().st_size > 0


def test_cli_diagnostic_test_book_convert_dry_run(tmp_path: Path):
    txt_book = tmp_path / "sample.txt"
    txt_book.write_text("Chapter 1\nTesting dry run...", encoding="utf-8")
    out_dir = tmp_path / "output"

    result = runner.invoke(
        app,
        [
            "test-book-convert",
            str(txt_book),
            "--output-dir",
            str(out_dir),
            "--engine",
            "python",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert not (out_dir / "sample.epub").exists()
