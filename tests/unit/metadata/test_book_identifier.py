from pathlib import Path
from unittest.mock import MagicMock

from media_cron.config import BooksConfig
from media_cron.metadata.base import MetadataProviderRegistry
from media_cron.metadata.book_identifier import BookIdentifier
from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.models import BookMetadata, MetadataMatch
from media_cron.metadata.scorer import ConfidenceScorer


class DummyMockProvider:
    provider_name = "openlibrary"

    def __init__(self, candidates=None):
        self.candidates = candidates or []

    def search(self, title: str, author: str | None = None, config=None):
        return self.candidates


def test_book_identifier_high_confidence_match(tmp_path: Path):
    candidate = MetadataMatch(
        title="Dune",
        author="Frank Herbert",
        year=1965,
        provider="openlibrary",
        confidence=0.98,
        isbn="9780441172719",
        subjects=["Science Fiction", "Space Opera"],
    )
    provider = DummyMockProvider(candidates=[candidate])
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kwargs: provider)

    cache = MetadataCache(cache_file=tmp_path / "cache.json")
    identifier = BookIdentifier(
        registry=registry,
        cache=cache,
        scorer=ConfidenceScorer(),
        config=BooksConfig(confidence_threshold=0.85),
    )

    local_meta = BookMetadata(title="Dune", author="Frank Herbert")
    result = identifier.identify(local_meta, path=Path("Dune.mobi"))

    assert result.confidence >= 0.85
    assert result.title == "Dune"
    assert result.author == "Frank Herbert"
    assert result.isbn == "9780441172719"
    assert result.provider == "openlibrary"


def test_book_identifier_low_confidence_fallback(tmp_path: Path):
    candidate = MetadataMatch(
        title="Completely Different Title",
        author="Different Author",
        year=2020,
        provider="openlibrary",
        confidence=0.10,
    )
    provider = DummyMockProvider(candidates=[candidate])
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kwargs: provider)

    cache = MetadataCache(cache_file=tmp_path / "cache.json")
    identifier = BookIdentifier(
        registry=registry,
        cache=cache,
        scorer=ConfidenceScorer(),
        config=BooksConfig(confidence_threshold=0.85),
    )

    local_meta = BookMetadata(title="Dune", author="Frank Herbert")
    result = identifier.identify(local_meta, path=Path("Dune.mobi"))

    # Confidence below threshold -> preserves local title and author
    assert result.title == "Dune"
    assert result.author == "Frank Herbert"
    assert result.provider == "local_tag"


def test_book_identifier_offline_mode(tmp_path: Path):
    provider = DummyMockProvider()
    provider.search = MagicMock()
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kwargs: provider)

    cache = MetadataCache(cache_file=tmp_path / "cache.json")
    config = BooksConfig(enable_external_lookup=False)
    identifier = BookIdentifier(
        registry=registry,
        cache=cache,
        config=config,
    )

    local_meta = BookMetadata(title="Dune", author="Frank Herbert")
    result = identifier.identify(local_meta, path=Path("Dune.mobi"))

    assert result.title == "Dune"
    assert result.author == "Frank Herbert"
    assert result.provider == "local_tag"
    provider.search.assert_not_called()
