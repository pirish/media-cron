import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.metadata.models import MetadataMatch

runner = CliRunner()


@pytest.fixture
def mock_openlibrary_match():
    return [
        MetadataMatch(
            title="The Hobbit",
            author="J.R.R. Tolkien",
            year=1937,
            work_id="OL262758W",
            provider="openlibrary",
            confidence=0.96,
        )
    ]


def test_cli_test_book_lookup_json_schema(mock_openlibrary_match):
    with patch(
        "media_cron.metadata.providers.openlibrary.OpenLibraryProvider.search"
    ) as mock_search:
        mock_search.return_value = mock_openlibrary_match

        res = runner.invoke(
            app,
            [
                "test-book-lookup",
                "The Hobbit",
                "--author",
                "J.R.R. Tolkien",
                "--provider",
                "openlibrary",
                "--format",
                "json",
            ],
        )

        assert res.exit_code == 0
        data = json.loads(res.stdout)
        assert data["query_title"] == "The Hobbit"
        assert data["query_author"] == "J.R.R. Tolkien"
        assert data["provider"] == "openlibrary"
        assert data["matches_found"] == 1
        assert data["top_match"]["title"] == "The Hobbit"
        assert data["top_match"]["author"] == "J.R.R. Tolkien"
        assert data["top_match"]["confidence"] == 0.96
        assert "latency_ms" in data


def test_cli_test_book_lookup_text_output(mock_openlibrary_match):
    with patch(
        "media_cron.metadata.providers.openlibrary.OpenLibraryProvider.search"
    ) as mock_search:
        mock_search.return_value = mock_openlibrary_match

        res = runner.invoke(
            app,
            [
                "test-book-lookup",
                "The Hobbit",
                "--author",
                "J.R.R. Tolkien",
                "--provider",
                "openlibrary",
                "--format",
                "text",
            ],
        )

        assert res.exit_code == 0
        assert "=== Book Lookup Diagnostic ===" in res.stdout
        assert "Top Match:" in res.stdout
        assert "J.R.R. Tolkien" in res.stdout


def test_cli_run_audiobook_flags_and_dry_run(tmp_path: Path, mock_openlibrary_match):
    source = tmp_path / "source"
    dest = tmp_path / "destination"
    staging = tmp_path / "staging"
    source.mkdir()
    dest.mkdir()
    staging.mkdir()

    ab_file = source / "The Hobbit.m4b"
    ab_file.write_bytes(b"\x00\x00\x00\x1cftypM4B \x00\x00\x00\x00M4B mp42isom" + b"\x00" * 100)

    with patch(
        "media_cron.metadata.providers.openlibrary.OpenLibraryProvider.search"
    ) as mock_search:
        mock_search.return_value = mock_openlibrary_match

        res = runner.invoke(
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
                "--format",
                "json",
                "--audiobook-lookup",
                "--audiobook-confidence-threshold",
                "0.85",
            ],
        )

        assert res.exit_code == 0
        data = json.loads(res.stdout)
        assert data["dry_run"] is True
        assert "audiobook_summary" in data
        ab_summary = data["audiobook_summary"]
        assert ab_summary["total_audiobooks"] == 1
        assert ab_summary["identified_external"] == 1
        assert ab_summary["provider_breakdown"]["openlibrary"] == 1

        # Dry run ensures no files were written to destination
        assert not (dest / "Audiobooks").exists()


def test_cli_run_no_audiobook_lookup_flag(tmp_path: Path):
    source = tmp_path / "source"
    dest = tmp_path / "destination"
    staging = tmp_path / "staging"
    source.mkdir()
    dest.mkdir()
    staging.mkdir()

    ab_file = source / "Frank Herbert - Dune.m4b"
    ab_file.write_bytes(b"\x00\x00\x00\x1cftypM4B \x00\x00\x00\x00M4B mp42isom" + b"\x00" * 100)

    with patch(
        "media_cron.metadata.providers.openlibrary.OpenLibraryProvider.search"
    ) as mock_search:
        res = runner.invoke(
            app,
            [
                "run",
                "--source",
                str(source),
                "--destination",
                str(dest),
                "--staging",
                str(staging),
                "--no-audiobook-lookup",
                "--format",
                "json",
            ],
        )

        assert res.exit_code == 0
        mock_search.assert_not_called()
        data = json.loads(res.stdout)
        ab_summary = data.get("audiobook_summary", {})
        assert ab_summary.get("identified_local_only") == 1
        assert ab_summary.get("identified_external") == 0
