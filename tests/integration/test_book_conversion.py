from pathlib import Path
from unittest.mock import MagicMock

import pytest

from media_cron.config import (
    BookConversionConfig,
    BooksConfig,
    ExternalProviderConfig,
    GeneralConfig,
    MediaCronConfig,
    PathsConfig,
)
from media_cron.metadata.base import MetadataProviderRegistry
from media_cron.metadata.book_identifier import BookIdentifier
from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.converter import PythonFallbackConverter
from media_cron.metadata.models import BookMetadata, MetadataMatch
from media_cron.pipeline import Pipeline
from media_cron.plugins.input.directory import DirectoryScannerInput
from media_cron.plugins.lookup.book import BookLookupPlugin
from media_cron.plugins.output.cleaner import JunkCleanerOutput
from media_cron.plugins.output.organizer import LibraryOrganizerOutput
from media_cron.plugins.registry import PluginRegistry


@pytest.fixture
def isolated_conv_env(tmp_path: Path):
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


def test_txt_to_epub_conversion_in_pipeline(isolated_conv_env):
    source = isolated_conv_env["source"]
    staging = isolated_conv_env["staging"]
    dest = isolated_conv_env["dest"]
    cache_file = isolated_conv_env["cache"] / "book_cache.json"

    txt_file = source / "Isaac Asimov - Foundation.txt"
    txt_file.write_text("Chapter 1: The Psychohistorians\nHari Seldon was...", encoding="utf-8")

    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="Foundation",
            author="Isaac Asimov",
            year=1951,
            provider="openlibrary",
            confidence=0.98,
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
        conversion=BookConversionConfig(
            enabled=True,
            preferred_engine="python_fallback",
            retention_policy="preserve",
        ),
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

    # Verify destination file is .epub
    expected_dest = dest / "Books" / "Isaac Asimov" / "Foundation.epub"
    assert expected_dest.exists()
    assert expected_dest.stat().st_size > 0

    # Verify original source file is preserved in staging (retention policy preserve)
    assert (staging / txt_file.name).exists()


def test_already_standard_epub_not_reconverted(isolated_conv_env):
    source = isolated_conv_env["source"]
    staging = isolated_conv_env["staging"]
    dest = isolated_conv_env["dest"]

    epub_file = source / "Frank Herbert - Dune.epub"
    converter = PythonFallbackConverter()
    converter.convert(
        Path("/dev/null"),
        epub_file,
        metadata=BookMetadata(title="Dune", author="Frank Herbert"),
    )

    books_config = BooksConfig(
        enabled=True,
        enable_external_lookup=False,
        conversion=BookConversionConfig(enabled=True),
    )
    identifier = BookIdentifier(config=books_config)

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

    assert summary.error_count == 0
    expected_dest = dest / "Books" / "Frank Herbert" / "Dune.epub"
    assert expected_dest.exists()
