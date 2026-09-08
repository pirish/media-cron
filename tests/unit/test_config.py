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
