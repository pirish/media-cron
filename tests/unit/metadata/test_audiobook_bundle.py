from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from media_cron.config import AudiobookConfig, ExternalProviderConfig
from media_cron.metadata.aggregator import AudiobookBundleAggregator
from media_cron.metadata.base import MetadataProviderRegistry
from media_cron.metadata.cache import MetadataCache
from media_cron.metadata.identifier import AudiobookIdentifier
from media_cron.metadata.models import MetadataMatch


@pytest.fixture
def mock_identifier(tmp_path: Path) -> AudiobookIdentifier:
    mock_provider = MagicMock()
    mock_provider.provider_name = "openlibrary"
    mock_provider.search.return_value = [
        MetadataMatch(
            title="The Way of Kings",
            author="Brandon Sanderson",
            year=2010,
            provider="openlibrary",
            confidence=0.96,
        )
    ]
    registry = MetadataProviderRegistry()
    registry.register("openlibrary", lambda **kw: mock_provider)

    cache = MetadataCache(cache_file=tmp_path / "cache.json")
    config = AudiobookConfig(
        enable_external_lookup=True,
        confidence_threshold=0.85,
        providers={
            "openlibrary": ExternalProviderConfig(
                provider_name="openlibrary", enabled=True, priority=10
            )
        },
    )
    ident = AudiobookIdentifier(config=config, registry=registry, cache=cache)
    ident._mock_provider = mock_provider
    return ident


def test_disc_subfolder_resolution(tmp_path: Path, mock_identifier: AudiobookIdentifier):
    aggregator = AudiobookBundleAggregator(identifier=mock_identifier)

    book_root = tmp_path / "Brandon Sanderson - The Way of Kings"
    cd1 = book_root / "CD1"
    cd2 = book_root / "Disc 2"
    cd1.mkdir(parents=True)
    cd2.mkdir(parents=True)

    track1 = cd1 / "01 - Chapter 1.mp3"
    track2 = cd2 / "01 - Chapter 20.mp3"
    track1.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00#" + b"\x00" * 20)
    track2.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00#" + b"\x00" * 20)

    assert aggregator.is_disc_folder(cd1) is True
    assert aggregator.is_disc_folder(cd2) is True
    assert aggregator.resolve_bundle_root(track1) == book_root
    assert aggregator.resolve_bundle_root(track2) == book_root
    assert aggregator.is_multi_file_bundle(track1) is True


def test_album_tag_consensus(tmp_path: Path, mock_identifier: AudiobookIdentifier):
    aggregator = AudiobookBundleAggregator(identifier=mock_identifier)

    book_root = tmp_path / "Unorganized Folder"
    book_root.mkdir()
    f1 = book_root / "track01.mp3"
    f2 = book_root / "track02.mp3"
    f3 = book_root / "track03.mp3"
    for f in (f1, f2, f3):
        f.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00#" + b"\x00" * 20)

    mock_tag1 = MagicMock(album="The Way of Kings", artist="Brandon Sanderson")
    mock_tag2 = MagicMock(album="The Way of Kings", artist="Brandon Sanderson")
    mock_tag3 = MagicMock(album=None, artist=None)

    with patch("media_cron.metadata.aggregator.TinyTag") as mock_tinytag:
        mock_tinytag.get.side_effect = [mock_tag1, mock_tag2, mock_tag3]
        album, artist = aggregator.extract_album_consensus([f1, f2, f3])
        assert album == "The Way of Kings"
        assert artist == "Brandon Sanderson"


def test_bundle_fallback_to_parent_directory(tmp_path: Path, mock_identifier: AudiobookIdentifier):
    aggregator = AudiobookBundleAggregator(identifier=mock_identifier)

    book_root = tmp_path / "Brandon Sanderson - The Way of Kings"
    book_root.mkdir()
    f1 = book_root / "01.mp3"
    f2 = book_root / "02.mp3"
    f1.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00#" + b"\x00" * 20)
    f2.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00#" + b"\x00" * 20)

    # Empty tags simulate missing/stripped tags
    with patch("media_cron.metadata.aggregator.TinyTag") as mock_tinytag:
        mock_tinytag.get.return_value = MagicMock(album=None, artist=None)
        bundle = aggregator.get_bundle(f1)

        assert bundle.is_multi_file is True
        assert len(bundle.files) == 2
        assert bundle.seed_title == "The Way of Kings"
        assert bundle.seed_author == "Brandon Sanderson"
        assert bundle.matched_metadata is not None
        assert bundle.matched_metadata.title == "The Way of Kings"
        assert bundle.matched_metadata.author == "Brandon Sanderson"


def test_bundle_single_query_across_tracks(tmp_path: Path, mock_identifier: AudiobookIdentifier):
    aggregator = AudiobookBundleAggregator(identifier=mock_identifier)

    book_root = tmp_path / "Brandon Sanderson - The Way of Kings"
    cd1 = book_root / "CD1"
    cd2 = book_root / "CD2"
    cd1.mkdir(parents=True)
    cd2.mkdir(parents=True)

    t1 = cd1 / "01.mp3"
    t2 = cd1 / "02.mp3"
    t3 = cd2 / "01.mp3"
    for t in (t1, t2, t3):
        t.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00#" + b"\x00" * 20)

    # Calling get_bundle for t1, then t2, then t3
    b1 = aggregator.get_bundle(t1)
    b2 = aggregator.get_bundle(t2)
    b3 = aggregator.get_bundle(t3)

    assert b1 is b2
    assert b2 is b3
    # Provider was queried only once for the entire bundle!
    assert mock_identifier._mock_provider.search.call_count == 1
