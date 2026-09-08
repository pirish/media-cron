import json
from pathlib import Path

from media_cron.config import (
    GeneralConfig,
    MediaCronConfig,
    PathsConfig,
    TorrentClientConfig,
)
from media_cron.models import BatchSummary
from media_cron.pipeline import Pipeline
from media_cron.torrent.clients.qbittorrent import QBittorrentClient


def test_hybrid_ingest_processes_both_drop_folder_and_torrent(tmp_path: Path, monkeypatch):
    drop_dir = tmp_path / "drop"
    torrent_downloads = tmp_path / "torrent_downloads"
    staging_dir = tmp_path / "staging"
    dest_dir = tmp_path / "library"

    drop_dir.mkdir()
    torrent_downloads.mkdir()
    staging_dir.mkdir()
    dest_dir.mkdir()

    # 1. Local drop file
    drop_file = drop_dir / "Manual.Drop.Movie.2024.1080p.mkv"
    drop_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"drop media" * 1000)

    # 2. Torrent download file
    torrent_folder = torrent_downloads / "Torrent.Movie.2023.1080p"
    torrent_folder.mkdir()
    torrent_file = torrent_folder / "Torrent.Movie.2023.1080p.mkv"
    torrent_file.write_bytes(b"\x1a\x45\xdf\xa3" + b"torrent media" * 1000)

    info_hash = "9999888877776666555544443333222211110000"

    mock_torrents = [
        {
            "hash": info_hash,
            "name": "Torrent.Movie.2023.1080p",
            "size": 5000,
            "progress": 1.0,
            "state": "uploading",
            "save_path": str(torrent_downloads),
            "content_path": str(torrent_folder),
            "category": "",
            "tags": "",
        }
    ]

    mock_files = [
        {
            "name": "Torrent.Movie.2023.1080p/Torrent.Movie.2023.1080p.mkv",
            "size": 5000,
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
        elif "/api/v2/torrents/addTags" in endpoint:
            return b""
        elif "/api/v2/torrents/setCategory" in endpoint:
            return b""
        return b""

    monkeypatch.setattr(QBittorrentClient, "_request", fake_request)

    client_cfg = TorrentClientConfig(
        client_type="qbittorrent",
        host="localhost",
        port=8080,
    )

    app_cfg = MediaCronConfig(
        general=GeneralConfig(mode="copy", dry_run=False),
        paths=PathsConfig(
            source_dir=drop_dir,
            staging_dir=staging_dir,
            destination_dir=dest_dir,
        ),
        active_torrent_client="qbittorrent",
        hybrid_ingest=True,
        torrent_clients={"qbittorrent": client_cfg},
    )

    pipeline = Pipeline(app_cfg)
    summary: BatchSummary = pipeline.run()

    # Verify both sources were processed
    assert summary.exit_code == 0
    assert summary.error_count == 0
    assert summary.processed_count == 2
    assert summary.torrent_summary is not None
    assert summary.torrent_summary["ingested_torrents"] == 1

    # Verify both movies are in the library
    lib_files = [f.name for f in dest_dir.rglob("*") if f.is_file()]
    assert any("Manual Drop Movie" in f for f in lib_files)
    assert any("Torrent Movie" in f for f in lib_files)
