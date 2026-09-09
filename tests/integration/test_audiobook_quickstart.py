import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.metadata.models import MetadataMatch

runner = CliRunner()


@pytest.fixture
def mock_openlibrary_neverwhere():
    return [
        MetadataMatch(
            title="Neverwhere",
            author="Neil Gaiman",
            year=1996,
            work_id="OL45832W",
            provider="openlibrary",
            confidence=0.97,
        )
    ]


@pytest.fixture
def mock_openlibrary_dune():
    return [
        MetadataMatch(
            title="Dune",
            author="Frank Herbert",
            year=1965,
            work_id="OL893415W",
            provider="openlibrary",
            confidence=0.98,
        )
    ]


@pytest.fixture
def mock_openlibrary_1984():
    return [
        MetadataMatch(
            title="1984",
            author="George Orwell",
            year=1949,
            work_id="OL1168083W",
            provider="openlibrary",
            confidence=0.99,
        )
    ]


def test_quickstart_scenario_1_standalone_m4b(tmp_path: Path, mock_openlibrary_neverwhere):
    """Scenario 1: Standalone .m4b Identification via Open Library (P1)."""
    source = tmp_path / "downloads"
    staging = tmp_path / "staging"
    dest = tmp_path / "library"
    cache_file = tmp_path / "cache" / "audiobook_cache.json"

    source.mkdir(parents=True)
    staging.mkdir(parents=True)
    dest.mkdir(parents=True)

    config_data = {
        "paths": {
            "source_dir": str(source),
            "staging_dir": str(staging),
            "destination_dir": str(dest),
        },
        "general": {"mode": "copy", "dry_run": False},
        "audiobook": {
            "enable_external_lookup": True,
            "confidence_threshold": 0.85,
            "cache": {"cache_file": str(cache_file)},
        },
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    m4b_file = source / "Neil.Gaiman.-.Neverwhere.m4b"
    m4b_file.write_bytes(b"\x00\x00\x00\x1cftypM4B \x00\x00\x00\x00M4B mp42isom" + b"\x00" * 100)

    with patch(
        "media_cron.metadata.providers.openlibrary.OpenLibraryProvider.search"
    ) as mock_search:
        mock_search.return_value = mock_openlibrary_neverwhere

        res = runner.invoke(app, ["run", "--config", str(config_file), "--format", "json"])
        assert res.exit_code == 0
        summary = json.loads(res.stdout)
        assert summary["processed_count"] == 1
        assert summary["audiobook_summary"]["identified_external"] == 1

        expected_dest = dest / "Audiobooks" / "Neil Gaiman" / "Neverwhere" / "01 - Neverwhere.m4b"
        assert expected_dest.exists()


def test_quickstart_scenario_2_multi_file_bundle(tmp_path: Path, mock_openlibrary_dune):
    """Scenario 2: Multi-File Chapter Bundle with Disc Subfolders (P2)."""
    source = tmp_path / "downloads"
    staging = tmp_path / "staging"
    dest = tmp_path / "library"
    cache_file = tmp_path / "cache" / "audiobook_cache.json"

    cd1 = source / "Dune" / "CD1"
    cd2 = source / "Dune" / "CD2"
    cd1.mkdir(parents=True)
    cd2.mkdir(parents=True)
    staging.mkdir(parents=True)
    dest.mkdir(parents=True)

    t1 = cd1 / "Track01.mp3"
    t2 = cd1 / "Track02.mp3"
    t3 = cd2 / "Track01.mp3"
    for t in (t1, t2, t3):
        t.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00#" + b"\x00" * 50)

    config_data = {
        "paths": {
            "source_dir": str(source),
            "staging_dir": str(staging),
            "destination_dir": str(dest),
        },
        "general": {"mode": "copy"},
        "audiobook": {
            "enable_external_lookup": True,
            "confidence_threshold": 0.85,
            "cache": {"cache_file": str(cache_file)},
        },
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # Mock tag returning album Dune, author Frank Herbert
    mock_tag = MagicMock(
        album="Dune",
        artist="Frank Herbert",
        genre="Audiobook",
        track=None,
        year=None,
        bitrate=None,
    )

    with (
        patch(
            "media_cron.metadata.providers.openlibrary.OpenLibraryProvider.search"
        ) as mock_search,
        patch("media_cron.metadata.aggregator.TinyTag") as mock_tt_agg,
        patch("media_cron.plugins.lookup.audio.TinyTag") as mock_tt_lookup,
    ):
        mock_search.return_value = mock_openlibrary_dune
        mock_tt_agg.get.return_value = mock_tag
        mock_tt_lookup.get.return_value = mock_tag

        res = runner.invoke(
            app, ["run", "--config", str(config_file), "--dry-run", "--format", "json"]
        )
        assert res.exit_code == 0
        summary = json.loads(res.stdout)
        assert summary["dry_run"] is True
        assert summary["processed_count"] == 3
        # Provider queried exactly ONCE for the entire bundle
        assert mock_search.call_count == 1

        # Check planned destinations
        planned_dests = [
            op["destination_path"] for op in summary["operations"] if op.get("destination_path")
        ]
        assert len(planned_dests) == 3
        for d in planned_dests:
            assert "Audiobooks/Frank Herbert/Dune" in d


def test_quickstart_scenario_3_caching_performance(tmp_path: Path, mock_openlibrary_1984):
    """Scenario 3: Persistent Response Caching Performance (P3)."""
    cache_file = tmp_path / "cache" / "audiobook_cache.json"

    config_data = {
        "audiobook": {
            "enable_external_lookup": True,
            "cache": {"cache_file": str(cache_file), "ttl_seconds": 2592000},
        }
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    with patch(
        "media_cron.metadata.providers.openlibrary.OpenLibraryProvider.search"
    ) as mock_search:
        mock_search.return_value = mock_openlibrary_1984

        # 1. First lookup: cache miss
        res1 = runner.invoke(
            app,
            [
                "test-book-lookup",
                "1984",
                "--author",
                "George Orwell",
                "--config",
                str(config_file),
                "--format",
                "json",
            ],
        )
        assert res1.exit_code == 0
        d1 = json.loads(res1.stdout)
        assert d1["cached"] is False
        assert mock_search.call_count == 1
        assert cache_file.exists()

        # 2. Second lookup: cache hit (< 50ms)
        res2 = runner.invoke(
            app,
            [
                "test-book-lookup",
                "1984",
                "--author",
                "George Orwell",
                "--config",
                str(config_file),
                "--format",
                "json",
            ],
        )
        assert res2.exit_code == 0
        d2 = json.loads(res2.stdout)
        assert d2["cached"] is True
        assert d2["latency_ms"] < 50.0
        # Provider not called again
        assert mock_search.call_count == 1


def test_quickstart_scenario_4_offline_fallback(tmp_path: Path):
    """Scenario 4: Offline & Network Outage Fallback (P4)."""
    source = tmp_path / "downloads"
    staging = tmp_path / "staging"
    dest = tmp_path / "library"

    source.mkdir(parents=True)
    staging.mkdir(parents=True)
    dest.mkdir(parents=True)

    ab_file = source / "Frank.Herbert.-.Dune.m4b"
    ab_file.write_bytes(b"\x00\x00\x00\x1cftypM4B \x00\x00\x00\x00M4B mp42isom" + b"\x00" * 100)

    config_data = {
        "paths": {
            "source_dir": str(source),
            "staging_dir": str(staging),
            "destination_dir": str(dest),
        },
        "general": {"mode": "copy"},
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    with patch(
        "media_cron.metadata.providers.openlibrary.OpenLibraryProvider.search"
    ) as mock_search:
        res = runner.invoke(
            app,
            [
                "run",
                "--config",
                str(config_file),
                "--no-audiobook-lookup",
                "--format",
                "json",
            ],
        )
        assert res.exit_code == 0
        summary = json.loads(res.stdout)
        assert summary["audiobook_summary"]["identified_local_only"] == 1
        assert summary["audiobook_summary"]["identified_external"] == 0
        # No network requests initiated
        mock_search.assert_not_called()
