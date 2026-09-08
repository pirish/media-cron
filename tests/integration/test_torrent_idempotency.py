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


def test_torrent_lifecycle_idempotency(tmp_path: Path, monkeypatch):
    downloads_dir = tmp_path / "downloads"
    staging_dir = tmp_path / "staging"
    dest_dir = tmp_path / "library"

    downloads_dir.mkdir()
    staging_dir.mkdir()
    dest_dir.mkdir()

    # Create torrent files
    torrent_folder = downloads_dir / "Inception.2010.1080p"
    torrent_folder.mkdir()
    movie_file = torrent_folder / "Inception.2010.1080p.mkv"
    movie_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"video data" * 1000)

    info_hash = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"

    # Torrent state simulator
    torrent_state = {
        "hash": info_hash,
        "name": "Inception.2010.1080p",
        "size": 10000,
        "progress": 1.0,
        "state": "uploading",
        "save_path": str(downloads_dir),
        "content_path": str(torrent_folder),
        "category": "",
        "tags": "",
    }

    mock_files = [
        {"name": "Inception.2010.1080p/Inception.2010.1080p.mkv", "size": 10000, "progress": 1.0},
    ]

    def fake_request(self, endpoint, method="GET", data=None):
        if "/api/v2/app/version" in endpoint:
            return b"v4.6.0"
        elif "/api/v2/auth/login" in endpoint:
            return b"Ok."
        elif "/api/v2/torrents/info" in endpoint:
            return json.dumps([torrent_state]).encode("utf-8")
        elif "/api/v2/torrents/files" in endpoint:
            return json.dumps(mock_files).encode("utf-8")
        elif "/api/v2/torrents/addTags" in endpoint:
            tags = data.get("tags", "") if data else ""
            existing = torrent_state.get("tags", "")
            torrent_state["tags"] = f"{existing},{tags}".strip(",")
            return b""
        elif "/api/v2/torrents/setCategory" in endpoint:
            cat = data.get("category", "") if data else ""
            torrent_state["category"] = cat
            return b""
        return b""

    monkeypatch.setattr(QBittorrentClient, "_request", fake_request)

    client_cfg = TorrentClientConfig(
        client_type="qbittorrent",
        host="localhost",
        port=8080,
        seeding=TorrentSeedingConfig(
            mode="direct_filesystem",
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
        ),
        active_torrent_client="qbittorrent",
        torrent_clients={"qbittorrent": client_cfg},
    )

    # --- Run 1: First Ingestion ---
    pipeline1 = Pipeline(app_cfg)
    summary1: BatchSummary = pipeline1.run()

    assert summary1.exit_code == 0
    assert summary1.processed_count == 1
    assert summary1.torrent_summary is not None
    assert summary1.torrent_summary["ingested_torrents"] == 1
    assert summary1.torrent_summary["tagged_torrents"] == 1

    # Verify state was updated on the client
    assert "media-cron-processed" in torrent_state["tags"]
    assert torrent_state["category"] == "media-cron-done"

    # --- Run 2: Subsequent Scheduled Ingestion ---
    pipeline2 = Pipeline(app_cfg)
    summary2: BatchSummary = pipeline2.run()

    assert summary2.exit_code == 0
    assert summary2.processed_count == 0
    assert summary2.torrent_summary is not None
    assert summary2.torrent_summary["discovered_torrents"] == 0
    assert summary2.torrent_summary["ingested_torrents"] == 0
