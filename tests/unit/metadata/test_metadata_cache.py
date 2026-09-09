import time
from pathlib import Path

from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.models import MetadataMatch


def test_cache_put_and_get(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    cache = MetadataCache(cache_file=cache_file, default_ttl=3600)

    match = MetadataMatch(
        title="The Hobbit",
        author="J.R.R. Tolkien",
        year=1937,
        provider="openlibrary",
        confidence=0.95,
    )
    cache.put(provider="openlibrary", title="The Hobbit", author="J.R.R. Tolkien", match=match)

    retrieved = cache.get(provider="openlibrary", title="The Hobbit", author="J.R.R. Tolkien")
    assert retrieved is not None
    assert retrieved.title == "The Hobbit"
    assert retrieved.author == "J.R.R. Tolkien"
    assert retrieved.confidence == 0.95


def test_cache_persistence_across_instances(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    cache1 = MetadataCache(cache_file=cache_file, default_ttl=3600)

    match = MetadataMatch(
        title="Neverwhere",
        author="Neil Gaiman",
        year=1996,
        provider="openlibrary",
        confidence=0.92,
    )
    cache1.put(provider="openlibrary", title="Neverwhere", author="Neil Gaiman", match=match)

    # Instantiate second cache pointing to same file
    cache2 = MetadataCache(cache_file=cache_file, default_ttl=3600)
    retrieved = cache2.get(provider="openlibrary", title="Neverwhere", author="Neil Gaiman")
    assert retrieved is not None
    assert retrieved.title == "Neverwhere"
    assert retrieved.year == 1996


def test_cache_expiration(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    cache = MetadataCache(cache_file=cache_file, default_ttl=1)  # 1 second TTL

    match = MetadataMatch(
        title="Dune",
        author="Frank Herbert",
        year=1965,
        provider="openlibrary",
        confidence=0.90,
    )
    cache.put(
        provider="openlibrary", title="Dune", author="Frank Herbert", match=match, ttl_seconds=1
    )

    # Immediately available
    assert cache.get(provider="openlibrary", title="Dune", author="Frank Herbert") is not None

    # Simulate expiration by mocking time
    retrieved = cache.get(
        provider="openlibrary", title="Dune", author="Frank Herbert", current_time=time.time() + 10
    )
    assert retrieved is None


def test_cache_corrupted_file_recovery(tmp_path: Path):
    cache_file = tmp_path / "corrupt.json"
    cache_file.write_text("{invalid json content!!!")

    cache = MetadataCache(cache_file=cache_file)
    # Should not raise exception, but start empty
    assert cache.get(provider="openlibrary", title="Anything") is None
