from pathlib import Path

import pytest

from media_cron.config import MediaCronConfig


def test_default_configuration():
    cfg = MediaCronConfig.load()
    assert cfg.general.mode == "hardlink"
    assert cfg.general.dry_run is False
    assert cfg.paths.staging_dir == Path.home() / ".media-cron" / "staging"
    assert ".nfo" in cfg.general.junk_extensions
    assert "movie" in cfg.templates
    assert cfg.plugins.input == "directory_scanner"


def test_load_yaml_file(tmp_path: Path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("""
paths:
  source_dir: "/tmp/downloads"
  staging_dir: "/tmp/staging"
  destination_dir: "/tmp/media"
  seed_dir: "/tmp/seeding"
general:
  mode: "move"
  dry_run: true
  sample_size_threshold_mb: 75
templates:
  movie: "Films/{title}/{title}.{ext}"
plugins:
  input: "custom_scanner"
""")
    cfg = MediaCronConfig.load(config_path=yaml_file)
    assert cfg.paths.source_dir == Path("/tmp/downloads")
    assert cfg.paths.staging_dir == Path("/tmp/staging")
    assert cfg.paths.destination_dir == Path("/tmp/media")
    assert cfg.paths.seed_dir == Path("/tmp/seeding")
    assert cfg.general.mode == "move"
    assert cfg.general.dry_run is True
    assert cfg.general.sample_size_threshold_mb == 75
    assert cfg.templates["movie"] == "Films/{title}/{title}.{ext}"
    assert cfg.plugins.input == "custom_scanner"


def test_environment_variable_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("MEDIA_CRON_SOURCE_DIR", str(tmp_path / "env_source"))
    monkeypatch.setenv("MEDIA_CRON_STAGING_DIR", str(tmp_path / "env_staging"))
    monkeypatch.setenv("MEDIA_CRON_DESTINATION_DIR", str(tmp_path / "env_dest"))
    monkeypatch.setenv("MEDIA_CRON_SEED_DIR", str(tmp_path / "env_seed"))
    monkeypatch.setenv("MEDIA_CRON_MODE", "copy")
    monkeypatch.setenv("MEDIA_CRON_DRY_RUN", "true")

    cfg = MediaCronConfig.load()
    assert cfg.paths.source_dir == tmp_path / "env_source"
    assert cfg.paths.staging_dir == tmp_path / "env_staging"
    assert cfg.paths.destination_dir == tmp_path / "env_dest"
    assert cfg.paths.seed_dir == tmp_path / "env_seed"
    assert cfg.general.mode == "copy"
    assert cfg.general.dry_run is True


def test_torrent_configuration_loading(tmp_path: Path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("""
active_torrent_client: "qbittorrent"
hybrid_ingest: true
torrent_clients:
  qbittorrent:
    client_type: "qbittorrent"
    host: "192.168.1.100"
    port: 8085
    username: "qbuser"
    password: "qbpassword"
    path_mappings:
      - remote_prefix: "/data/completed"
        local_prefix: "/mnt/storage/completed"
    filters:
      categories: ["movies"]
      exclude_tags: ["done"]
    seeding:
      mode: "client_relocate"
      target_location: "seed_dir"
      completion_tag: "processed"
      completion_category: "archived"
""")
    cfg = MediaCronConfig.load(config_path=yaml_file)
    assert cfg.active_torrent_client == "qbittorrent"
    assert cfg.hybrid_ingest is True
    assert "qbittorrent" in cfg.torrent_clients
    qb = cfg.torrent_clients["qbittorrent"]
    assert qb.host == "192.168.1.100"
    assert qb.port == 8085
    assert qb.username == "qbuser"
    assert qb.password == "qbpassword"
    assert len(qb.path_mappings) == 1
    assert qb.translate_path("/data/completed/movie.mkv") == Path(
        "/mnt/storage/completed/movie.mkv"
    )
    assert qb.filters.categories == ["movies"]
    assert qb.filters.exclude_tags == ["done"]
    assert qb.seeding.mode == "client_relocate"
    assert qb.seeding.completion_tag == "processed"
    assert qb.seeding.completion_category == "archived"


def test_torrent_environment_variable_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEDIA_CRON_ACTIVE_TORRENT_CLIENT", "qbittorrent")
    monkeypatch.setenv("MEDIA_CRON_HYBRID_INGEST", "true")
    monkeypatch.setenv("MEDIA_CRON_QBITTORRENT_HOST", "qbittorrent-host")
    monkeypatch.setenv("MEDIA_CRON_QBITTORRENT_PORT", "9999")
    monkeypatch.setenv("MEDIA_CRON_QBITTORRENT_USERNAME", "admin_env")
    monkeypatch.setenv("MEDIA_CRON_QBITTORRENT_PASSWORD", "secret_env")
    monkeypatch.setenv("MEDIA_CRON_SEEDING_MODE", "direct_filesystem")
    monkeypatch.setenv("MEDIA_CRON_COMPLETION_TAG", "env-tagged")
    monkeypatch.setenv("MEDIA_CRON_COMPLETION_CATEGORY", "env-done")

    cfg = MediaCronConfig.load()
    assert cfg.active_torrent_client == "qbittorrent"
    assert cfg.hybrid_ingest is True
    assert "qbittorrent" in cfg.torrent_clients
    qb = cfg.torrent_clients["qbittorrent"]
    assert qb.host == "qbittorrent-host"
    assert qb.port == 9999
    assert qb.username == "admin_env"
    assert qb.password == "secret_env"
    assert qb.seeding.mode == "direct_filesystem"
    assert qb.seeding.completion_tag == "env-tagged"
    assert qb.seeding.completion_category == "env-done"


def test_torrent_config_repr_masks_password():
    from media_cron.torrent.models import TorrentClientConfig

    cfg = TorrentClientConfig(
        client_type="qbittorrent",
        host="localhost",
        port=8080,
        username="admin",
        password="supersecretpassword",
    )
    repr_str = repr(cfg)
    assert "supersecretpassword" not in repr_str
    assert "***" in repr_str
