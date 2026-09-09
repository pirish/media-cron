import time
from pathlib import Path

from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.models import MetadataMatch, UDCClassification


def test_book_cache_put_and_get(tmp_path: Path):
    cache_file = tmp_path / "book_cache.json"
    cache = MetadataCache(cache_file=cache_file, default_ttl=3600)

    udc = UDCClassification(
        notation="82-311.9",
        description="Literature - Fiction - Science fiction",
        confidence=1.0,
    )
    match = MetadataMatch(
        title="Dune",
        author="Frank Herbert",
        year=1965,
        provider="openlibrary",
        confidence=0.96,
        isbn="9780441172719",
        subjects=["Science Fiction", "Space Opera"],
        udc_code="82-311.9",
        udc_classification=udc,
    )

    cache.put(
        provider="openlibrary",
        title="  Dune  ",
        author="Frank   Herbert",
        match=match,
    )

    # Fetch from cache using normalized query
    retrieved = cache.get(provider="openlibrary", title="dune", author="frank herbert")
    assert retrieved is not None
    assert retrieved.title == "Dune"
    assert retrieved.isbn == "9780441172719"
    assert retrieved.udc_code == "82-311.9"
    assert retrieved.udc_classification is not None
    assert retrieved.udc_classification.notation == "82-311.9"

    # Reload cache from disk in a fresh instance
    reloaded_cache = MetadataCache(cache_file=cache_file)
    disk_retrieved = reloaded_cache.get(
        provider="openlibrary", title="Dune", author="Frank Herbert"
    )
    assert disk_retrieved is not None
    assert disk_retrieved.isbn == "9780441172719"
    assert disk_retrieved.udc_code == "82-311.9"


def test_book_cache_ttl_expiration(tmp_path: Path):
    cache_file = tmp_path / "book_cache.json"
    cache = MetadataCache(cache_file=cache_file, default_ttl=10)

    match = MetadataMatch(title="Neuromancer", author="William Gibson")
    cache.put(provider="openlibrary", title="Neuromancer", author="William Gibson", match=match)

    # Valid before expiration
    assert (
        cache.get(
            provider="openlibrary",
            title="Neuromancer",
            author="William Gibson",
            current_time=time.time(),
        )
        is not None
    )

    # Expired after TTL
    expired_result = cache.get(
        provider="openlibrary",
        title="Neuromancer",
        author="William Gibson",
        current_time=time.time() + 20,
    )
    assert expired_result is None
