import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from media_cron.config import (
    BooksConfig,
    ExternalProviderConfig,
    GeneralConfig,
    MediaCronConfig,
    PathsConfig,
)
from media_cron.metadata.base import MetadataProviderRegistry
from media_cron.metadata.book_identifier import BookIdentifier
from media_cron.metadata.book_reader import BookMetadataReader
from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.models import MetadataMatch
from media_cron.pipeline import Pipeline
from media_cron.plugins.input.directory import DirectoryScannerInput
from media_cron.plugins.lookup.book import BookLookupPlugin
from media_cron.plugins.output.cleaner import JunkCleanerOutput
from media_cron.plugins.output.organizer import LibraryOrganizerOutput
from media_cron.plugins.registry import PluginRegistry


@pytest.fixture
def isolated_book_env(tmp_path: Path):
    source_dir = tmp_path / "source"
    staging_dir = tmp_path / "staging"
    dest_dir = tmp_path / "destination"
    cache_dir = tmp_path / "cache"

    source_dir.mkdir()
    staging_dir.mkdir()
    dest_dir.mkdir()
    cache_dir.mkdir()

    return {
        "source": source_dir,
        "staging": staging_dir,
        "dest": dest_dir,
        "cache": cache_dir,
    }


def _create_sample_epub(path: Path, title: str, author: str, isbn: str | None = None) -> None:
    isbn_line = f'<dc:identifier id="isbn">urn:isbn:{isbn}</dc:identifier>' if isbn else ""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
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
    {isbn_line}
    <dc:date>1965</dc:date>
    <dc:subject>Science Fiction</dc:subject>
  </metadata>
</package>""",
        )


def test_single_file_epub_identification_pipeline(isolated_book_env):
    source = isolated_book_env["source"]
    staging = isolated_book_env["staging"]
    dest = isolated_book_env["dest"]
    cache_file = isolated_book_env["cache"] / "book_cache.json"

    epub_file = source / "Dune.epub"
    _create_sample_epub(epub_file, title="Dune", author="Frank Herbert", isbn="9780441172719")

    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="Dune",
            author="Frank Herbert",
            year=1965,
            work_id="OL893415W",
            provider="openlibrary",
            confidence=0.98,
            isbn="9780441172719",
            subjects=["Science Fiction", "Space Opera"],
        )
    ]
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: mock_provider)

    cache = MetadataCache(cache_file=cache_file)
    books_config = BooksConfig(
        enabled=True,
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )
    identifier = BookIdentifier(config=books_config, registry=registry, cache=cache)

    plugin_registry = PluginRegistry()
    plugin_registry.register_lookup("book_meta", lambda: BookLookupPlugin(identifier=identifier))
    plugin_registry.register_input("directory_scanner", DirectoryScannerInput)
    plugin_registry.register_output("library_organizer", LibraryOrganizerOutput)
    plugin_registry.register_output("junk_cleaner", JunkCleanerOutput)

    config = MediaCronConfig(
        paths=PathsConfig(source_dir=source, staging_dir=staging, destination_dir=dest),
        general=GeneralConfig(mode="copy", dry_run=False),
        books=books_config,
    )

    pipeline = Pipeline(config=config, registry=plugin_registry)
    summary = pipeline.run()

    assert summary.total_scanned == 1
    assert summary.processed_count == 1
    assert summary.error_count == 0

    expected_dest = dest / "Books" / "Frank Herbert" / "Dune.epub"
    assert expected_dest.exists()

    ident_summary = identifier.get_summary()
    assert ident_summary["total_books"] == 1
    assert ident_summary["identified_external"] == 1
    assert ident_summary["average_confidence"] == 0.98


def test_filename_heuristic_identification_txt(isolated_book_env):
    source = isolated_book_env["source"]
    cache_file = isolated_book_env["cache"] / "book_cache.json"

    txt_file = source / "Isaac Asimov - Foundation.txt"
    txt_file.write_text("Chapter 1\n...", encoding="utf-8")

    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="Foundation",
            author="Isaac Asimov",
            year=1951,
            work_id="OL46505W",
            provider="openlibrary",
            confidence=0.95,
            isbn="9780553293357",
            subjects=["Science Fiction"],
        )
    ]
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: mock_provider)

    cache = MetadataCache(cache_file=cache_file)
    books_config = BooksConfig(
        enabled=True,
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )
    identifier = BookIdentifier(config=books_config, registry=registry, cache=cache)

    reader = BookMetadataReader()
    local_meta = reader.read_metadata(txt_file)
    assert local_meta.author == "Isaac Asimov"
    assert local_meta.title == "Foundation"

    asset = identifier.identify(local_meta, path=txt_file)
    assert asset.confidence >= 0.85
    assert asset.title == "Foundation"
    assert asset.author == "Isaac Asimov"
    assert asset.isbn == "9780553293357"
    assert asset.provider == "openlibrary"


def test_offline_mode_preserves_local_cues(isolated_book_env):
    source = isolated_book_env["source"]
    cache_file = isolated_book_env["cache"] / "book_cache.json"

    epub_file = source / "Local Only - Mystery Book.epub"
    _create_sample_epub(epub_file, title="Mystery Book", author="Local Only")

    mock_provider = MagicMock()
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: mock_provider)

    cache = MetadataCache(cache_file=cache_file)
    books_config = BooksConfig(
        enabled=True,
        enable_external_lookup=False,  # Offline mode
    )
    identifier = BookIdentifier(config=books_config, registry=registry, cache=cache)

    reader = BookMetadataReader()
    local_meta = reader.read_metadata(epub_file)
    asset = identifier.identify(local_meta, path=epub_file)

    assert asset.title == "Mystery Book"
    assert asset.author == "Local Only"
    assert asset.provider == "local_tag"
    mock_provider.search.assert_not_called()
