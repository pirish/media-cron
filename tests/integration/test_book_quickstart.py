import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app

runner = CliRunner()


def _create_minimal_epub(
    path: Path, title: str, author: str, subjects: list[str] | None = None
) -> None:
    subs = subjects or []
    sub_xml = "\n".join(f"<dc:subject>{s}</dc:subject>" for s in subs)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        zf.writestr(
            "OEBPS/content.opf",
            f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    {sub_xml}
  </metadata>
  <manifest><item id="c" href="c.xhtml" media-type="application/xhtml+xml"/></manifest>
  <spine><itemref idref="c"/></spine>
</package>""",
        )
        zf.writestr("OEBPS/c.xhtml", "<html><body><p>Test</p></body></html>")


def test_quickstart_scenario_1_automated_identification(tmp_path: Path):
    """Validation Scenario 1: Automated Book & Author Identification via CLI diagnostic."""
    book_file = tmp_path / "Frank Herbert - Dune.mobi"
    book_file.write_bytes(b"dummy mobi file")

    result = runner.invoke(
        app,
        [
            "test-book-identify",
            str(book_file),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["status"] == "success"
    assert data["identified"]["title"] == "Dune"
    assert data["identified"]["author"] == "Frank Herbert"


def test_quickstart_scenario_2_udc_lookup(tmp_path: Path):
    """Validation Scenario 2: Universal Decimal Classification (UDC) Lookup."""
    epub_file = tmp_path / "Isaac Asimov - Foundation.epub"
    _create_minimal_epub(
        epub_file, title="Foundation", author="Isaac Asimov", subjects=["Science Fiction"]
    )

    result = runner.invoke(
        app,
        [
            "test-book-identify",
            str(epub_file),
            "--udc",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["status"] == "success"
    assert data["udc"] is not None
    assert data["udc"]["notation"] == "82-311.9"
    assert "Science fiction" in data["udc"]["description"]


def test_quickstart_scenario_3_format_conversion(tmp_path: Path):
    """Validation Scenario 3: Format Conversion to Standard EPUB with non-destructive preservation."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    staging_dir = tmp_path / "staging"
    source_dir.mkdir()
    dest_dir.mkdir()
    staging_dir.mkdir()

    sample_txt = source_dir / "sample_book.txt"
    sample_txt.write_text("Chapter 1: The Beginning\nOnce upon a time...", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "process",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--staging",
            str(staging_dir),
            "--books",
            "--convert-epub",
            "--retention",
            "preserve",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["processed_count"] == 1

    # Verify converted EPUB exists at destination
    converted_epub = dest_dir / "Books" / "Unknown Author" / "sample_book.epub"
    assert converted_epub.exists()
    assert converted_epub.stat().st_size > 0

    # Verify EPUB integrity
    with zipfile.ZipFile(converted_epub, "r") as zf:
        assert zf.read("mimetype") == b"application/epub+zip"
        assert "META-INF/container.xml" in zf.namelist()


def test_quickstart_scenario_4_dry_run_simulation(tmp_path: Path):
    """Validation Scenario 4: Dry-Run Simulation & Failure Safety."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    staging_dir = tmp_path / "staging"
    source_dir.mkdir()
    dest_dir.mkdir()
    staging_dir.mkdir()

    sample_txt = source_dir / "sample_book.txt"
    sample_txt.write_text("Chapter 1: Dry run test\nContent...", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "process",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--staging",
            str(staging_dir),
            "--books",
            "--convert-epub",
            "--retention",
            "replace",
            "--dry-run",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True

    # Source file MUST be untouched
    assert sample_txt.exists()
    # No destination files written
    assert not (dest_dir / "Books").exists()
