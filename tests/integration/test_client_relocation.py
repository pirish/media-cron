import json
from pathlib import Path

from media_cron.config import (
    GeneralConfig,
    MediaCronConfig,
    PathsConfig,
    TorrentClientConfig,
    TorrentSeedingConfig,
)
from media_cron.models import BatchSummary
from media_cron.pipeline import Pipeline
from media_cron.torrent.clients.qbittorrent import QBittorrentClient


def test_client_managed_relocation_preserves_clutter(tmp_path: Path, monkeypatch):
    # Setup directories
    downloads_dir = tmp_path / "downloads"
    staging_dir = tmp_path / "staging"
    dest_dir = tmp_path / "library"
    seed_dir = tmp_path / "seeding"

    downloads_dir.mkdir()
    staging_dir.mkdir()
    dest_dir.mkdir()
    seed_dir.mkdir()

    # Create torrent folder with media file AND non-media clutter (.nfo, sample.mkv, cover.jpg)
    torrent_folder = downloads_dir / "Test.Show.S01E01"
    torrent_folder.mkdir()
    video_file = torrent_folder / "Test.Show.S01E01.mkv"
    video_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"A" * 2000)

    nfo_file = torrent_folder / "info.nfo"
    nfo_file.write_text("Release info and tracker notes")

    sample_file = torrent_folder / "sample.mkv"
    sample_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"S" * 200)

    cover_file = torrent_folder / "cover.jpg"
    cover_file.write_bytes(b"\xff\xd8\xff" + b"C" * 100)

    info_hash = "1111222233334444555566667777888899990000"

    # Configure app with client_relocate seeding mode
    client_cfg = TorrentClientConfig(
        client_type="qbittorrent",
        host="localhost",
        port=8080,
        seeding=TorrentSeedingConfig(
            mode="client_relocate",
            target_location="seed_dir",
            completion_tag="media-cron-processed",
            completion_category="media-cron-done",
        ),
    )

    app_cfg = MediaCronConfig(
        general=GeneralConfig(mode="copy", dry_run=False),
        paths=PathsConfig(
            source_dir=None,
            staging_dir=staging_dir,
            destination_dir=dest_dir,
            seed_dir=seed_dir,
        ),
        active_torrent_client="qbittorrent",
        torrent_clients={"qbittorrent": client_cfg},
    )

    # Mock qBittorrent API
    mock_torrents = [
        {
            "hash": info_hash,
            "name": "Test.Show.S01E01",
            "size": 2500,
            "progress": 1.0,
            "state": "uploading",
            "save_path": str(downloads_dir),
            "content_path": str(torrent_folder),
            "category": "",
            "tags": "",
        }
    ]

    mock_files = [
        {"name": "Test.Show.S01E01/Test.Show.S01E01.mkv", "size": 2000, "progress": 1.0},
        {"name": "Test.Show.S01E01/info.nfo", "size": 100, "progress": 1.0},
        {"name": "Test.Show.S01E01/sample.mkv", "size": 200, "progress": 1.0},
        {"name": "Test.Show.S01E01/cover.jpg", "size": 100, "progress": 1.0},
    ]

    relocated_targets = {}

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
            relocated_targets[hashes] = location
            return b""
        elif "/api/v2/torrents/addTags" in endpoint:
            return b""
        elif "/api/v2/torrents/setCategory" in endpoint:
            return b""
        return b""

    monkeypatch.setattr(QBittorrentClient, "_request", fake_request)

    pipeline = Pipeline(app_cfg)
    summary: BatchSummary = pipeline.run()

    # Verify pipeline succeeded
    assert summary.exit_code == 0
    assert summary.error_count == 0

    # 1. Verify clutter was NOT moved into library
    organized_files = list(dest_dir.rglob("*"))
    organized_names = [f.name for f in organized_files if f.is_file()]
    assert any("Test Show" in n or "Test.Show" in n for n in organized_names)
    assert not any(n.endswith(".nfo") for n in organized_names)
    assert not any(n == "sample.mkv" for n in organized_names)
    assert not any(n == "cover.jpg" for n in organized_names)

    # 2. Verify original files and clutter were preserved in the download path
    assert video_file.exists()
    assert nfo_file.exists()
    assert sample_file.exists()
    assert cover_file.exists()

    # 3. Verify qBittorrent received setLocation to seed_dir
    assert info_hash in relocated_targets
    assert relocated_targets[info_hash] == str(seed_dir)
