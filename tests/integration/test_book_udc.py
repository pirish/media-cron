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
    UDCConfig,
)
from media_cron.metadata.base import MetadataProviderRegistry
from media_cron.metadata.book_identifier import BookIdentifier
from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.models import MetadataMatch
from media_cron.metadata.udc import UDCResolver
from media_cron.pipeline import Pipeline
from media_cron.plugins.input.directory import DirectoryScannerInput
from media_cron.plugins.lookup.book import BookLookupPlugin
from media_cron.plugins.output.cleaner import JunkCleanerOutput
from media_cron.plugins.output.organizer import LibraryOrganizerOutput
from media_cron.plugins.registry import PluginRegistry


@pytest.fixture
def isolated_udc_env(tmp_path: Path):
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


def _create_sample_epub(path: Path, title: str, author: str, subjects: list[str]) -> None:
    subject_lines = "\n".join(f"<dc:subject>{s}</dc:subject>" for s in subjects)
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
    {subject_lines}
  </metadata>
</package>""",
        )


def test_book_identification_with_udc_enrichment(isolated_udc_env):
    source = isolated_udc_env["source"]
    staging = isolated_udc_env["staging"]
    dest = isolated_udc_env["dest"]
    cache_file = isolated_udc_env["cache"] / "book_cache.json"

    epub_file = source / "Dune.epub"
    _create_sample_epub(
        epub_file, title="Dune", author="Frank Herbert", subjects=["Science Fiction"]
    )

    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="Dune",
            author="Frank Herbert",
            year=1965,
            provider="openlibrary",
            confidence=0.98,
            subjects=["Science Fiction", "Space Opera"],
        )
    ]
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: mock_provider)

    cache = MetadataCache(cache_file=cache_file)
    udc_resolver = UDCResolver()
    books_config = BooksConfig(
        enabled=True,
        enable_external_lookup=True,
        udc_lookup=UDCConfig(enabled=True, min_confidence=0.70),
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )
    identifier = BookIdentifier(
        config=books_config,
        registry=registry,
        cache=cache,
        udc_resolver=udc_resolver,
    )

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

    # Verify BookAsset identification has UDC code
    asset = identifier.identify(path=epub_file)
    assert asset.udc_classification is not None
    assert asset.udc_classification.notation == "82-311.9"
    assert asset.canonical_metadata.udc_code == "82-311.9"


def test_book_identification_with_udc_disabled(isolated_udc_env):
    source = isolated_udc_env["source"]
    epub_file = source / "Foundation.epub"
    _create_sample_epub(
        epub_file, title="Foundation", author="Isaac Asimov", subjects=["Science Fiction"]
    )

    udc_resolver = UDCResolver()
    books_config = BooksConfig(
        enabled=True,
        enable_external_lookup=False,
        udc_lookup=UDCConfig(enabled=False),
    )
    identifier = BookIdentifier(
        config=books_config,
        udc_resolver=udc_resolver,
    )

    asset = identifier.identify(path=epub_file)
    assert asset.udc_classification is None
    assert asset.canonical_metadata.udc_code is None
