import time
from pathlib import Path

from media_cron.metadata.cache import MusicMetadataCache
from media_cron.metadata.models import MusicCatalogMatch


def test_music_cache_key_generation():
    key1 = MusicMetadataCache.generate_key(
        "MusicBrainz", "  Pink   Floyd  ", "  The  Dark  Side of the Moon "
    )
    key2 = MusicMetadataCache.generate_key("musicbrainz", "pink floyd", "the dark side of the moon")
    assert key1 == key2
    assert len(key1) == 64  # sha256


def test_music_cache_put_and_get(tmp_path: Path):
    cache_file = tmp_path / "music_cache.json"
    cache = MusicMetadataCache(cache_file=cache_file, default_ttl=3600)

    match = MusicCatalogMatch(
        title="The Dark Side of the Moon",
        artist="Pink Floyd",
        release_id="mb-rel-12345",
        provider="musicbrainz",
        confidence=0.98,
        year=1973,
        track_count=10,
        tracks=["Speak to Me", "Breathe", "Time"],
    )

    cache.put(
        provider="musicbrainz",
        artist="Pink Floyd",
        album="The Dark Side of the Moon",
        matches=[match],
    )

    retrieved = cache.get(
        provider="musicbrainz",
        artist="pink floyd",
        album="the dark side of the moon",
    )
    assert retrieved is not None
    assert len(retrieved) == 1
    assert retrieved[0].release_id == "mb-rel-12345"
    assert retrieved[0].confidence == 0.98
    assert retrieved[0].tracks == ["Speak to Me", "Breathe", "Time"]

    # Verify get_match helper
    top_match = cache.get_match(
        provider="musicbrainz",
        artist="pink floyd",
        album="the dark side of the moon",
    )
    assert top_match is not None
    assert top_match.title == "The Dark Side of the Moon"

    # Reload across fresh instance from disk
    reloaded = MusicMetadataCache(cache_file=cache_file)
    disk_retrieved = reloaded.get(
        provider="musicbrainz",
        artist="Pink Floyd",
        album="The Dark Side of the Moon",
    )
    assert disk_retrieved is not None
    assert len(disk_retrieved) == 1
    assert disk_retrieved[0].year == 1973


def test_music_cache_ttl_expiration(tmp_path: Path):
    cache_file = tmp_path / "music_cache.json"
    cache = MusicMetadataCache(cache_file=cache_file, default_ttl=10)

    match = MusicCatalogMatch(
        title="OK Computer",
        artist="Radiohead",
        release_id="mb-rel-67890",
        provider="musicbrainz",
        confidence=0.95,
        year=1997,
    )
    cache.put(
        provider="musicbrainz",
        artist="Radiohead",
        album="OK Computer",
        matches=[match],
    )

    # Valid before expiry
    now = time.time()
    assert cache.get("musicbrainz", "Radiohead", "OK Computer", current_time=now) is not None

    # Expired after TTL
    assert cache.get("musicbrainz", "Radiohead", "OK Computer", current_time=now + 20) is None


def test_music_cache_corrupted_file_recovery(tmp_path: Path):
    cache_file = tmp_path / "corrupt_music.json"
    cache_file.write_text("invalid json content")

    cache = MusicMetadataCache(cache_file=cache_file)
    assert cache.get("musicbrainz", "Radiohead", "OK Computer") is None
