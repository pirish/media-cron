import json
from pathlib import Path

from typer.testing import CliRunner

from media_cron.cli import app
from media_cron.torrent.clients.qbittorrent import QBittorrentClient

runner = CliRunner()


def test_quickstart_scenario_1_dry_run(tmp_path: Path, monkeypatch):
    staging = tmp_path / "mc-staging"
    dest = tmp_path / "mc-library"
    seed = tmp_path / "mc-seeding"
    downloads = tmp_path / "downloads"

    staging.mkdir()
    dest.mkdir()
    seed.mkdir()
    downloads.mkdir()

    # Create completed torrent file
    movie_file = downloads / "Oppenheimer.2023.1080p.mkv"
    movie_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"movie data" * 100)

    info_hash = "111122223333444455556666777788889999aaaa"

    mock_torrents = [
        {
            "hash": info_hash,
            "name": "Oppenheimer.2023.1080p.mkv",
            "size": 5000,
            "progress": 1.0,
            "state": "uploading",
            "save_path": str(downloads),
            "content_path": str(movie_file),
            "category": "",
            "tags": "",
        }
    ]

    mock_files = [{"name": "Oppenheimer.2023.1080p.mkv", "size": 5000, "progress": 1.0}]

    def fake_request(self, endpoint, method="GET", data=None):
        if "/api/v2/app/version" in endpoint:
            return b"v4.6.0"
        elif "/api/v2/auth/login" in endpoint:
            return b"Ok."
        elif "/api/v2/torrents/info" in endpoint:
            return json.dumps(mock_torrents).encode("utf-8")
        elif "/api/v2/torrents/files" in endpoint:
            return json.dumps(mock_files).encode("utf-8")
        return b""

    monkeypatch.setattr(QBittorrentClient, "_request", fake_request)

    result = runner.invoke(
        app,
        [
            "run",
            "--torrent-client",
            "qbittorrent",
            "--staging-dir",
            str(staging),
            "--destination-dir",
            str(dest),
            "--seed-dir",
            str(seed),
            "--dry-run",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    # Zero files copied to staging in dry-run
    staged_files = list(staging.glob("*"))
    assert len(staged_files) == 0


def test_quickstart_scenario_2_live_clutter_preservation(tmp_path: Path, monkeypatch):
    staging = tmp_path / "mc-staging"
    dest = tmp_path / "mc-library"
    seed = tmp_path / "mc-seeding"
    downloads = tmp_path / "downloads"

    staging.mkdir()
    dest.mkdir()
    seed.mkdir()
    downloads.mkdir()

    # Create torrent folder with media and clutter
    torrent_folder = downloads / "Dune.Part.Two.2024.1080p"
    torrent_folder.mkdir()
    video_file = torrent_folder / "Dune.Part.Two.2024.1080p.mkv"
    video_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"dune data" * 100)
    nfo_file = torrent_folder / "release.nfo"
    nfo_file.write_text("Dune release notes")

    info_hash = "22223333444455556666777788889999aaaabbbb"

    mock_torrents = [
        {
            "hash": info_hash,
            "name": "Dune.Part.Two.2024.1080p",
            "size": 6000,
            "progress": 1.0,
            "state": "uploading",
            "save_path": str(downloads),
            "content_path": str(torrent_folder),
            "category": "",
            "tags": "",
        }
    ]

    mock_files = [
        {
            "name": "Dune.Part.Two.2024.1080p/Dune.Part.Two.2024.1080p.mkv",
            "size": 5000,
            "progress": 1.0,
        },
        {"name": "Dune.Part.Two.2024.1080p/release.nfo", "size": 1000, "progress": 1.0},
    ]

    relocated = {}
    tagged = {}

    def fake_request(self, endpoint, method="GET", data=None):
        if "/api/v2/app/version" in endpoint:
            return b"v4.6.0"
        elif "/api/v2/auth/login" in endpoint:
            return b"Ok."
        elif "/api/v2/torrents/info" in endpoint:
            return json.dumps(mock_torrents).encode("utf-8")
        elif "/api/v2/torrents/files" in endpoint:
            return json.dumps(mock_files).encode("utf-8")
        elif "/api/v2/torrents/setLocation" in endpoint:
            hashes = data.get("hashes") if data else ""
            location = data.get("location") if data else ""
            relocated[hashes] = location
            return b""
        elif "/api/v2/torrents/addTags" in endpoint:
            tagged["tag"] = data.get("tags") if data else ""
            return b""
        elif "/api/v2/torrents/setCategory" in endpoint:
            tagged["category"] = data.get("category") if data else ""
            return b""
        return b""

    monkeypatch.setattr(QBittorrentClient, "_request", fake_request)

    result = runner.invoke(
        app,
        [
            "run",
            "--torrent-client",
            "qbittorrent",
            "--staging-dir",
            str(staging),
            "--destination-dir",
            str(dest),
            "--seed-dir",
            str(seed),
            "--seeding-mode",
            "client_relocate",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    # Media organized
    organized_files = [f.name for f in dest.rglob("*") if f.is_file()]
    assert any("Dune Part Two" in f or "Dune.Part.Two" in f for f in organized_files)
    # Clutter excluded from library
    assert not any(f.endswith(".nfo") for f in organized_files)
    # Original files preserved in download path
    assert video_file.exists()
    assert nfo_file.exists()
    # Relocation and tagging executed
    assert info_hash in relocated
    assert tagged.get("tag") == "media-cron-processed"
    assert tagged.get("category") == "media-cron-done"


def test_quickstart_scenario_3_targeted_hook(tmp_path: Path, monkeypatch):
    staging = tmp_path / "mc-staging"
    dest = tmp_path / "mc-library"
    seed = tmp_path / "mc-seeding"
    downloads = tmp_path / "downloads"

    staging.mkdir()
    dest.mkdir()
    seed.mkdir()
    downloads.mkdir()

    target_hash = "4a5b6c7d8e9f0123456789abcdef0123456789ab"
    target_folder = downloads / "Targeted.Show.S01E01"
    target_folder.mkdir()
    video_file = target_folder / "Targeted.Show.S01E01.mkv"
    video_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"video" * 100)

    other_hash = "9999999999999999999999999999999999999999"

    mock_torrents = [
        {
            "hash": target_hash,
            "name": "Targeted.Show.S01E01",
            "size": 2000,
            "progress": 1.0,
            "state": "uploading",
            "save_path": str(downloads),
            "content_path": str(target_folder),
            "category": "",
            "tags": "",
        },
        {
            "hash": other_hash,
            "name": "Ignored.Movie.2024",
            "size": 5000,
            "progress": 1.0,
            "state": "uploading",
            "save_path": str(downloads),
            "content_path": str(downloads / "Ignored.Movie.2024"),
            "category": "",
            "tags": "",
        },
    ]

    mock_files = [
        {"name": "Targeted.Show.S01E01/Targeted.Show.S01E01.mkv", "size": 2000, "progress": 1.0}
    ]

    def fake_request(self, endpoint, method="GET", data=None):
        if "/api/v2/app/version" in endpoint:
            return b"v4.6.0"
        elif "/api/v2/auth/login" in endpoint:
            return b"Ok."
        elif "/api/v2/torrents/info" in endpoint:
            return json.dumps(mock_torrents).encode("utf-8")
        elif "/api/v2/torrents/files" in endpoint:
            return json.dumps(mock_files).encode("utf-8")
        return b""

    monkeypatch.setattr(QBittorrentClient, "_request", fake_request)

    result = runner.invoke(
        app,
        [
            "run",
            "--torrent-client",
            "qbittorrent",
            "--torrent-hash",
            target_hash,
            "--staging-dir",
            str(staging),
            "--destination-dir",
            str(dest),
            "--seed-dir",
            str(seed),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["torrent_summary"]["ingested_torrents"] == 1
    # Only targeted show organized
    organized = [f.name for f in dest.rglob("*") if f.is_file()]
    assert any("Targeted Show" in f or "Targeted.Show" in f for f in organized)
    assert not any("Ignored" in f for f in organized)


def test_quickstart_scenario_4_hybrid_drop_and_torrent(tmp_path: Path, monkeypatch):
    drop = tmp_path / "mc-drop"
    staging = tmp_path / "mc-staging"
    dest = tmp_path / "mc-library"
    seed = tmp_path / "mc-seeding"
    downloads = tmp_path / "downloads"

    drop.mkdir()
    staging.mkdir()
    dest.mkdir()
    seed.mkdir()
    downloads.mkdir()

    # Drop folder media
    drop_file = drop / "Dropped.Movie.2024.1080p.mkv"
    drop_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"dropped" * 100)

    # Torrent media
    torrent_folder = downloads / "Torrented.Movie.2023.1080p"
    torrent_folder.mkdir()
    torrent_file = torrent_folder / "Torrented.Movie.2023.1080p.mkv"
    torrent_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"torrented" * 100)

    info_hash = "abcdef1234567890abcdef1234567890abcdef12"
    mock_torrents = [
        {
            "hash": info_hash,
            "name": "Torrented.Movie.2023.1080p",
            "size": 3000,
            "progress": 1.0,
            "state": "uploading",
            "save_path": str(downloads),
            "content_path": str(torrent_folder),
            "category": "",
            "tags": "",
        }
    ]
    mock_files = [
        {
            "name": "Torrented.Movie.2023.1080p/Torrented.Movie.2023.1080p.mkv",
            "size": 3000,
            "progress": 1.0,
        }
    ]

    def fake_request(self, endpoint, method="GET", data=None):
        if "/api/v2/app/version" in endpoint:
            return b"v4.6.0"
        elif "/api/v2/auth/login" in endpoint:
            return b"Ok."
        elif "/api/v2/torrents/info" in endpoint:
            return json.dumps(mock_torrents).encode("utf-8")
        elif "/api/v2/torrents/files" in endpoint:
            return json.dumps(mock_files).encode("utf-8")
        return b""

    monkeypatch.setattr(QBittorrentClient, "_request", fake_request)

    result = runner.invoke(
        app,
        [
            "run",
            "--source-dir",
            str(drop),
            "--torrent-client",
            "qbittorrent",
            "--hybrid",
            "--staging-dir",
            str(staging),
            "--destination-dir",
            str(dest),
            "--seed-dir",
            str(seed),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["processed_count"] == 2
    assert data["torrent_summary"]["ingested_torrents"] == 1


def test_quickstart_scenario_5_test_client_diagnostics(monkeypatch):
    # 1. Success case
    def fake_ok(self, endpoint, method="GET", data=None):
        if "/api/v2/app/version" in endpoint:
            return b"v4.6.0"
        elif "/api/v2/auth/login" in endpoint:
            return b"Ok."
        return b""

    monkeypatch.setattr(QBittorrentClient, "_request", fake_ok)
    res_ok = runner.invoke(
        app, ["test-client", "--torrent-client", "qbittorrent", "--format", "json"]
    )
    assert res_ok.exit_code == 0
    data_ok = json.loads(res_ok.stdout)
    assert data_ok["connected"] is True

    # 2. Connection error case
    import urllib.error

    def fake_fail(self, endpoint, method="GET", data=None):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(QBittorrentClient, "_request", fake_fail)
    res_fail = runner.invoke(
        app, ["test-client", "--torrent-client", "qbittorrent", "--format", "json"]
    )
    assert res_fail.exit_code != 0
    data_fail = json.loads(res_fail.stdout)
    assert data_fail["connected"] is False
